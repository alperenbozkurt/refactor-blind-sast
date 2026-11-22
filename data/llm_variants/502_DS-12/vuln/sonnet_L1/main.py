import pickle
import os
import hashlib
from datetime import datetime

DEFAULT_TITLE = 'Untitled'
DEFAULT_AUTHOR = 'Unknown'
ANALYTICS_KEYS = ('processing_time', 'word_count', 'image_count')


class DocumentMetadata:
    """Holds descriptive information about a document."""

    def __init__(self):
        self.title = DEFAULT_TITLE
        self.author = DEFAULT_AUTHOR
        self.tags = []
        self.created = datetime.now()
        self.modified = datetime.now()


class DocumentProcessor:
    """Loads serialized documents, parses them and produces reports."""

    def __init__(self):
        self.cache = {}
        self.metadata = DocumentMetadata()
        self.parsed_content = None
        self.analytics = {key: 0 for key in ANALYTICS_KEYS}

    def load_serialized_document(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError('Document file not found')
        with open(file_path, 'rb') as f:
            # Note: pickle deserialization is only safe for trusted files.
            document_data = pickle.load(f)
            self._process_serialized_data(document_data)

    def _process_serialized_data(self, data):
        self._update_metadata(data)
        self.parsed_content = self._parse_content(data.get('content', ''))
        self._update_analytics(data.get('analytics', {}))

    def _update_metadata(self, data):
        self.metadata.title = data.get('title', DEFAULT_TITLE)
        self.metadata.author = data.get('author', DEFAULT_AUTHOR)
        self.metadata.tags = data.get('tags', [])
        self.metadata.modified = datetime.now()

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
        for key in ANALYTICS_KEYS:
            self.analytics[key] = analytics_data.get(key, 0)

    def _metadata_report(self):
        return {
            'title': self.metadata.title,
            'author': self.metadata.author,
            'tags': self.metadata.tags,
            'created': self.metadata.created.isoformat(),
            'modified': self.metadata.modified.isoformat(),
        }

    def _content_info(self):
        return {
            'format': self.parsed_content.get('format', 'unknown'),
            'size': len(str(self.parsed_content)),
        }

    def generate_report(self):
        return {
            'metadata': self._metadata_report(),
            'analytics': self.analytics,
            'content_info': self._content_info(),
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
    """Coordinates document processing and keeps a history of actions."""

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
