import hashlib
import importlib
import inspect
import os
import pickle
from datetime import datetime
from typing import Any, Dict

PLUGIN_DATA_DIR = 'plugin_data'

MENU_TEXT = (
    '\n1. Load plugin\n'
    '2. Create document\n'
    '3. Process document\n'
    '4. Exit'
)


class Document:
    """A text document with metadata, annotations, and processed content."""

    def __init__(self, content: str):
        self.content = content
        self.metadata = {
            'created': datetime.now(),
            'modified': datetime.now(),
            'checksum': hashlib.md5(content.encode()).hexdigest(),
        }
        self.annotations = []
        self.processed_content = None


class PluginManager:
    """Loads plugins and uses them to process documents."""

    def __init__(self):
        self.plugins = {}
        self.loaded_plugins = {}
        self.document_cache = {}
        self.plugin_data_dir = PLUGIN_DATA_DIR
        os.makedirs(self.plugin_data_dir, exist_ok=True)

    def load_plugin(self, plugin_path: str) -> bool:
        try:
            if plugin_path.endswith('.py'):
                return self._load_python_plugin(plugin_path)
            if plugin_path.endswith('.pkl'):
                return self._load_compiled_plugin(plugin_path)
            print(f'Unsupported plugin format: {plugin_path}')
            return False
        except Exception as e:
            print(f'Failed to load plugin {plugin_path}: {str(e)}')
            return False

    def _load_python_plugin(self, plugin_path: str) -> bool:
        plugin_name = os.path.splitext(os.path.basename(plugin_path))[0]
        spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        plugin_class = self._find_plugin_class(module)
        if plugin_class is None:
            return False
        self.plugins[plugin_name] = plugin_class
        self.loaded_plugins[plugin_name] = {
            'type': 'python',
            'path': plugin_path,
            'loaded_at': datetime.now(),
        }
        return True

    @staticmethod
    def _find_plugin_class(module):
        for _, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and hasattr(obj, 'is_plugin') and obj.is_plugin:
                return obj
        return None

    def _load_compiled_plugin(self, plugin_path: str) -> bool:
        with open(plugin_path, 'rb') as f:
            plugin_data = pickle.load(f)
        plugin_name = plugin_data.get(
            'name', os.path.splitext(os.path.basename(plugin_path))[0]
        )
        if not plugin_name:
            raise ValueError('Plugin name not specified')
        self.plugins[plugin_name] = plugin_data['plugin_class']
        self.loaded_plugins[plugin_name] = {
            'type': 'compiled',
            'path': plugin_path,
            'loaded_at': datetime.now(),
            'signature': plugin_data.get('signature'),
        }
        with open(self._plugin_data_file(plugin_name), 'wb') as f:
            pickle.dump(plugin_data.get('persistent_data', {}), f)
        return True

    def _plugin_data_file(self, plugin_name: str) -> str:
        return os.path.join(self.plugin_data_dir, f'{plugin_name}.pkl')

    def process_document(self, plugin_name: str, document: Document) -> Document:
        if plugin_name not in self.plugins:
            raise ValueError(f'Plugin {plugin_name} not loaded')
        plugin_instance = self.plugins[plugin_name]()
        try:
            result = plugin_instance.process(document)
            document.processed_content = result
            document.metadata['modified'] = datetime.now()
            document.metadata['processed_by'] = plugin_name
        except Exception as e:
            document.annotations.append({
                'type': 'error',
                'plugin': plugin_name,
                'message': str(e),
                'timestamp': datetime.now(),
            })
        return document

    def get_plugin_data(self, plugin_name: str) -> Dict[str, Any]:
        data_file = self._plugin_data_file(plugin_name)
        if not os.path.exists(data_file):
            return {}
        with open(data_file, 'rb') as f:
            return pickle.load(f)

    def list_plugins(self) -> list:
        return list(self.plugins.keys())

    def unload_plugin(self, plugin_name: str) -> bool:
        if plugin_name not in self.plugins:
            return False
        del self.plugins[plugin_name]
        del self.loaded_plugins[plugin_name]
        return True


class DocumentProcessor:
    """Manages documents and coordinates their processing via plugins."""

    def __init__(self):
        self.plugin_manager = PluginManager()
        self.documents = {}

    def load_plugin(self, path: str) -> bool:
        return self.plugin_manager.load_plugin(path)

    def create_document(self, content: str) -> str:
        doc_id = hashlib.sha256(content.encode()).hexdigest()
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
        if choice == '1':
            _handle_load_plugin(processor)
        elif choice == '2':
            _handle_create_document(processor)
        elif choice == '3':
            _handle_process_document(processor)
        elif choice == '4':
            break
        else:
            print('Invalid option')


if __name__ == '__main__':
    main()
