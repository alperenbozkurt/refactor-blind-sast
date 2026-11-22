import os
import zipfile
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
DEFAULT_ARCHIVE_DIR = '/var/archives'
DEFAULT_DOCUMENT_STORAGE = '/var/documents'
DEFAULT_MAX_ARCHIVE_SIZE = 100 * 1024 * 1024
DEFAULT_ALLOWED_DOCUMENT_EXTENSIONS = {'.pdf', '.docx', '.txt', '.md'}

MIN_COMPRESSION_LEVEL = 0
MAX_COMPRESSION_LEVEL = 9
DEFAULT_COMPRESSION_LEVEL = 6
DEFAULT_MAX_ARCHIVE_AGE_DAYS = 30

ARCHIVE_PREFIX = 'doc_archive_'
ARCHIVE_EXTENSION = '.zip'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
class AppConfig:
    """Default application configuration values."""

    ARCHIVE_DIR = os.path.abspath(DEFAULT_ARCHIVE_DIR)
    DOCUMENT_STORAGE = os.path.abspath(DEFAULT_DOCUMENT_STORAGE)
    MAX_ARCHIVE_SIZE = DEFAULT_MAX_ARCHIVE_SIZE
    ALLOWED_DOCUMENT_EXTENSIONS = DEFAULT_ALLOWED_DOCUMENT_EXTENSIONS


app = Flask(__name__)
app.config['ARCHIVE_DIR'] = AppConfig.ARCHIVE_DIR
app.config['DOCUMENT_STORAGE'] = AppConfig.DOCUMENT_STORAGE
app.config['MAX_ARCHIVE_SIZE'] = AppConfig.MAX_ARCHIVE_SIZE
app.config['ALLOWED_DOCUMENT_EXTENSIONS'] = AppConfig.ALLOWED_DOCUMENT_EXTENSIONS


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _error_response(message, status):
    """Build a JSON error response tuple."""
    return (jsonify({'error': message}), status)


def _remove_if_exists(path):
    if os.path.exists(path):
        os.remove(path)


def _is_valid_compression_level(level):
    return MIN_COMPRESSION_LEVEL <= level <= MAX_COMPRESSION_LEVEL


def _new_archive_name():
    return f'{ARCHIVE_PREFIX}{uuid.uuid4().hex}{ARCHIVE_EXTENSION}'


# --------------------------------------------------------------------------- #
# Core service
# --------------------------------------------------------------------------- #
class DocumentArchiver:

    def __init__(self):
        os.makedirs(app.config['ARCHIVE_DIR'], exist_ok=True)
        os.makedirs(app.config['DOCUMENT_STORAGE'], exist_ok=True)

    # -- path validation ---------------------------------------------------- #
    def is_safe_path(self, base, path):
        base = os.path.abspath(base)
        path = os.path.abspath(path)
        return path.startswith(base + os.sep)

    def _has_allowed_extension(self, path):
        return any((path.lower().endswith(ext)
                    for ext in app.config['ALLOWED_DOCUMENT_EXTENSIONS']))

    def is_allowed_document(self, path):
        if not self.is_safe_path(app.config['DOCUMENT_STORAGE'], path):
            return False
        if not os.path.exists(path):
            return False
        if os.path.isdir(path):
            return True
        return self._has_allowed_extension(path)

    # -- archive creation --------------------------------------------------- #
    def _add_file(self, zipf, doc_path):
        zipf.write(doc_path, secure_filename(os.path.basename(doc_path)))

    def _add_directory(self, zipf, doc_path):
        for (root, _, files) in os.walk(doc_path):
            for file in files:
                file_path = os.path.join(root, file)
                if self.is_allowed_document(file_path):
                    arcname = os.path.relpath(file_path, os.path.dirname(doc_path))
                    zipf.write(file_path, secure_filename(arcname))

    def _write_archive(self, archive_path, doc_path, compression_level):
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED,
                             compresslevel=compression_level) as zipf:
            if os.path.isfile(doc_path):
                self._add_file(zipf, doc_path)
            elif os.path.isdir(doc_path):
                self._add_directory(zipf, doc_path)

    def archive_document(self, doc_path, compression_level=DEFAULT_COMPRESSION_LEVEL):
        if not _is_valid_compression_level(compression_level):
            return None
        if not isinstance(doc_path, str) or not self.is_allowed_document(doc_path):
            return None
        archive_path = os.path.join(app.config['ARCHIVE_DIR'], _new_archive_name())
        try:
            self._write_archive(archive_path, doc_path, compression_level)
            if os.path.getsize(archive_path) > app.config['MAX_ARCHIVE_SIZE']:
                os.remove(archive_path)
                return None
            return archive_path
        except Exception as e:
            app.logger.error(f'Archive failed: {e}')
            _remove_if_exists(archive_path)
            return None

    # -- cleanup ------------------------------------------------------------ #
    def _is_archive_file(self, archive, archive_path):
        return os.path.isfile(archive_path) and archive.endswith(ARCHIVE_EXTENSION)

    def _is_expired(self, archive_path, now, max_age_days):
        mtime = datetime.fromtimestamp(os.path.getmtime(archive_path))
        return (now - mtime).days > max_age_days

    def cleanup_old_archives(self, max_age_days=DEFAULT_MAX_ARCHIVE_AGE_DAYS):
        now = datetime.now()
        for archive in os.listdir(app.config['ARCHIVE_DIR']):
            archive_path = os.path.join(app.config['ARCHIVE_DIR'], archive)
            if self._is_archive_file(archive, archive_path):
                if not self.is_safe_path(app.config['ARCHIVE_DIR'], archive_path):
                    continue
                try:
                    if self._is_expired(archive_path, now, max_age_days):
                        os.remove(archive_path)
                except Exception as e:
                    app.logger.error(f'Failed to remove old archive: {e}')


archiver = DocumentArchiver()


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/archive', methods=['POST'])
def create_archive():
    data = request.get_json()
    if not data or 'document_path' not in data:
        return _error_response('Invalid request', 400)
    if not isinstance(data['document_path'], str):
        return _error_response('Invalid document path', 400)
    compression = data.get('compression_level', DEFAULT_COMPRESSION_LEVEL)
    archive_path = archiver.archive_document(data['document_path'], compression)
    if archive_path:
        return (jsonify({'status': 'success',
                         'archive_path': os.path.basename(archive_path)}), 201)
    else:
        return _error_response('Archive creation failed', 500)


@app.route('/archive/<archive_name>')
def download_archive(archive_name):
    if not archive_name.endswith(ARCHIVE_EXTENSION) or '../' in archive_name:
        return _error_response('Invalid archive name', 400)
    archive_path = os.path.join(app.config['ARCHIVE_DIR'], archive_name)
    if not archiver.is_safe_path(app.config['ARCHIVE_DIR'], archive_path):
        return _error_response('Access denied', 403)
    if not os.path.exists(archive_path):
        return _error_response('Archive not found', 404)
    try:
        return send_file(archive_path, as_attachment=True)
    except Exception as e:
        app.logger.error(f'Download error: {e}')
        return _error_response('Internal server error', 500)


@app.route('/documents', methods=['GET'])
def list_documents():
    try:
        docs = []
        for (root, _, files) in os.walk(app.config['DOCUMENT_STORAGE']):
            for file in files:
                file_path = os.path.join(root, file)
                if archiver.is_allowed_document(file_path):
                    docs.append(os.path.relpath(file_path, app.config['DOCUMENT_STORAGE']))
        return jsonify({'documents': docs})
    except Exception as e:
        app.logger.error(f'Document list error: {e}')
        return _error_response('Internal server error', 500)


@app.route('/cleanup', methods=['POST'])
def cleanup_archives():
    try:
        archiver.cleanup_old_archives()
        return jsonify({'status': 'success'})
    except Exception as e:
        app.logger.error(f'Cleanup error: {e}')
        return _error_response('Internal server error', 500)


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT)
