"""Document management module.

Provides tools for modelling document metadata, loading and processing
serialized JSON documents, caching processed results and driving a simple
command-line document management system.
"""

import hashlib
import json
import os
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DEFAULT_TITLE = 'Untitled'
DEFAULT_AUTHOR = 'Unknown'
DEFAULT_CONTENT_FORMAT = 'plaintext'
UNKNOWN_CONTENT_FORMAT = 'unknown'
SUPPORTED_DOCUMENT_EXTENSION = '.json'

ERROR_DOCUMENT_NOT_FOUND = 'Document file not found'
ERROR_UNSUPPORTED_DOCUMENT = 'Only JSON documents are supported'
ERROR_INVALID_DOCUMENT_DATA = 'Document data must be a dictionary'
ERROR_INVALID_CONTENT_FORMAT = 'Invalid content format'

ACTION_PROCESS = 'process'

CLI_READY_MESSAGE = 'Document Management System ready'
CLI_PROMPT = "Enter document path (or 'quit' to exit): "
CLI_QUIT_COMMAND = 'quit'
CLI_EMPTY_PATH_ERROR = 'Error: No file path provided'
CLI_RESULT_PREFIX = 'Processing result:'

# Analytics fields paired with the callable used to coerce their values.
# The order is significant: it determines the order in which fields are
# updated, which is observable if coercion of a later field fails.
ANALYTICS_FIELD_CONVERTERS = (
    ('processing_time', float),
    ('word_count', int),
    ('image_count', int),
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _now():
    """Return the current local date and time."""
    return datetime.now()


def _default_analytics():
    """Return a fresh analytics mapping with zeroed counters."""
    return {field: 0 for field, _ in ANALYTICS_FIELD_CONVERTERS}


def _compute_checksum(text):
    """Return the MD5 hex digest of *text*."""
    return hashlib.md5(text.encode()).hexdigest()


def _extract_tags(raw_tags):
    """Normalise raw tag data into a list of strings."""
    if isinstance(raw_tags, list):
        return [str(tag) for tag in raw_tags]
    return []


def _build_content_payload(text, content_format):
    """Build the parsed-content payload for a piece of text."""
    return {
        'text': text,
        'format': content_format,
        'checksum': _compute_checksum(text),
    }


# ---------------------------------------------------------------------------
# Core classes
# ---------------------------------------------------------------------------

class DocumentMetadata:
    """Descriptive metadata associated with a document."""

    def __init__(self):
        self.title = DEFAULT_TITLE
        self.author = DEFAULT_AUTHOR
        self.tags = []
        self.created = _now()
        self.modified = _now()


class DocumentProcessor:
    """Loads, parses, analyses and caches serialized documents."""

    def __init__(self):
        self.cache = {}
        self.metadata = DocumentMetadata()
        self.parsed_content = None
        self.analytics = _default_analytics()

    def load_serialized_document(self, file_path):
        self._validate_document_path(file_path)
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                document_data = json.load(f)
                self._process_document_data(document_data)
            except json.JSONDecodeError as e:
                raise ValueError(f'Invalid JSON document: {str(e)}')

    @staticmethod
    def _validate_document_path(file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError(ERROR_DOCUMENT_NOT_FOUND)
        if not file_path.endswith(SUPPORTED_DOCUMENT_EXTENSION):
            raise ValueError(ERROR_UNSUPPORTED_DOCUMENT)

    def _process_document_data(self, data):
        if not isinstance(data, dict):
            raise ValueError(ERROR_INVALID_DOCUMENT_DATA)
        self._apply_metadata(data)
        content = data.get('content', '')
        self.parsed_content = self._parse_content(content)
        analytics = data.get('analytics', {})
        if isinstance(analytics, dict):
            self._update_analytics(analytics)

    def _apply_metadata(self, data):
        self.metadata.title = str(data.get('title', DEFAULT_TITLE))
        self.metadata.author = str(data.get('author', DEFAULT_AUTHOR))
        self.metadata.tags = _extract_tags(data.get('tags', []))
        self.metadata.modified = _now()

    def _parse_content(self, content):
        if isinstance(content, str):
            return _build_content_payload(content, DEFAULT_CONTENT_FORMAT)
        elif isinstance(content, dict):
            if 'text' in content and isinstance(content['text'], str):
                return _build_content_payload(
                    content['text'],
                    content.get('format', DEFAULT_CONTENT_FORMAT),
                )
        return {'error': ERROR_INVALID_CONTENT_FORMAT}

    def _update_analytics(self, analytics_data):
        try:
            for field, converter in ANALYTICS_FIELD_CONVERTERS:
                self.analytics[field] = converter(analytics_data.get(field, 0))
        except (ValueError, TypeError):
            pass

    def generate_report(self):
        return {
            'metadata': self._serialize_metadata(),
            'analytics': self.analytics,
            'content_info': self._describe_content(),
        }

    def _serialize_metadata(self):
        return {
            'title': self.metadata.title,
            'author': self.metadata.author,
            'tags': self.metadata.tags,
            'created': self.metadata.created.isoformat(),
            'modified': self.metadata.modified.isoformat(),
        }

    def _describe_content(self):
        return {
            'format': self.parsed_content.get('format', UNKNOWN_CONTENT_FORMAT),
            'size': len(str(self.parsed_content)),
        }

    def cache_document(self, key):
        self.cache[key] = {
            'metadata': self.metadata,
            'parsed_content': self.parsed_content,
            'timestamp': _now(),
        }

    def get_cached_document(self, key):
        return self.cache.get(key)


class DocumentManagementSystem:
    """High-level facade coordinating document processing and history."""

    def __init__(self):
        self.processor = DocumentProcessor()
        self.document_history = []

    def process_document(self, file_path):
        try:
            self.processor.load_serialized_document(file_path)
            report = self.processor.generate_report()
            self._record_action(file_path, ACTION_PROCESS)
            return report
        except Exception as e:
            return {'error': str(e)}

    def _record_action(self, file_path, action):
        self.document_history.append({
            'file': file_path,
            'timestamp': _now(),
            'action': action,
        })

    def get_history(self):
        return self.document_history


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def main():
    dms = DocumentManagementSystem()
    print(CLI_READY_MESSAGE)
    while True:
        file_path = input(CLI_PROMPT).strip()
        if file_path.lower() == CLI_QUIT_COMMAND:
            break
        if not file_path:
            print(CLI_EMPTY_PATH_ERROR)
            continue
        result = dms.process_document(file_path)
        print(CLI_RESULT_PREFIX, result)


if __name__ == '__main__':
    main()
