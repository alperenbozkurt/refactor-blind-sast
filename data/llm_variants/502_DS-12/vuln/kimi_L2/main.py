"""Document Management System.

Loads serialized documents, extracts metadata, parses content, tracks
analytics, caches processed documents and records a processing history.
"""

import hashlib
import os
import pickle
from datetime import datetime

# --------------------------------------------------------------------------
# Default values
# --------------------------------------------------------------------------

DEFAULT_TITLE = 'Untitled'
DEFAULT_AUTHOR = 'Unknown'
DEFAULT_CONTENT = ''

# --------------------------------------------------------------------------
# Serialized document keys
# --------------------------------------------------------------------------

TITLE_KEY = 'title'
AUTHOR_KEY = 'author'
TAGS_KEY = 'tags'
CONTENT_KEY = 'content'
ANALYTICS_DATA_KEY = 'analytics'

# --------------------------------------------------------------------------
# Analytics keys
# --------------------------------------------------------------------------

PROCESSING_TIME_KEY = 'processing_time'
WORD_COUNT_KEY = 'word_count'
IMAGE_COUNT_KEY = 'image_count'

ANALYTICS_KEYS = (PROCESSING_TIME_KEY, WORD_COUNT_KEY, IMAGE_COUNT_KEY)

# --------------------------------------------------------------------------
# Content formats and messages
# --------------------------------------------------------------------------

FORMAT_PLAINTEXT = 'plaintext'
FORMAT_UNKNOWN = 'unknown'

ERROR_DOCUMENT_NOT_FOUND = 'Document file not found'
ERROR_INVALID_CONTENT_FORMAT = 'Invalid content format'

ACTION_PROCESS = 'process'

# --------------------------------------------------------------------------
# Command-line interface strings
# --------------------------------------------------------------------------

CLI_READY_MESSAGE = 'Document Management System ready'
CLI_PROMPT = "Enter document path (or 'quit' to exit): "
CLI_RESULT_PREFIX = 'Processing result:'
CLI_QUIT_COMMAND = 'quit'


# --------------------------------------------------------------------------
# Helper functions
# --------------------------------------------------------------------------

def _now():
    """Return the current local timestamp."""
    return datetime.now()


def _md5_checksum(text):
    """Return the MD5 hex digest of a text string."""
    return hashlib.md5(text.encode()).hexdigest()


def _default_analytics():
    """Return a fresh analytics dictionary with zeroed counters."""
    return {key: 0 for key in ANALYTICS_KEYS}


def _read_serialized_data(file_path):
    """Read and unpickle the document data stored at ``file_path``."""
    with open(file_path, 'rb') as f:
        return pickle.load(f)


def _apply_metadata(metadata, data):
    """Populate ``metadata`` from serialized ``data``."""
    metadata.title = data.get(TITLE_KEY, DEFAULT_TITLE)
    metadata.author = data.get(AUTHOR_KEY, DEFAULT_AUTHOR)
    metadata.tags = data.get(TAGS_KEY, [])
    metadata.modified = _now()


def _parse_text_content(text):
    """Build the parsed-content dictionary for plain text."""
    return {
        'text': text,
        'format': FORMAT_PLAINTEXT,
        'checksum': _md5_checksum(text),
    }


def _invalid_content_result():
    """Return the parsed-content dictionary for unsupported content."""
    return {'error': ERROR_INVALID_CONTENT_FORMAT}


def _metadata_summary(metadata):
    """Return the report-ready representation of ``metadata``."""
    return {
        'title': metadata.title,
        'author': metadata.author,
        'tags': metadata.tags,
        'created': metadata.created.isoformat(),
        'modified': metadata.modified.isoformat(),
    }


def _content_summary(parsed_content):
    """Return the report-ready summary of the parsed content."""
    return {
        'format': parsed_content.get('format', FORMAT_UNKNOWN),
        'size': len(str(parsed_content)),
    }


def _cache_entry(metadata, parsed_content):
    """Build a cache entry for the current document state."""
    return {
        'metadata': metadata,
        'parsed_content': parsed_content,
        'timestamp': _now(),
    }


def _history_entry(file_path):
    """Build a history entry for a processed document."""
    return {
        'file': file_path,
        'timestamp': _now(),
        'action': ACTION_PROCESS,
    }


def _error_result(exception):
    """Build the error dictionary returned for failed processing."""
    return {'error': str(exception)}


def _is_quit_command(user_input):
    """Return True when the user asked to exit the CLI loop."""
    return user_input.lower() == CLI_QUIT_COMMAND


# --------------------------------------------------------------------------
# Core classes
# --------------------------------------------------------------------------

class DocumentMetadata:
    """Container for a document's descriptive metadata."""

    def __init__(self):
        self.title = DEFAULT_TITLE
        self.author = DEFAULT_AUTHOR
        self.tags = []
        self.created = _now()
        self.modified = _now()


class DocumentProcessor:
    """Loads, parses, analyses and caches a single document."""

    def __init__(self):
        self.cache = {}
        self.metadata = DocumentMetadata()
        self.parsed_content = None
        self.analytics = _default_analytics()

    def load_serialized_document(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError(ERROR_DOCUMENT_NOT_FOUND)
        self._process_serialized_data(_read_serialized_data(file_path))

    def _process_serialized_data(self, data):
        _apply_metadata(self.metadata, data)
        self.parsed_content = self._parse_content(data.get(CONTENT_KEY, DEFAULT_CONTENT))
        self._update_analytics(data.get(ANALYTICS_DATA_KEY, {}))

    def _parse_content(self, content):
        if isinstance(content, str):
            return _parse_text_content(content)
        if isinstance(content, dict):
            return content
        return _invalid_content_result()

    def _update_analytics(self, analytics_data):
        for key in ANALYTICS_KEYS:
            self.analytics[key] = analytics_data.get(key, 0)

    def generate_report(self):
        return {
            'metadata': _metadata_summary(self.metadata),
            'analytics': self.analytics,
            'content_info': _content_summary(self.parsed_content),
        }

    def cache_document(self, key):
        self.cache[key] = _cache_entry(self.metadata, self.parsed_content)

    def get_cached_document(self, key):
        return self.cache.get(key)


class DocumentManagementSystem:
    """High-level facade that processes documents and tracks history."""

    def __init__(self):
        self.processor = DocumentProcessor()
        self.document_history = []

    def process_document(self, file_path):
        try:
            self.processor.load_serialized_document(file_path)
            report = self.processor.generate_report()
            self.document_history.append(_history_entry(file_path))
            return report
        except Exception as e:
            return _error_result(e)

    def get_history(self):
        return self.document_history


# --------------------------------------------------------------------------
# Command-line interface
# --------------------------------------------------------------------------

def main():
    """Run the interactive document processing loop."""
    dms = DocumentManagementSystem()
    print(CLI_READY_MESSAGE)
    while True:
        file_path = input(CLI_PROMPT)
        if _is_quit_command(file_path):
            break
        result = dms.process_document(file_path)
        print(CLI_RESULT_PREFIX, result)


if __name__ == '__main__':
    main()
