import hashlib
import io
import os
import pickle
from datetime import datetime

DEFAULT_TITLE = 'Untitled'
DEFAULT_AUTHOR = 'Unknown'

# Only plain data types are allowed when unpickling. Anything else (for
# example arbitrary callables) is rejected, so a crafted file cannot execute
# code while it is being loaded.
_SAFE_GLOBALS = {
    ('builtins', 'set'),
    ('builtins', 'frozenset'),
    ('builtins', 'complex'),
    ('builtins', 'bytearray'),
    ('datetime', 'datetime'),
    ('datetime', 'date'),
    ('datetime', 'time'),
    ('datetime', 'timedelta'),
}


class _RestrictedUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) in _SAFE_GLOBALS:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f'Forbidden global: {module}.{name}')


class DocumentMetadata:

    def __init__(self):
        self.title = DEFAULT_TITLE
        self.author = DEFAULT_AUTHOR
        self.tags = []
        self.created = datetime.now()
        self.modified = datetime.now()


class DocumentProcessor:

    def __init__(self):
        self.cache = {}
        self.metadata = DocumentMetadata()
        self.parsed_content = None
        self.analytics = {'processing_time': 0, 'word_count': 0, 'image_count': 0}

    def load_serialized_document(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError('Document file not found')
        with open(file_path, 'rb') as f:
            document_data = _RestrictedUnpickler(f).load()
            self._process_serialized_data(document_data)

    def _process_serialized_data(self, data):
        self.metadata.title = data.get('title', DEFAULT_TITLE)
        self.metadata.author = data.get('author', DEFAULT_AUTHOR)
        self.metadata.tags = data.get('tags', [])
        self.metadata.modified = datetime.now()
        self.parsed_content = self._parse_content(data.get('content', ''))
        self._update_analytics(data.get('analytics', {}))

    def _parse_content(self, content):
        if isinstance(content, str):
            return {
                'text': content,
                'format': 'plaintext',
                'checksum': hashlib.md5(content.encode()).hexdigest(),
            }
        if isinstance(content, dict):
            return content
        return {'error': 'Invalid content format'}

    def _update_analytics(self, analytics_data):
        for key in ('processing_time', 'word_count', 'image_count'):
            self.analytics[key] = analytics_data.get(key, 0)

    def generate_report(self):
        meta = self.metadata
        return {
            'metadata': {
                'title': meta.title,
                'author': meta.author,
                'tags': meta.tags,
                'created': meta.created.isoformat(),
                'modified': meta.modified.isoformat(),
            },
            'analytics': self.analytics,
            'content_info': {
                'format': self.parsed_content.get('format', 'unknown'),
                'size': len(str(self.parsed_content)),
            },
        }

    def cache_document(self, key):
        self.cache[key] = {
            'metadata': self.metadata,
            'parsed_content': self.parsed_content,
            'timestamp': datetime.now(),
        }

    def get_cached_document(self, key):
        return self.cache.get(key)


class DocumentManagementSystem:

    def __init__(self):
        self.processor = DocumentProcessor()
        self.document_history = []

    def process_document(self, file_path):
        try:
            self.processor.load_serialized_document(file_path)
            report = self.processor.generate_report()
            self.document_history.append({
                'file': file_path,
                'timestamp': datetime.now(),
                'action': 'process',
            })
            return report
        except Exception as e:
            return {'error': str(e)}

    def get_history(self):
        return self.document_history


def main():
    dms = DocumentManagementSystem()
    print('Document Management System ready')
    while True:
        file_path = input("Enter document path (or 'quit' to exit): ")
        if file_path.lower() == 'quit':
            break
        result = dms.process_document(file_path)
        print('Processing result:', result)


if __name__ == '__main__':
    main()
