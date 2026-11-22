"""Document processor with a pluggable architecture.

Supports Python-based and JSON-based plugins that transform documents.
"""

import hashlib
import importlib.util
import inspect
import json
import os
from datetime import datetime
from typing import Any, Dict

# Builtins exposed to dynamically loaded Python plugins.
_SAFE_BUILTINS = {
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

_MENU = (
    '\n1. Load plugin\n'
    '2. Create document\n'
    '3. Process document\n'
    '4. Exit'
)


class Document:
    """A document with content, metadata and annotations."""

    def __init__(self, content: str):
        self.content = content
        self.metadata = {
            'created': datetime.now(),
            'modified': datetime.now(),
            'checksum': hashlib.md5(content.encode()).hexdigest(),
        }
        self.annotations = []
        self.processed_content = None


def _make_json_plugin_class(config: Dict[str, Any]) -> type:
    """Create a plugin class backed by a JSON configuration."""

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


class PluginManager:
    """Loads, unloads and runs document processing plugins."""

    def __init__(self):
        self.plugins = {}
        self.loaded_plugins = {}
        self.document_cache = {}
        self.plugin_data_dir = 'plugin_data'
        os.makedirs(self.plugin_data_dir, exist_ok=True)

    def load_plugin(self, plugin_path: str) -> bool:
        try:
            if not os.path.exists(plugin_path):
                raise ValueError('Plugin file does not exist')
            if plugin_path.endswith('.py'):
                return self._load_python_plugin(plugin_path)
            if plugin_path.endswith('.json'):
                return self._load_json_plugin(plugin_path)
            print(f'Unsupported plugin format: {plugin_path}')
            return False
        except Exception as e:
            print(f'Failed to load plugin {plugin_path}: {e}')
            return False

    def _load_python_plugin(self, plugin_path: str) -> bool:
        plugin_name = os.path.splitext(os.path.basename(plugin_path))[0]
        spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
        module = importlib.util.module_from_spec(spec)
        module.__dict__['__builtins__'] = dict(_SAFE_BUILTINS)
        spec.loader.exec_module(module)
        for _, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and hasattr(obj, 'is_plugin') and obj.is_plugin:
                self._register_plugin(plugin_name, obj, 'python', plugin_path)
                return True
        return False

    def _load_json_plugin(self, plugin_path: str) -> bool:
        with open(plugin_path, 'r', encoding='utf-8') as f:
            try:
                plugin_data = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f'Invalid JSON format: {e}')

        plugin_name = plugin_data.get('name')
        if not plugin_name or not isinstance(plugin_name, str):
            raise ValueError('Plugin name must be a non-empty string')

        allowed_config = {
            'name': plugin_name,
            'version': plugin_data.get('version', '1.0'),
            'description': plugin_data.get('description', ''),
            'settings': plugin_data.get('settings', {}),
        }

        data_file = os.path.join(self.plugin_data_dir, f'{plugin_name}.json')
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(allowed_config, f, indent=2)

        plugin_class = _make_json_plugin_class(allowed_config)
        self._register_plugin(plugin_name, plugin_class, 'json', plugin_path)
        return True

    def _register_plugin(self, plugin_name: str, plugin_class: type,
                         plugin_type: str, plugin_path: str) -> None:
        self.plugins[plugin_name] = plugin_class
        self.loaded_plugins[plugin_name] = {
            'type': plugin_type,
            'path': plugin_path,
            'loaded_at': datetime.now(),
        }

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
        data_file = os.path.join(self.plugin_data_dir, f'{plugin_name}.json')
        if os.path.exists(data_file):
            with open(data_file, 'r', encoding='utf-8') as f:
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
    """High-level facade over the plugin manager and document store."""

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
            self.documents[doc_id] = self.plugin_manager.process_document(
                plugin_name, document
            )
            return True
        except Exception as e:
            print(f'Processing failed: {e}')
            return False

    def get_document(self, doc_id: str) -> Document:
        return self.documents.get(doc_id)


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
        '1': _handle_load_plugin,
        '2': _handle_create_document,
        '3': _handle_process_document,
    }
    while True:
        print(_MENU)
        choice = input('Select option: ').strip()
        if choice == '4':
            break
        handler = handlers.get(choice)
        if handler is None:
            print('Invalid option')
        else:
            handler(processor)


if __name__ == '__main__':
    main()
