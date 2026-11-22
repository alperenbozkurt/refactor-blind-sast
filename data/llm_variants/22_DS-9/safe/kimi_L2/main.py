"""Document archiving web service.

Exposes HTTP endpoints for creating ZIP archives of stored documents,
downloading them, listing available documents and removing old archives.
"""

import os
import uuid
import zipfile
from datetime import datetime

from flask import Flask, jsonify, request, send_file
from werkzeug.utils import secure_filename


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class ArchiveServiceConfig:
    """Configuration values loaded into the Flask application."""

    ARCHIVE_DIR = os.path.abspath('/var/archives')
    DOCUMENT_STORAGE = os.path.abspath('/var/documents')
    MAX_ARCHIVE_SIZE = 100 * 1024 * 1024  # 100 MB
    ALLOWED_DOCUMENT_EXTENSIONS = {'.pdf', '.docx', '.txt', '.md'}


# Named constants shared by the service layer and the routes.
ARCHIVE_FILE_EXTENSION = '.zip'
ARCHIVE_NAME_PREFIX = 'doc_archive_'
PATH_TRAVERSAL_TOKEN = '../'

MIN_COMPRESSION_LEVEL = 0
MAX_COMPRESSION_LEVEL = 9
DEFAULT_COMPRESSION_LEVEL = 6

DEFAULT_MAX_ARCHIVE_AGE_DAYS = 30

STATUS_SUCCESS = 'success'

ERROR_INVALID_REQUEST = 'Invalid request'
ERROR_INVALID_DOCUMENT_PATH = 'Invalid document path'
ERROR_ARCHIVE_CREATION_FAILED = 'Archive creation failed'
ERROR_INVALID_ARCHIVE_NAME = 'Invalid archive name'
ERROR_ACCESS_DENIED = 'Access denied'
ERROR_ARCHIVE_NOT_FOUND = 'Archive not found'
ERROR_INTERNAL_SERVER_ERROR = 'Internal server error'

HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000


app = Flask(__name__)
app.config.from_object(ArchiveServiceConfig)


# ---------------------------------------------------------------------------
# Small helper functions
# ---------------------------------------------------------------------------

def _is_within_directory(base, path):
    """Return True when ``path`` resolves to a location inside ``base``."""
    base = os.path.abspath(base)
    path = os.path.abspath(path)
    return path.startswith(base + os.sep)


def _error_response(message, status_code):
    """Build a JSON error response tuple."""
    return jsonify({'error': message}), status_code


def _has_archive_extension(filename):
    """Return True when ``filename`` carries the archive file extension."""
    return filename.endswith(ARCHIVE_FILE_EXTENSION)


def _collect_allowed_documents():
    """Return storage-relative paths of all allowed documents."""
    storage_dir = app.config['DOCUMENT_STORAGE']
    docs = []
    for (root, _, files) in os.walk(storage_dir):
        for file in files:
            file_path = os.path.join(root, file)
            if archiver.is_allowed_document(file_path):
                docs.append(os.path.relpath(file_path, storage_dir))
    return docs


# ---------------------------------------------------------------------------
# Archiving service
# ---------------------------------------------------------------------------

class DocumentArchiver:
    """Creates and maintains ZIP archives of stored documents."""

    def __init__(self):
        self._ensure_storage_directories()

    @staticmethod
    def _ensure_storage_directories():
        os.makedirs(app.config['ARCHIVE_DIR'], exist_ok=True)
        os.makedirs(app.config['DOCUMENT_STORAGE'], exist_ok=True)

    def is_safe_path(self, base, path):
        return _is_within_directory(base, path)

    def is_allowed_document(self, path):
        if not self.is_safe_path(app.config['DOCUMENT_STORAGE'], path):
            return False
        if not os.path.exists(path):
            return False
        if os.path.isdir(path):
            return True
        return self._has_allowed_extension(path)

    @staticmethod
    def _has_allowed_extension(path):
        allowed_extensions = app.config['ALLOWED_DOCUMENT_EXTENSIONS']
        return any(path.lower().endswith(ext) for ext in allowed_extensions)

    @staticmethod
    def _is_valid_compression_level(compression_level):
        return MIN_COMPRESSION_LEVEL <= compression_level <= MAX_COMPRESSION_LEVEL

    @staticmethod
    def _build_archive_path():
        archive_name = f'{ARCHIVE_NAME_PREFIX}{uuid.uuid4().hex}{ARCHIVE_FILE_EXTENSION}'
        return os.path.join(app.config['ARCHIVE_DIR'], archive_name)

    @staticmethod
    def _is_oversized(archive_path):
        return os.path.getsize(archive_path) > app.config['MAX_ARCHIVE_SIZE']

    def _write_archive(self, archive_path, doc_path, compression_level):
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED,
                             compresslevel=compression_level) as zipf:
            if os.path.isfile(doc_path):
                zipf.write(doc_path, secure_filename(os.path.basename(doc_path)))
            elif os.path.isdir(doc_path):
                self._write_directory(zipf, doc_path)

    def _write_directory(self, zipf, doc_path):
        for (root, _, files) in os.walk(doc_path):
            for file in files:
                file_path = os.path.join(root, file)
                if self.is_allowed_document(file_path):
                    arcname = os.path.relpath(file_path, os.path.dirname(doc_path))
                    zipf.write(file_path, secure_filename(arcname))

    def archive_document(self, doc_path, compression_level=DEFAULT_COMPRESSION_LEVEL):
        if not self._is_valid_compression_level(compression_level):
            return None
        if not isinstance(doc_path, str) or not self.is_allowed_document(doc_path):
            return None
        archive_path = self._build_archive_path()
        try:
            self._write_archive(archive_path, doc_path, compression_level)
            if self._is_oversized(archive_path):
                os.remove(archive_path)
                return None
            return archive_path
        except Exception as e:
            app.logger.error(f'Archive failed: {e}')
            if os.path.exists(archive_path):
                os.remove(archive_path)
            return None

    def cleanup_old_archives(self, max_age_days=DEFAULT_MAX_ARCHIVE_AGE_DAYS):
        now = datetime.now()
        for archive in os.listdir(app.config['ARCHIVE_DIR']):
            archive_path = os.path.join(app.config['ARCHIVE_DIR'], archive)
            if self._is_archive_file(archive_path, archive):
                self._remove_if_expired(archive_path, now, max_age_days)

    @staticmethod
    def _is_archive_file(archive_path, archive_name):
        return os.path.isfile(archive_path) and _has_archive_extension(archive_name)

    def _remove_if_expired(self, archive_path, now, max_age_days):
        if not self.is_safe_path(app.config['ARCHIVE_DIR'], archive_path):
            return
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(archive_path))
            if (now - mtime).days > max_age_days:
                os.remove(archive_path)
        except Exception as e:
            app.logger.error(f'Failed to remove old archive: {e}')


archiver = DocumentArchiver()


# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------

@app.route('/archive', methods=['POST'])
def create_archive():
    data = request.get_json()
    if not data or 'document_path' not in data:
        return _error_response(ERROR_INVALID_REQUEST, HTTP_BAD_REQUEST)
    if not isinstance(data['document_path'], str):
        return _error_response(ERROR_INVALID_DOCUMENT_PATH, HTTP_BAD_REQUEST)
    compression = data.get('compression_level', DEFAULT_COMPRESSION_LEVEL)
    archive_path = archiver.archive_document(data['document_path'], compression)
    if archive_path:
        return (jsonify({'status': STATUS_SUCCESS,
                         'archive_path': os.path.basename(archive_path)}), HTTP_CREATED)
    return _error_response(ERROR_ARCHIVE_CREATION_FAILED, HTTP_INTERNAL_SERVER_ERROR)


@app.route('/archive/<archive_name>')
def download_archive(archive_name):
    if not _has_archive_extension(archive_name) or PATH_TRAVERSAL_TOKEN in archive_name:
        return _error_response(ERROR_INVALID_ARCHIVE_NAME, HTTP_BAD_REQUEST)
    archive_path = os.path.join(app.config['ARCHIVE_DIR'], archive_name)
    if not archiver.is_safe_path(app.config['ARCHIVE_DIR'], archive_path):
        return _error_response(ERROR_ACCESS_DENIED, HTTP_FORBIDDEN)
    if not os.path.exists(archive_path):
        return _error_response(ERROR_ARCHIVE_NOT_FOUND, HTTP_NOT_FOUND)
    try:
        return send_file(archive_path, as_attachment=True)
    except Exception as e:
        app.logger.error(f'Download error: {e}')
        return _error_response(ERROR_INTERNAL_SERVER_ERROR, HTTP_INTERNAL_SERVER_ERROR)


@app.route('/documents', methods=['GET'])
def list_documents():
    try:
        return jsonify({'documents': _collect_allowed_documents()})
    except Exception as e:
        app.logger.error(f'Document list error: {e}')
        return _error_response(ERROR_INTERNAL_SERVER_ERROR, HTTP_INTERNAL_SERVER_ERROR)


@app.route('/cleanup', methods=['POST'])
def cleanup_archives():
    try:
        archiver.cleanup_old_archives()
        return jsonify({'status': STATUS_SUCCESS})
    except Exception as e:
        app.logger.error(f'Cleanup error: {e}')
        return _error_response(ERROR_INTERNAL_SERVER_ERROR, HTTP_INTERNAL_SERVER_ERROR)


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT)
