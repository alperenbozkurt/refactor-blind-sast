import pickle
import os
import hashlib
import importlib
import importlib.util
import inspect
from datetime import datetime
from typing import Dict, Any


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

PLUGIN_DATA_DIR = 'plugin_data'
PYTHON_PLUGIN_EXT = '.py'
COMPILED_PLUGIN_EXT = '.pkl'
PLUGIN_TYPE_PYTHON = 'python'
PLUGIN_TYPE_COMPILED = 'compiled'
PLUGIN_MARKER_ATTR = 'is_plugin'

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
# Small helpers
# --------------------------------------------------------------------------- #

def _now() -> datetime:
    return datetime.now()


def _md5_hex(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _name_from_path(path: str) -> str:
    """Return the file name of ``path`` without directory or extension."""
    return os.path.splitext(os.path.basename(path))[0]


# --------------------------------------------------------------------------- #
# Domain model
# --------------------------------------------------------------------------- #

class Document:

    def __init__(self, content: str):
        self.content = content
        self.metadata = {
            'created': _now(),
            'modified': _now(),
            'checksum': _md5_hex(content),
        }
        self.annotations = []
        self.processed_content = None


# --------------------------------------------------------------------------- #
# Plugin management
# --------------------------------------------------------------------------- #

class PluginManager:

    def __init__(self):
        self.plugins = {}
        self.loaded_plugins = {}
        self.document_cache = {}
        self.plugin_data_dir = PLUGIN_DATA_DIR
        os.makedirs(self.plugin_data_dir, exist_ok=True)

    # -- loading ----------------------------------------------------------- #

    def load_plugin(self, plugin_path: str) -> bool:
        try:
            if plugin_path.endswith(PYTHON_PLUGIN_EXT):
                return self._load_python_plugin(plugin_path)
            elif plugin_path.endswith(COMPILED_PLUGIN_EXT):
                return self._load_compiled_plugin(plugin_path)
            else:
                print(f'Unsupported plugin format: {plugin_path}')
                return False
        except Exception as e:
            print(f'Failed to load plugin {plugin_path}: {str(e)}')
            return False

    @staticmethod
    def _is_plugin_class(obj: Any) -> bool:
        return (
            inspect.isclass(obj)
            and hasattr(obj, PLUGIN_MARKER_ATTR)
            and obj.is_plugin
        )

    def _register_plugin(self, plugin_name: str, plugin_class: Any,
                         info: Dict[str, Any]) -> None:
        self.plugins[plugin_name] = plugin_class
        self.loaded_plugins[plugin_name] = info

    def _load_python_plugin(self, plugin_path: str) -> bool:
        plugin_name = _name_from_path(plugin_path)
        spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for (name, obj) in inspect.getmembers(module):
            if self._is_plugin_class(obj):
                self._register_plugin(plugin_name, obj, {
                    'type': PLUGIN_TYPE_PYTHON,
                    'path': plugin_path,
                    'loaded_at': _now(),
                })
                return True
        return False

    def _load_compiled_plugin(self, plugin_path: str) -> bool:
        with open(plugin_path, 'rb') as f:
            plugin_data = pickle.load(f)
        plugin_name = plugin_data.get('name', _name_from_path(plugin_path))
        if not plugin_name:
            raise ValueError('Plugin name not specified')
        self._register_plugin(plugin_name, plugin_data['plugin_class'], {
            'type': PLUGIN_TYPE_COMPILED,
            'path': plugin_path,
            'loaded_at': _now(),
            'signature': plugin_data.get('signature'),
        })
        self._write_plugin_data(plugin_name, plugin_data.get('persistent_data', {}))
        return True

    # -- persistent plugin data -------------------------------------------- #

    def _plugin_data_path(self, plugin_name: str) -> str:
        return os.path.join(self.plugin_data_dir, f'{plugin_name}{COMPILED_PLUGIN_EXT}')

    def _write_plugin_data(self, plugin_name: str, data: Any) -> None:
        with open(self._plugin_data_path(plugin_name), 'wb') as f:
            pickle.dump(data, f)

    def get_plugin_data(self, plugin_name: str) -> Dict[str, Any]:
        data_file = self._plugin_data_path(plugin_name)
        if os.path.exists(data_file):
            with open(data_file, 'rb') as f:
                return pickle.load(f)
        return {}

    # -- processing -------------------------------------------------------- #

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
            document.annotations.append({
                'type': 'error',
                'plugin': plugin_name,
                'message': str(e),
                'timestamp': _now(),
            })
            return document

    # -- inspection / unloading -------------------------------------------- #

    def list_plugins(self) -> list:
        return list(self.plugins.keys())

    def unload_plugin(self, plugin_name: str) -> bool:
        if plugin_name in self.plugins:
            del self.plugins[plugin_name]
            del self.loaded_plugins[plugin_name]
            return True
        return False


# --------------------------------------------------------------------------- #
# Document processing facade
# --------------------------------------------------------------------------- #

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


_MENU_HANDLERS = {
    MENU_LOAD_PLUGIN: _handle_load_plugin,
    MENU_CREATE_DOCUMENT: _handle_create_document,
    MENU_PROCESS_DOCUMENT: _handle_process_document,
}


def main():
    processor = DocumentProcessor()
    print('Document Processor initialized')
    while True:
        _print_menu()
        choice = input('Select option: ')
        if choice == MENU_EXIT:
            break
        handler = _MENU_HANDLERS.get(choice)
        if handler is None:
            print('Invalid option')
        else:
            handler(processor)


if __name__ == '__main__':
    main()
