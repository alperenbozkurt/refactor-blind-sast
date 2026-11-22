import json
import os
import hashlib
from datetime import datetime

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SUPPORTED_EXTENSION = '.json'

DEFAULT_TITLE = 'Untitled'
DEFAULT_AUTHOR = 'Unknown'
DEFAULT_CONTENT_FORMAT = 'plaintext'
UNKNOWN_FORMAT = 'unknown'

ACTION_PROCESS = 'process'
QUIT_COMMAND = 'quit'
PROMPT = "Enter document path (or 'quit' to exit): "

ERR_FILE_NOT_FOUND = 'Document file not found'
ERR_UNSUPPORTED_TYPE = 'Only JSON documents are supported'
ERR_INVALID_JSON = 'Invalid JSON document: {}'
ERR_DATA_NOT_DICT = 'Document data must be a dictionary'
ERR_INVALID_CONTENT = 'Invalid content format'
ERR_NO_PATH = 'Error: No file path provided'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _compute_checksum(text):
    """Return the MD5 hex digest of the given text."""
    return hashlib.md5(text.encode()).hexdigest()


def _default_analytics():
    return {'processing_time': 0, 'word_count': 0, 'image_count': 0}


def _normalize_tags(tags):
    """Convert a raw tags value into a list of strings (or an empty list)."""
    if isinstance(tags, list):
        return [str(tag) for tag in tags]
    return []


def _build_parsed_content(text, content_format):
    return {
        'text': text,
        'format': content_format,
        'checksum': _compute_checksum(text),
    }


# ---------------------------------------------------------------------------
# Domain classes
# ---------------------------------------------------------------------------
class DocumentMetadata:

    def __init__(self):
        self.title = DEFAULT_TITLE
        self.author = DEFAULT_AUTHOR
        self.tags = []
        self.created = datetime.now()
        self.modified = datetime.now()

    def to_report(self):
        return {
            'title': self.title,
            'author': self.author,
            'tags': self.tags,
            'created': self.created.isoformat(),
            'modified': self.modified.isoformat(),
        }


class DocumentProcessor:

    def __init__(self):
        self.cache = {}
        self.metadata = DocumentMetadata()
        self.parsed_content = None
        self.analytics = _default_analytics()

    # -- loading -----------------------------------------------------------
    def load_serialized_document(self, file_path):
        self._validate_path(file_path)
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                document_data = json.load(f)
                self._process_document_data(document_data)
            except json.JSONDecodeError as e:
                raise ValueError(ERR_INVALID_JSON.format(str(e)))

    @staticmethod
    def _validate_path(file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError(ERR_FILE_NOT_FOUND)
        if not file_path.endswith(SUPPORTED_EXTENSION):
            raise ValueError(ERR_UNSUPPORTED_TYPE)

    # -- processing --------------------------------------------------------
    def _process_document_data(self, data):
        if not isinstance(data, dict):
            raise ValueError(ERR_DATA_NOT_DICT)
        self._update_metadata(data)
        self.parsed_content = self._parse_content(data.get('content', ''))
        analytics = data.get('analytics', {})
        if isinstance(analytics, dict):
            self._update_analytics(analytics)

    def _update_metadata(self, data):
        self.metadata.title = str(data.get('title', DEFAULT_TITLE))
        self.metadata.author = str(data.get('author', DEFAULT_AUTHOR))
        self.metadata.tags = _normalize_tags(data.get('tags', []))
        self.metadata.modified = datetime.now()

    def _parse_content(self, content):
        if isinstance(content, str):
            return _build_parsed_content(content, DEFAULT_CONTENT_FORMAT)
        elif isinstance(content, dict):
            if 'text' in content and isinstance(content['text'], str):
                return _build_parsed_content(
                    content['text'],
                    content.get('format', DEFAULT_CONTENT_FORMAT),
                )
        return {'error': ERR_INVALID_CONTENT}

    def _update_analytics(self, analytics_data):
        try:
            self.analytics['processing_time'] = float(analytics_data.get('processing_time', 0))
            self.analytics['word_count'] = int(analytics_data.get('word_count', 0))
            self.analytics['image_count'] = int(analytics_data.get('image_count', 0))
        except (ValueError, TypeError):
            pass

    # -- reporting ---------------------------------------------------------
    def generate_report(self):
        return {
            'metadata': self.metadata.to_report(),
            'analytics': self.analytics,
            'content_info': self._content_info(),
        }

    def _content_info(self):
        return {
            'format': self.parsed_content.get('format', UNKNOWN_FORMAT),
            'size': len(str(self.parsed_content)),
        }

    # -- caching -----------------------------------------------------------
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
            self._record_history(file_path, ACTION_PROCESS)
            return report
        except Exception as e:
            return {'error': str(e)}

    def _record_history(self, file_path, action):
        self.document_history.append({
            'file': file_path,
            'timestamp': datetime.now(),
            'action': action,
        })

    def get_history(self):
        return self.document_history


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    dms = DocumentManagementSystem()
    print('Document Management System ready')
    while True:
        file_path = input(PROMPT).strip()
        if file_path.lower() == QUIT_COMMAND:
            break
        if not file_path:
            print(ERR_NO_PATH)
            continue
        result = dms.process_document(file_path)
        print('Processing result:', result)


if __name__ == '__main__':
    main()
