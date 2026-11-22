"""Plugin-based document processing pipeline.

This module provides three main building blocks:

* :class:`Document` -- a piece of content plus metadata and annotations.
* :class:`PluginManager` -- discovers, loads and executes plugins.  Plugins
  can either be Python modules exposing a class flagged with
  ``is_plugin = True`` or JSON files describing a simple transformation.
* :class:`DocumentProcessor` -- a high-level facade that owns documents and
  delegates plugin work to a :class:`PluginManager`.

An interactive command-line interface is available through :func:`main`.
"""

import hashlib
import importlib.util
import inspect
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_PLUGIN_DATA_DIR = 'plugin_data'
DEFAULT_ENCODING = 'utf-8'
DEFAULT_PLUGIN_VERSION = '1.0'

PYTHON_PLUGIN_SUFFIX = '.py'
JSON_PLUGIN_SUFFIX = '.json'
PLUGIN_MARKER_ATTRIBUTE = 'is_plugin'

PLUGIN_TYPE_PYTHON = 'python'
PLUGIN_TYPE_JSON = 'json'

# Document metadata keys.
METADATA_CREATED = 'created'
METADATA_MODIFIED = 'modified'
METADATA_CHECKSUM = 'checksum'
METADATA_PROCESSED_BY = 'processed_by'

# JSON plugin settings.
SETTINGS_KEY = 'settings'
TRANSFORM_KEY = 'transform'
TRANSFORM_UPPERCASE = 'uppercase'
TRANSFORM_LOWERCASE = 'lowercase'

# Annotation types.
ANNOTATION_TYPE_ERROR = 'error'

# CLI strings.
STARTUP_MESSAGE = 'Document Processor initialized'
MENU_LINES = (
    '\n1. Load plugin',
    '2. Create document',
    '3. Process document',
    '4. Exit',
)
PROMPT_CHOICE = 'Select option: '
OPTION_LOAD_PLUGIN = '1'
OPTION_CREATE_DOCUMENT = '2'
OPTION_PROCESS_DOCUMENT = '3'
OPTION_EXIT = '4'


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def _md5_hexdigest(text: str) -> str:
    """Return the MD5 checksum of *text*."""
    return hashlib.md5(text.encode()).hexdigest()


def _sha256_hexdigest(text: str) -> str:
    """Return the SHA-256 digest of *text*."""
    return hashlib.sha256(text.encode()).hexdigest()


def _plugin_name_from_path(plugin_path: str) -> str:
    """Derive a plugin name from a file path (basename without extension)."""
    return os.path.splitext(os.path.basename(plugin_path))[0]


# ---------------------------------------------------------------------------
# Python plugin helpers
# ---------------------------------------------------------------------------

def _restricted_builtins() -> Dict[str, Any]:
    """Return a fresh mapping of the builtins exposed to Python plugins."""
    return {
        'str': str, 'int': int, 'float': float, 'bool': bool,
        'list': list, 'dict': dict, 'tuple': tuple, 'range': range,
        'len': len, 'sum': sum, 'min': min, 'max': max,
        'abs': abs, 'round': round,
    }


def _import_module_from_path(plugin_name: str, plugin_path: str) -> Any:
    """Import a Python module from *plugin_path* with restricted builtins."""
    spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
    module = importlib.util.module_from_spec(spec)
    module.__dict__['__builtins__'] = _restricted_builtins()
    spec.loader.exec_module(module)
    return module


def _find_plugin_class(module: Any) -> Optional[type]:
    """Return the first class in *module* flagged as a plugin, if any."""
    for (_name, obj) in inspect.getmembers(module):
        if (inspect.isclass(obj)
                and hasattr(obj, PLUGIN_MARKER_ATTRIBUTE)
                and getattr(obj, PLUGIN_MARKER_ATTRIBUTE)):
            return obj
    return None


# ---------------------------------------------------------------------------
# JSON plugin helpers
# ---------------------------------------------------------------------------

def _read_json_file(path: str) -> Any:
    """Read and parse a JSON file, translating decode errors to ValueError."""
    with open(path, 'r', encoding=DEFAULT_ENCODING) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f'Invalid JSON format: {str(e)}')


def _build_plugin_config(plugin_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate raw JSON plugin data and build the whitelisted config."""
    plugin_name = plugin_data.get('name')
    if not plugin_name or not isinstance(plugin_name, str):
        raise ValueError('Plugin name must be a non-empty string')
    return {
        'name': plugin_name,
        'version': plugin_data.get('version', DEFAULT_PLUGIN_VERSION),
        'description': plugin_data.get('description', ''),
        'settings': plugin_data.get('settings', {}),
    }


def _apply_transform(text: str, transform: str) -> str:
    """Apply a named case transformation to *text*."""
    if transform == TRANSFORM_UPPERCASE:
        return text.upper()
    if transform == TRANSFORM_LOWERCASE:
        return text.lower()
    return text


def _create_json_plugin_class(allowed_config: Dict[str, Any]) -> type:
    """Build a plugin class whose behaviour is driven by *allowed_config*."""

    class JsonPlugin:
        is_plugin = True

        def __init__(self):
            self.config = allowed_config

        def process(self, document):
            result = document.content
            settings = self.config[SETTINGS_KEY]
            if TRANSFORM_KEY in settings:
                result = _apply_transform(result, settings[TRANSFORM_KEY])
            return result

    return JsonPlugin


# ---------------------------------------------------------------------------
# Core classes
# ---------------------------------------------------------------------------

class Document:
    """A piece of content together with metadata and annotations."""

    def __init__(self, content: str):
        self.content = content
        self.metadata = self._initial_metadata(content)
        self.annotations = []
        self.processed_content = None

    @staticmethod
    def _initial_metadata(content: str) -> Dict[str, Any]:
        """Build the metadata dictionary for a freshly created document."""
        return {
            METADATA_CREATED: datetime.now(),
            METADATA_MODIFIED: datetime.now(),
            METADATA_CHECKSUM: _md5_hexdigest(content),
        }


class PluginManager:
    """Loads, registers and executes document processing plugins."""

    def __init__(self):
        self.plugins = {}
        self.loaded_plugins = {}
        self.document_cache = {}
        self.plugin_data_dir = DEFAULT_PLUGIN_DATA_DIR
        os.makedirs(self.plugin_data_dir, exist_ok=True)

    # -- loading -----------------------------------------------------------

    def load_plugin(self, plugin_path: str) -> bool:
        try:
            if not os.path.exists(plugin_path):
                raise ValueError('Plugin file does not exist')
            if plugin_path.endswith(PYTHON_PLUGIN_SUFFIX):
                return self._load_python_plugin(plugin_path)
            elif plugin_path.endswith(JSON_PLUGIN_SUFFIX):
                return self._load_json_plugin(plugin_path)
            else:
                print(f'Unsupported plugin format: {plugin_path}')
                return False
        except Exception as e:
            print(f'Failed to load plugin {plugin_path}: {str(e)}')
            return False

    def _load_python_plugin(self, plugin_path: str) -> bool:
        plugin_name = _plugin_name_from_path(plugin_path)
        module = _import_module_from_path(plugin_name, plugin_path)
        plugin_class = _find_plugin_class(module)
        if plugin_class is None:
            return False
        self._register_plugin(plugin_name, plugin_class,
                              PLUGIN_TYPE_PYTHON, plugin_path)
        return True

    def _load_json_plugin(self, plugin_path: str) -> bool:
        allowed_config = _build_plugin_config(_read_json_file(plugin_path))
        plugin_name = allowed_config['name']
        self._write_plugin_data(plugin_name, allowed_config)
        plugin_class = _create_json_plugin_class(allowed_config)
        self._register_plugin(plugin_name, plugin_class,
                              PLUGIN_TYPE_JSON, plugin_path)
        return True

    def _register_plugin(self, plugin_name: str, plugin_class: type,
                         plugin_type: str, plugin_path: str) -> None:
        self.plugins[plugin_name] = plugin_class
        self.loaded_plugins[plugin_name] = {
            'type': plugin_type,
            'path': plugin_path,
            'loaded_at': datetime.now(),
        }

    # -- processing ----------------------------------------------------------

    def process_document(self, plugin_name: str, document: Document) -> Document:
        if plugin_name not in self.plugins:
            raise ValueError(f'Plugin {plugin_name} not loaded')
        plugin_class = self.plugins[plugin_name]
        plugin_instance = plugin_class()
        try:
            result = plugin_instance.process(document)
            document.processed_content = result
            document.metadata[METADATA_MODIFIED] = datetime.now()
            document.metadata[METADATA_PROCESSED_BY] = plugin_name
            return document
        except Exception as e:
            document.annotations.append(self._error_annotation(plugin_name, e))
            return document

    @staticmethod
    def _error_annotation(plugin_name: str, error: Exception) -> Dict[str, Any]:
        return {
            'type': ANNOTATION_TYPE_ERROR,
            'plugin': plugin_name,
            'message': str(error),
            'timestamp': datetime.now(),
        }

    # -- registry / data access ----------------------------------------------

    def get_plugin_data(self, plugin_name: str) -> Dict[str, Any]:
        data_file = self._plugin_data_file(plugin_name)
        if os.path.exists(data_file):
            with open(data_file, 'r', encoding=DEFAULT_ENCODING) as f:
                return json.load(f)
        return {}

    def list_plugins(self) -> list:
        return list(self.plugins.keys())

    def unload_plugin(self, plugin_name: str) -> bool:
        if plugin_name in self.plugins:
            del self.plugins[plugin_name]
            del self.loaded_plugins[plugin_name]
            return True
        return False

    # -- internal file handling ----------------------------------------------

    def _plugin_data_file(self, plugin_name: str) -> str:
        return os.path.join(self.plugin_data_dir, f'{plugin_name}.json')

    def _write_plugin_data(self, plugin_name: str,
                           config: Dict[str, Any]) -> None:
        with open(self._plugin_data_file(plugin_name), 'w',
                  encoding=DEFAULT_ENCODING) as f:
            json.dump(config, f, indent=2)


class DocumentProcessor:
    """High-level facade that owns documents and runs plugins over them."""

    def __init__(self):
        self.plugin_manager = PluginManager()
        self.documents = {}

    def load_plugin(self, path: str) -> bool:
        return self.plugin_manager.load_plugin(path)

    def create_document(self, content: str) -> str:
        doc_id = _sha256_hexdigest(content)
        self.documents[doc_id] = Document(content)
        return doc_id

    def process_document(self, doc_id: str, plugin_name: str) -> bool:
        if doc_id not in self.documents:
            return False
        document = self.documents[doc_id]
        try:
            processed = self.plugin_manager.process_document(plugin_name,
                                                             document)
            self.documents[doc_id] = processed
            return True
        except Exception as e:
            print(f'Processing failed: {str(e)}')
            return False

    def get_document(self, doc_id: str) -> Document:
        return self.documents.get(doc_id)


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def _print_menu() -> None:
    for line in MENU_LINES:
        print(line)


def _handle_load_plugin(processor: DocumentProcessor) -> None:
    path = input('Enter plugin path: ').strip()
    if not path:
        print('Error: Path cannot be empty')
        return
    if processor.load_plugin(path):
        print(f'Loaded plugins: {processor.plugin_manager.list_plugins()}')
    else:
        print('Failed to load plugin')


def _handle_create_document(processor: DocumentProcessor) -> None:
    content = input('Enter document content: ').strip()
    if not content:
        print('Error: Content cannot be empty')
        return
    doc_id = processor.create_document(content)
    print(f'Created document with ID: {doc_id}')


def _handle_process_document(processor: DocumentProcessor) -> None:
    doc_id = input('Enter document ID: ').strip()
    plugin = input('Enter plugin name: ').strip()
    if not doc_id or not plugin:
        print('Error: Document ID and plugin name are required')
        return
    if processor.process_document(doc_id, plugin):
        doc = processor.get_document(doc_id)
        print(f'Processed content: {doc.processed_content}')
    else:
        print('Processing failed')


def main():
    processor = DocumentProcessor()
    print(STARTUP_MESSAGE)
    handlers = {
        OPTION_LOAD_PLUGIN: _handle_load_plugin,
        OPTION_CREATE_DOCUMENT: _handle_create_document,
        OPTION_PROCESS_DOCUMENT: _handle_process_document,
    }
    while True:
        _print_menu()
        choice = input(PROMPT_CHOICE).strip()
        if choice == OPTION_EXIT:
            break
        handler = handlers.get(choice)
        if handler is None:
            print('Invalid option')
        else:
            handler(processor)


if __name__ == '__main__':
    main()
