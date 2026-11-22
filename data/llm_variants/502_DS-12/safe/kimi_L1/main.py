"""Document management system for loading, parsing and reporting documents."""

import hashlib
import json
import os
from datetime import datetime


class DocumentMetadata:
    """Metadata describing a document."""

    def __init__(self):
        self.title = 'Untitled'
        self.author = 'Unknown'
        self.tags = []
        self.created = datetime.now()
        self.modified = datetime.now()


class DocumentProcessor:
    """Load, parse, analyse and cache serialized documents."""

    def __init__(self):
        self.cache = {}
        self.metadata = DocumentMetadata()
        self.parsed_content = None
        self.analytics = {
            'processing_time': 0,
            'word_count': 0,
            'image_count': 0,
        }

    def load_serialized_document(self, file_path):
        """Load a JSON document from ``file_path`` and process its data."""
        if not os.path.exists(file_path):
            raise FileNotFoundError('Document file not found')
        if not file_path.endswith('.json'):
            raise ValueError('Only JSON documents are supported')

        with open(file_path, 'r', encoding='utf-8') as document_file:
            try:
                document_data = json.load(document_file)
                self._process_document_data(document_data)
            except json.JSONDecodeError as e:
                raise ValueError(f'Invalid JSON document: {e}')

    def _process_document_data(self, data):
        """Populate metadata, parsed content and analytics from raw data."""
        if not isinstance(data, dict):
            raise ValueError('Document data must be a dictionary')

        self.metadata.title = str(data.get('title', 'Untitled'))
        self.metadata.author = str(data.get('author', 'Unknown'))

        tags = data.get('tags', [])
        if isinstance(tags, list):
            self.metadata.tags = [str(tag) for tag in tags]
        else:
            self.metadata.tags = []

        self.metadata.modified = datetime.now()

        content = data.get('content', '')
        self.parsed_content = self._parse_content(content)

        analytics = data.get('analytics', {})
        if isinstance(analytics, dict):
            self._update_analytics(analytics)

    def _parse_content(self, content):
        """Normalize ``content`` into a content-info dictionary."""
        if isinstance(content, str):
            text = content
            content_format = 'plaintext'
        elif (isinstance(content, dict)
              and 'text' in content
              and isinstance(content['text'], str)):
            text = content['text']
            content_format = content.get('format', 'plaintext')
        else:
            return {'error': 'Invalid content format'}

        return {
            'text': text,
            'format': content_format,
            'checksum': hashlib.md5(text.encode()).hexdigest(),
        }

    def _update_analytics(self, analytics_data):
        """Merge known numeric analytics fields into ``self.analytics``."""
        conversions = (
            ('processing_time', float),
            ('word_count', int),
            ('image_count', int),
        )
        try:
            for key, converter in conversions:
                self.analytics[key] = converter(analytics_data.get(key, 0))
        except (ValueError, TypeError):
            pass

    def generate_report(self):
        """Build a report dictionary for the currently processed document."""
        return {
            'metadata': {
                'title': self.metadata.title,
                'author': self.metadata.author,
                'tags': self.metadata.tags,
                'created': self.metadata.created.isoformat(),
                'modified': self.metadata.modified.isoformat(),
            },
            'analytics': self.analytics,
            'content_info': {
                'format': self.parsed_content.get('format', 'unknown'),
                'size': len(str(self.parsed_content)),
            },
        }

    def cache_document(self, key):
        """Store the current document state in the cache under ``key``."""
        self.cache[key] = {
            'metadata': self.metadata,
            'parsed_content': self.parsed_content,
            'timestamp': datetime.now(),
        }

    def get_cached_document(self, key):
        """Return the cached document stored under ``key``, if any."""
        return self.cache.get(key)


class DocumentManagementSystem:
    """High-level interface for processing documents and tracking history."""

    def __init__(self):
        self.processor = DocumentProcessor()
        self.document_history = []

    def process_document(self, file_path):
        """Process the document at ``file_path`` and return a report."""
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
        """Return the recorded document processing history."""
        return self.document_history


def main():
    """Run the interactive command-line interface."""
    dms = DocumentManagementSystem()
    print('Document Management System ready')

    while True:
        file_path = input("Enter document path (or 'quit' to exit): ").strip()

        if file_path.lower() == 'quit':
            break
        if not file_path:
            print('Error: No file path provided')
            continue

        result = dms.process_document(file_path)
        print('Processing result:', result)


if __name__ == '__main__':
    main()
