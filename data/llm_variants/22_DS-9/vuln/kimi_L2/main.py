"""Document archiving service.

A small Flask application that creates zip archives of documents stored on
disk, serves those archives for download, lists the stored documents and
removes archives that have grown too old.
"""

import os
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from flask import Flask, jsonify, request, send_file

# ---------------------------------------------------------------------------
# Constants and configuration
# ---------------------------------------------------------------------------

DEFAULT_COMPRESSION_LEVEL = 6
DEFAULT_MAX_AGE_DAYS = 30

ARCHIVE_NAME_TEMPLATE = 'doc_archive_{token}.zip'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
SERVER_DEBUG = True

HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500


@dataclass(frozen=True)
class Settings:
    """Default filesystem locations and archive limits."""

    archive_dir: str = '/var/archives'
    document_storage: str = '/var/documents'
    max_archive_size: int = 100 * 1024 * 1024


settings = Settings()

app = Flask(__name__)
app.config['ARCHIVE_DIR'] = settings.archive_dir
app.config['DOCUMENT_STORAGE'] = settings.document_storage
app.config['MAX_ARCHIVE_SIZE'] = settings.max_archive_size


# ---------------------------------------------------------------------------
# Archiving
# ---------------------------------------------------------------------------

class DocumentArchiver:
    """Creates zip archives of documents and prunes outdated archives."""

    def __init__(self):
        self._ensure_storage_directories()

    @staticmethod
    def _ensure_storage_directories():
        os.makedirs(app.config['ARCHIVE_DIR'], exist_ok=True)
        os.makedirs(app.config['DOCUMENT_STORAGE'], exist_ok=True)

    def validate_document_path(self, doc_path):
        return os.path.exists(doc_path)

    def archive_document(self, doc_path, compression_level=DEFAULT_COMPRESSION_LEVEL):
        if not self.validate_document_path(doc_path):
            return None
        archive_path = os.path.join(app.config['ARCHIVE_DIR'], _new_archive_name())
        try:
            self._write_archive(doc_path, archive_path, compression_level)
            if self._exceeds_size_limit(archive_path):
                os.remove(archive_path)
                return None
            return archive_path
        except Exception as e:
            print(f'Archive failed: {str(e)}')
            if os.path.exists(archive_path):
                os.remove(archive_path)
            return None

    def _write_archive(self, doc_path, archive_path, compression_level):
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED,
                             compresslevel=compression_level) as zipf:
            if os.path.isfile(doc_path):
                zipf.write(doc_path, os.path.basename(doc_path))
            elif os.path.isdir(doc_path):
                self._write_directory(zipf, doc_path)

    @staticmethod
    def _write_directory(zipf, doc_path):
        for root, _, files in os.walk(doc_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, os.path.dirname(doc_path))
                zipf.write(file_path, arcname)

    @staticmethod
    def _exceeds_size_limit(archive_path):
        return os.path.getsize(archive_path) > app.config['MAX_ARCHIVE_SIZE']

    def cleanup_old_archives(self, max_age_days=DEFAULT_MAX_AGE_DAYS):
        now = datetime.now()
        for archive in os.listdir(app.config['ARCHIVE_DIR']):
            archive_path = os.path.join(app.config['ARCHIVE_DIR'], archive)
            if os.path.isfile(archive_path) and _is_expired(archive_path, now, max_age_days):
                self._remove_archive(archive_path)

    @staticmethod
    def _remove_archive(archive_path):
        try:
            os.remove(archive_path)
        except Exception as e:
            print(f'Failed to remove old archive: {str(e)}')


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _new_archive_name():
    """Return a unique file name for a new archive."""
    return ARCHIVE_NAME_TEMPLATE.format(token=uuid.uuid4().hex)


def _is_expired(file_path, now, max_age_days):
    """Return True when the file's mtime is older than ``max_age_days``."""
    mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
    return (now - mtime).days > max_age_days


def _collect_documents():
    """Return storage-relative paths of all documents under DOCUMENT_STORAGE."""
    storage_dir = app.config['DOCUMENT_STORAGE']
    docs = []
    for root, _, files in os.walk(storage_dir):
        for file in files:
            docs.append(os.path.relpath(os.path.join(root, file), storage_dir))
    return docs


def _error_response(message, status_code):
    """Build a JSON error response tuple."""
    return jsonify({'error': message}), status_code


archiver = DocumentArchiver()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/archive', methods=['POST'])
def create_archive():
    data = request.get_json()
    if not data or 'document_path' not in data:
        return _error_response('Missing document_path', HTTP_BAD_REQUEST)
    compression = data.get('compression_level', DEFAULT_COMPRESSION_LEVEL)
    archive_path = archiver.archive_document(data['document_path'], compression)
    if archive_path:
        return jsonify({'status': 'success',
                        'archive_path': os.path.basename(archive_path)}), HTTP_CREATED
    return _error_response('Archive creation failed', HTTP_INTERNAL_SERVER_ERROR)


@app.route('/archive/<archive_name>', methods=['GET'])
def download_archive(archive_name):
    archive_path = os.path.join(app.config['ARCHIVE_DIR'], archive_name)
    if not os.path.exists(archive_path):
        return _error_response('Archive not found', HTTP_NOT_FOUND)
    try:
        return send_file(archive_path, as_attachment=True)
    except Exception as e:
        return _error_response(str(e), HTTP_INTERNAL_SERVER_ERROR)


@app.route('/documents', methods=['GET'])
def list_documents():
    try:
        return jsonify({'documents': _collect_documents()})
    except Exception as e:
        return _error_response(str(e), HTTP_INTERNAL_SERVER_ERROR)


@app.route('/cleanup', methods=['POST'])
def cleanup_archives():
    try:
        archiver.cleanup_old_archives()
        return jsonify({'status': 'success'})
    except Exception as e:
        return _error_response(str(e), HTTP_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)


if __name__ == '__main__':
    main()
