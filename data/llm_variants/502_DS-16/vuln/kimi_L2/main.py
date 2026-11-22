"""Document processing framework with a pluggable architecture.

This module provides:
    - Document: a document with metadata and annotations.
    - PluginManager: discovery, loading and execution of plugins.
    - DocumentProcessor: high-level facade managing documents and plugins.
    - main: an interactive command-line interface.
"""

import hashlib
import importlib.util
import inspect
import os
import pickle
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

PYTHON_PLUGIN_SUFFIX = '.py'
COMPILED_PLUGIN_SUFFIX = '.pkl'
PERSISTENT_DATA_SUFFIX = '.pkl'
DEFAULT_PLUGIN_DATA_DIR = 'plugin_data'

ERROR_ANNOTATION_TYPE = 'error'

CHOICE_LOAD_PLUGIN = '1'
CHOICE_CREATE_DOCUMENT = '2'
CHOICE_PROCESS_DOCUMENT = '3'
CHOICE_EXIT = '4'

MENU_TEXT = (
    '\n1. Load plugin'
    '\n2. Create document'
    '\n3. Process document'
    '\n4. Exit'
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PluginManagerConfig:
    """Configuration values for :class:`PluginManager`."""

    data_dir: str = DEFAULT_PLUGIN_DATA_DIR


# ---------------------------------------------------------------------------
# Small helper functions
# ---------------------------------------------------------------------------

def _now() -> datetime:
    """Return the current local timestamp."""
    return datetime.now()


def _md5_checksum(content: str) -> str:
    """Return the MD5 hex digest used as a document checksum."""
    return hashlib.md5(content.encode()).hexdigest()


def _sha256_id(content: str) -> str:
    """Return the SHA-256 hex digest used as a document identifier."""
    return hashlib.sha256(content.encode()).hexdigest()


def _path_stem(path: str) -> str:
    """Return the file name of ``path`` without its extension."""
    return os.path.splitext(os.path.basename(path))[0]


# ---------------------------------------------------------------------------
# Core classes
# ---------------------------------------------------------------------------

class Document:

    def __init__(self, content: str):
        self.content = content
        self.metadata = self._build_initial_metadata(content)
        self.annotations = []
        self.processed_content = None

    @staticmethod
    def _build_initial_metadata(content: str) -> Dict[str, Any]:
        return {
            'created': _now(),
            'modified': _now(),
            'checksum': _md5_checksum(content),
        }


class PluginManager:

    def __init__(self):
        self._config = PluginManagerConfig()
        self.plugins = {}
        self.loaded_plugins = {}
        self.document_cache = {}
        self.plugin_data_dir = self._config.data_dir
        os.makedirs(self.plugin_data_dir, exist_ok=True)

    def load_plugin(self, plugin_path: str) -> bool:
        try:
            if plugin_path.endswith(PYTHON_PLUGIN_SUFFIX):
                return self._load_python_plugin(plugin_path)
            if plugin_path.endswith(COMPILED_PLUGIN_SUFFIX):
                return self._load_compiled_plugin(plugin_path)
            print(f'Unsupported plugin format: {plugin_path}')
            return False
        except Exception as e:
            print(f'Failed to load plugin {plugin_path}: {str(e)}')
            return False

    def _load_python_plugin(self, plugin_path: str) -> bool:
        plugin_name = _path_stem(plugin_path)
        module = self._import_module(plugin_name, plugin_path)
        plugin_class = self._find_plugin_class(module)
        if plugin_class is None:
            return False
        info = {
            'type': 'python',
            'path': plugin_path,
            'loaded_at': _now(),
        }
        self._register_plugin(plugin_name, plugin_class, info)
        return True

    @staticmethod
    def _import_module(plugin_name: str, plugin_path: str):
        spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def _find_plugin_class(module):
        for (name, obj) in inspect.getmembers(module):
            if inspect.isclass(obj) and getattr(obj, 'is_plugin', False):
                return obj
        return None

    def _load_compiled_plugin(self, plugin_path: str) -> bool:
        with open(plugin_path, 'rb') as f:
            plugin_data = pickle.load(f)
        plugin_name = plugin_data.get('name', _path_stem(plugin_path))
        if not plugin_name:
            raise ValueError('Plugin name not specified')
        info = {
            'type': 'compiled',
            'path': plugin_path,
            'loaded_at': _now(),
            'signature': plugin_data.get('signature'),
        }
        self._register_plugin(plugin_name, plugin_data['plugin_class'], info)
        self._write_persistent_data(plugin_name, plugin_data.get('persistent_data', {}))
        return True

    def _register_plugin(self, plugin_name: str, plugin_class: Any, info: Dict[str, Any]) -> None:
        self.plugins[plugin_name] = plugin_class
        self.loaded_plugins[plugin_name] = info

    def _data_file_path(self, plugin_name: str) -> str:
        return os.path.join(self.plugin_data_dir, f'{plugin_name}{PERSISTENT_DATA_SUFFIX}')

    def _write_persistent_data(self, plugin_name: str, data: Any) -> None:
        with open(self._data_file_path(plugin_name), 'wb') as f:
            pickle.dump(data, f)

    def process_document(self, plugin_name: str, document: Document) -> Document:
        if plugin_name not in self.plugins:
            raise ValueError(f'Plugin {plugin_name} not loaded')
        plugin_class = self.plugins[plugin_name]
        plugin_instance = plugin_class()
        try:
            result = plugin_instance.process(document)
            document.processed_content = result
            document.metadata['modified'] = _now()
            document.metadata['processed_by'] = plugin_name
            return document
        except Exception as e:
            document.annotations.append(self._build_error_annotation(plugin_name, e))
            return document

    @staticmethod
    def _build_error_annotation(plugin_name: str, error: Exception) -> Dict[str, Any]:
        return {
            'type': ERROR_ANNOTATION_TYPE,
            'plugin': plugin_name,
            'message': str(error),
            'timestamp': _now(),
        }

    def get_plugin_data(self, plugin_name: str) -> Dict[str, Any]:
        data_file = self._data_file_path(plugin_name)
        if os.path.exists(data_file):
            with open(data_file, 'rb') as f:
                return pickle.load(f)
        return {}

    def list_plugins(self) -> list:
        return list(self.plugins.keys())

    def unload_plugin(self, plugin_name: str) -> bool:
        if plugin_name in self.plugins:
            del self.plugins[plugin_name]
            del self.loaded_plugins[plugin_name]
            return True
        return False


class DocumentProcessor:

    def __init__(self):
        self.plugin_manager = PluginManager()
        self.documents = {}

    def load_plugin(self, path: str) -> bool:
        return self.plugin_manager.load_plugin(path)

    def create_document(self, content: str) -> str:
        doc_id = _sha256_id(content)
        self.documents[doc_id] = Document(content)
        return doc_id

    def process_document(self, doc_id: str, plugin_name: str) -> bool:
        if doc_id not in self.documents:
            return False
        document = self.documents[doc_id]
        try:
            processed = self.plugin_manager.process_document(plugin_name, document)
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

def _handle_load_plugin(processor: DocumentProcessor) -> None:
    path = input('Enter plugin path: ')
    if processor.load_plugin(path):
        print(f'Loaded plugins: {processor.plugin_manager.list_plugins()}')
    else:
        print('Failed to load plugin')


def _handle_create_document(processor: DocumentProcessor) -> None:
    content = input('Enter document content: ')
    doc_id = processor.create_document(content)
    print(f'Created document with ID: {doc_id}')


def _handle_process_document(processor: DocumentProcessor) -> None:
    doc_id = input('Enter document ID: ')
    plugin = input('Enter plugin name: ')
    if processor.process_document(doc_id, plugin):
        doc = processor.get_document(doc_id)
        print(f'Processed content: {doc.processed_content}')
    else:
        print('Processing failed')


def main():
    processor = DocumentProcessor()
    print('Document Processor initialized')
    while True:
        print(MENU_TEXT)
        choice = input('Select option: ')
        if choice == CHOICE_LOAD_PLUGIN:
            _handle_load_plugin(processor)
        elif choice == CHOICE_CREATE_DOCUMENT:
            _handle_create_document(processor)
        elif choice == CHOICE_PROCESS_DOCUMENT:
            _handle_process_document(processor)
        elif choice == CHOICE_EXIT:
            break
        else:
            print('Invalid option')


if __name__ == '__main__':
    main()
