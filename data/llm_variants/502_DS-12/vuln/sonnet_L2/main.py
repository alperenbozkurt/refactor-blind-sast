import pickle
import os
import hashlib
from datetime import datetime

# --- Constants ---------------------------------------------------------------

DEFAULT_TITLE = 'Untitled'
DEFAULT_AUTHOR = 'Unknown'
DEFAULT_CONTENT = ''
DEFAULT_FORMAT = 'unknown'
PLAINTEXT_FORMAT = 'plaintext'

ANALYTICS_FIELDS = ('processing_time', 'word_count', 'image_count')
DEFAULT_ANALYTICS_VALUE = 0

ERROR_FILE_NOT_FOUND = 'Document file not found'
ERROR_INVALID_CONTENT = 'Invalid content format'

ACTION_PROCESS = 'process'
QUIT_COMMAND = 'quit'
PROMPT = "Enter document path (or 'quit' to exit): "
READY_MESSAGE = 'Document Management System ready'
RESULT_LABEL = 'Processing result:'


# --- Helpers -----------------------------------------------------------------

def _now():
    return datetime.now()


def _new_analytics():
    return {field: DEFAULT_ANALYTICS_VALUE for field in ANALYTICS_FIELDS}


def _compute_checksum(text):
    return hashlib.md5(text.encode()).hexdigest()


# --- Domain classes ----------------------------------------------------------

class DocumentMetadata:

    def __init__(self):
        self.title = DEFAULT_TITLE
        self.author = DEFAULT_AUTHOR
        self.tags = []
        self.created = _now()
        self.modified = _now()

    def to_dict(self):
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
        self.analytics = _new_analytics()

    # -- Loading --

    def load_serialized_document(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError(ERROR_FILE_NOT_FOUND)
        with open(file_path, 'rb') as f:
            document_data = pickle.load(f)
            self._process_serialized_data(document_data)

    def _process_serialized_data(self, data):
        self._update_metadata(data)
        content = data.get('content', DEFAULT_CONTENT)
        self.parsed_content = self._parse_content(content)
        analytics = data.get('analytics', {})
        self._update_analytics(analytics)

    def _update_metadata(self, data):
        self.metadata.title = data.get('title', DEFAULT_TITLE)
        self.metadata.author = data.get('author', DEFAULT_AUTHOR)
        self.metadata.tags = data.get('tags', [])
        self.metadata.modified = _now()

    def _parse_content(self, content):
        if isinstance(content, str):
            return {
                'text': content,
                'format': PLAINTEXT_FORMAT,
                'checksum': _compute_checksum(content),
            }
        elif isinstance(content, dict):
            return content
        return {'error': ERROR_INVALID_CONTENT}

    def _update_analytics(self, analytics_data):
        for field in ANALYTICS_FIELDS:
            self.analytics[field] = analytics_data.get(field, DEFAULT_ANALYTICS_VALUE)

    # -- Reporting --

    def generate_report(self):
        return {
            'metadata': self.metadata.to_dict(),
            'analytics': self.analytics,
            'content_info': self._content_info(),
        }

    def _content_info(self):
        return {
            'format': self.parsed_content.get('format', DEFAULT_FORMAT),
            'size': len(str(self.parsed_content)),
        }

    # -- Caching --

    def cache_document(self, key):
        self.cache[key] = {
            'metadata': self.metadata,
            'parsed_content': self.parsed_content,
            'timestamp': _now(),
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
            'timestamp': _now(),
            'action': action,
        })

    def get_history(self):
        return self.document_history


# --- CLI ---------------------------------------------------------------------

def main():
    dms = DocumentManagementSystem()
    print(READY_MESSAGE)
    while True:
        file_path = input(PROMPT)
        if file_path.lower() == QUIT_COMMAND:
            break
        result = dms.process_document(file_path)
        print(RESULT_LABEL, result)


if __name__ == '__main__':
    main()
