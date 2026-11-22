import hashlib
import importlib
import importlib.util
import inspect
import os
import pickle
from datetime import datetime
from typing import Dict, Any


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
    """Loads, unloads, and executes document processing plugins."""

    def __init__(self):
        self.plugins = {}
        self.loaded_plugins = {}
        self.document_cache = {}
        self.plugin_data_dir = 'plugin_data'
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
            print(f'Failed to load plugin {plugin_path}: {e}')
            return False

    def _load_python_plugin(self, plugin_path: str) -> bool:
        plugin_name = self._plugin_name_from_path(plugin_path)
        spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for _, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and getattr(obj, 'is_plugin', False):
                self.plugins[plugin_name] = obj
                self.loaded_plugins[plugin_name] = {
                    'type': 'python',
                    'path': plugin_path,
                    'loaded_at': datetime.now(),
                }
                return True
        return False

    def _load_compiled_plugin(self, plugin_path: str) -> bool:
        with open(plugin_path, 'rb') as f:
            plugin_data = pickle.load(f)
        plugin_name = plugin_data.get('name', self._plugin_name_from_path(plugin_path))
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

    def process_document(self, plugin_name: str, document: Document) -> Document:
        if plugin_name not in self.plugins:
            raise ValueError(f'Plugin {plugin_name} not loaded')
        plugin_instance = self.plugins[plugin_name]()
        try:
            document.processed_content = plugin_instance.process(document)
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

    def _plugin_data_file(self, plugin_name: str) -> str:
        return os.path.join(self.plugin_data_dir, f'{plugin_name}.pkl')

    @staticmethod
    def _plugin_name_from_path(plugin_path: str) -> str:
        return os.path.splitext(os.path.basename(plugin_path))[0]


class DocumentProcessor:
    """High-level interface for managing documents and plugins."""

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
            self.documents[doc_id] = self.plugin_manager.process_document(plugin_name, document)
            return True
        except Exception as e:
            print(f'Processing failed: {e}')
            return False

    def get_document(self, doc_id: str) -> Document:
        return self.documents.get(doc_id)


def main():
    processor = DocumentProcessor()
    print('Document Processor initialized')

    def load_plugin():
        path = input('Enter plugin path: ')
        if processor.load_plugin(path):
            print(f'Loaded plugins: {processor.plugin_manager.list_plugins()}')
        else:
            print('Failed to load plugin')

    def create_document():
        content = input('Enter document content: ')
        doc_id = processor.create_document(content)
        print(f'Created document with ID: {doc_id}')

    def process_document():
        doc_id = input('Enter document ID: ')
        plugin = input('Enter plugin name: ')
        if processor.process_document(doc_id, plugin):
            doc = processor.get_document(doc_id)
            print(f'Processed content: {doc.processed_content}')
        else:
            print('Processing failed')

    actions = {
        '1': load_plugin,
        '2': create_document,
        '3': process_document,
    }

    while True:
        print('\n1. Load plugin')
        print('2. Create document')
        print('3. Process document')
        print('4. Exit')
        choice = input('Select option: ')
        if choice == '4':
            break
        action = actions.get(choice)
        if action is None:
            print('Invalid option')
        else:
            action()


if __name__ == '__main__':
    main()
