import os
import hashlib
import importlib
import importlib.util
import inspect
import json
from datetime import datetime
from typing import Dict, Any


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

DEFAULT_PLUGIN_DATA_DIR = 'plugin_data'

PYTHON_PLUGIN_EXTENSION = '.py'
JSON_PLUGIN_EXTENSION = '.json'

PLUGIN_TYPE_PYTHON = 'python'
PLUGIN_TYPE_JSON = 'json'

DEFAULT_PLUGIN_VERSION = '1.0'
JSON_FILE_ENCODING = 'utf-8'
JSON_INDENT = 2

SANDBOX_BUILTINS = {
    'str': str,
    'int': int,
    'float': float,
    'bool': bool,
    'list': list,
    'dict': dict,
    'tuple': tuple,
    'range': range,
    'len': len,
    'sum': sum,
    'min': min,
    'max': max,
    'abs': abs,
    'round': round,
}

MENU_LOAD_PLUGIN = '1'
MENU_CREATE_DOCUMENT = '2'
MENU_PROCESS_DOCUMENT = '3'
MENU_EXIT = '4'

MENU_TEXT_LINES = (
    '\n1. Load plugin',
    '2. Create document',
    '3. Process document',
    '4. Exit',
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _md5_hex(content: str) -> str:
    return hashlib.md5(content.encode()).hexdigest()


def _sha256_hex(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _plugin_record(plugin_type: str, plugin_path: str) -> Dict[str, Any]:
    return {'type': plugin_type, 'path': plugin_path, 'loaded_at': datetime.now()}


def _build_json_plugin_class(config: Dict[str, Any]):
    """Create a plugin class backed by a validated JSON configuration."""

    class JsonPlugin:
        is_plugin = True

        def __init__(self):
            self.config = config

        def process(self, document):
            result = document.content
            if 'transform' in self.config['settings']:
                transform = self.config['settings']['transform']
                if transform == 'uppercase':
                    result = result.upper()
                elif transform == 'lowercase':
                    result = result.lower()
            return result

    return JsonPlugin


# --------------------------------------------------------------------------- #
# Domain classes
# --------------------------------------------------------------------------- #

class Document:

    def __init__(self, content: str):
        self.content = content
        self.metadata = {
            'created': datetime.now(),
            'modified': datetime.now(),
            'checksum': _md5_hex(content),
        }
        self.annotations = []
        self.processed_content = None


class PluginManager:

    def __init__(self):
        self.plugins = {}
        self.loaded_plugins = {}
        self.document_cache = {}
        self.plugin_data_dir = DEFAULT_PLUGIN_DATA_DIR
        os.makedirs(self.plugin_data_dir, exist_ok=True)

    # -- loading ---------------------------------------------------------- #

    def load_plugin(self, plugin_path: str) -> bool:
        try:
            if not os.path.exists(plugin_path):
                raise ValueError('Plugin file does not exist')
            if plugin_path.endswith(PYTHON_PLUGIN_EXTENSION):
                return self._load_python_plugin(plugin_path)
            elif plugin_path.endswith(JSON_PLUGIN_EXTENSION):
                return self._load_json_plugin(plugin_path)
            else:
                print(f'Unsupported plugin format: {plugin_path}')
                return False
        except Exception as e:
            print(f'Failed to load plugin {plugin_path}: {str(e)}')
            return False

    def _register(self, plugin_name: str, plugin_class, plugin_type: str,
                  plugin_path: str) -> None:
        self.plugins[plugin_name] = plugin_class
        self.loaded_plugins[plugin_name] = _plugin_record(plugin_type, plugin_path)

    def _load_python_plugin(self, plugin_path: str) -> bool:
        plugin_name = os.path.splitext(os.path.basename(plugin_path))[0]
        spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
        module = importlib.util.module_from_spec(spec)
        module.__dict__['__builtins__'] = dict(SANDBOX_BUILTINS)
        spec.loader.exec_module(module)
        for (name, obj) in inspect.getmembers(module):
            if inspect.isclass(obj) and hasattr(obj, 'is_plugin') and obj.is_plugin:
                self._register(plugin_name, obj, PLUGIN_TYPE_PYTHON, plugin_path)
                return True
        return False

    @staticmethod
    def _read_json_plugin_file(plugin_path: str) -> Dict[str, Any]:
        with open(plugin_path, 'r', encoding=JSON_FILE_ENCODING) as f:
            try:
                return json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f'Invalid JSON format: {str(e)}')

    @staticmethod
    def _build_allowed_config(plugin_data: Dict[str, Any]) -> Dict[str, Any]:
        plugin_name = plugin_data.get('name')
        if not plugin_name or not isinstance(plugin_name, str):
            raise ValueError('Plugin name must be a non-empty string')
        return {
            'name': plugin_name,
            'version': plugin_data.get('version', DEFAULT_PLUGIN_VERSION),
            'description': plugin_data.get('description', ''),
            'settings': plugin_data.get('settings', {}),
        }

    def _plugin_data_path(self, plugin_name: str) -> str:
        return os.path.join(self.plugin_data_dir, f'{plugin_name}.json')

    def _persist_plugin_config(self, plugin_name: str, config: Dict[str, Any]) -> None:
        with open(self._plugin_data_path(plugin_name), 'w',
                  encoding=JSON_FILE_ENCODING) as f:
            json.dump(config, f, indent=JSON_INDENT)

    def _load_json_plugin(self, plugin_path: str) -> bool:
        plugin_data = self._read_json_plugin_file(plugin_path)
        allowed_config = self._build_allowed_config(plugin_data)
        plugin_name = allowed_config['name']
        self._persist_plugin_config(plugin_name, allowed_config)
        plugin_class = _build_json_plugin_class(allowed_config)
        self._register(plugin_name, plugin_class, PLUGIN_TYPE_JSON, plugin_path)
        return True

    # -- processing ------------------------------------------------------- #

    def process_document(self, plugin_name: str, document: Document) -> Document:
        if plugin_name not in self.plugins:
            raise ValueError(f'Plugin {plugin_name} not loaded')
        plugin_class = self.plugins[plugin_name]
        plugin_instance = plugin_class()
        try:
            result = plugin_instance.process(document)
            document.processed_content = result
            document.metadata['modified'] = datetime.now()
            document.metadata['processed_by'] = plugin_name
            return document
        except Exception as e:
            document.annotations.append({
                'type': 'error',
                'plugin': plugin_name,
                'message': str(e),
                'timestamp': datetime.now(),
            })
            return document

    # -- queries / management -------------------------------------------- #

    def get_plugin_data(self, plugin_name: str) -> Dict[str, Any]:
        data_file = self._plugin_data_path(plugin_name)
        if os.path.exists(data_file):
            with open(data_file, 'r', encoding=JSON_FILE_ENCODING) as f:
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


class DocumentProcessor:

    def __init__(self):
        self.plugin_manager = PluginManager()
        self.documents = {}

    def load_plugin(self, path: str) -> bool:
        return self.plugin_manager.load_plugin(path)

    def create_document(self, content: str) -> str:
        doc_id = _sha256_hex(content)
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


# --------------------------------------------------------------------------- #
# Command-line interface
# --------------------------------------------------------------------------- #

def _print_menu() -> None:
    for line in MENU_TEXT_LINES:
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
    print('Document Processor initialized')
    handlers = {
        MENU_LOAD_PLUGIN: _handle_load_plugin,
        MENU_CREATE_DOCUMENT: _handle_create_document,
        MENU_PROCESS_DOCUMENT: _handle_process_document,
    }
    while True:
        _print_menu()
        choice = input('Select option: ').strip()
        if choice == MENU_EXIT:
            break
        handler = handlers.get(choice)
        if handler is None:
            print('Invalid option')
        else:
            handler(processor)


if __name__ == '__main__':
    main()
