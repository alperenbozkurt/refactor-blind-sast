import os
import zipfile
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_file

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
DEFAULT_ARCHIVE_DIR = '/var/archives'
DEFAULT_DOCUMENT_STORAGE = '/var/documents'
DEFAULT_MAX_ARCHIVE_SIZE = 100 * 1024 * 1024

DEFAULT_COMPRESSION_LEVEL = 6
DEFAULT_MAX_AGE_DAYS = 30

ARCHIVE_NAME_PREFIX = 'doc_archive_'
ARCHIVE_NAME_SUFFIX = '.zip'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
SERVER_DEBUG = True

HTTP_OK_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_SERVER_ERROR = 500


class DefaultConfig:
    """Default application configuration values."""
    ARCHIVE_DIR = DEFAULT_ARCHIVE_DIR
    DOCUMENT_STORAGE = DEFAULT_DOCUMENT_STORAGE
    MAX_ARCHIVE_SIZE = DEFAULT_MAX_ARCHIVE_SIZE


app = Flask(__name__)
app.config['ARCHIVE_DIR'] = DefaultConfig.ARCHIVE_DIR
app.config['DOCUMENT_STORAGE'] = DefaultConfig.DOCUMENT_STORAGE
app.config['MAX_ARCHIVE_SIZE'] = DefaultConfig.MAX_ARCHIVE_SIZE


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _archive_dir():
    return app.config['ARCHIVE_DIR']


def _document_storage():
    return app.config['DOCUMENT_STORAGE']


def _max_archive_size():
    return app.config['MAX_ARCHIVE_SIZE']


def _generate_archive_name():
    return f'{ARCHIVE_NAME_PREFIX}{uuid.uuid4().hex}{ARCHIVE_NAME_SUFFIX}'


def _remove_if_exists(path):
    if os.path.exists(path):
        os.remove(path)


def _add_directory_to_zip(zipf, dir_path):
    base_dir = os.path.dirname(dir_path)
    for (root, _, files) in os.walk(dir_path):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, base_dir)
            zipf.write(file_path, arcname)


def _add_path_to_zip(zipf, doc_path):
    if os.path.isfile(doc_path):
        zipf.write(doc_path, os.path.basename(doc_path))
    elif os.path.isdir(doc_path):
        _add_directory_to_zip(zipf, doc_path)


def _is_older_than(path, max_age_days, now):
    mtime = datetime.fromtimestamp(os.path.getmtime(path))
    return (now - mtime).days > max_age_days


def _error_response(message, status):
    return (jsonify({'error': message}), status)


# --------------------------------------------------------------------------- #
# Core logic
# --------------------------------------------------------------------------- #
class DocumentArchiver:

    def __init__(self):
        os.makedirs(_archive_dir(), exist_ok=True)
        os.makedirs(_document_storage(), exist_ok=True)

    def validate_document_path(self, doc_path):
        return os.path.exists(doc_path)

    def archive_document(self, doc_path, compression_level=DEFAULT_COMPRESSION_LEVEL):
        if not self.validate_document_path(doc_path):
            return None
        archive_path = os.path.join(_archive_dir(), _generate_archive_name())
        try:
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED,
                                 compresslevel=compression_level) as zipf:
                _add_path_to_zip(zipf, doc_path)
            if os.path.getsize(archive_path) > _max_archive_size():
                os.remove(archive_path)
                return None
            return archive_path
        except Exception as e:
            print(f'Archive failed: {str(e)}')
            _remove_if_exists(archive_path)
            return None

    def cleanup_old_archives(self, max_age_days=DEFAULT_MAX_AGE_DAYS):
        now = datetime.now()
        for archive in os.listdir(_archive_dir()):
            archive_path = os.path.join(_archive_dir(), archive)
            if os.path.isfile(archive_path) and _is_older_than(archive_path, max_age_days, now):
                try:
                    os.remove(archive_path)
                except Exception as e:
                    print(f'Failed to remove old archive: {str(e)}')


archiver = DocumentArchiver()


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/archive', methods=['POST'])
def create_archive():
    data = request.get_json()
    if not data or 'document_path' not in data:
        return _error_response('Missing document_path', HTTP_BAD_REQUEST)
    compression = data.get('compression_level', DEFAULT_COMPRESSION_LEVEL)
    archive_path = archiver.archive_document(data['document_path'], compression)
    if archive_path:
        return (jsonify({'status': 'success',
                         'archive_path': os.path.basename(archive_path)}),
                HTTP_OK_CREATED)
    else:
        return _error_response('Archive creation failed', HTTP_SERVER_ERROR)


@app.route('/archive/<archive_name>', methods=['GET'])
def download_archive(archive_name):
    archive_path = os.path.join(_archive_dir(), archive_name)
    if not os.path.exists(archive_path):
        return _error_response('Archive not found', HTTP_NOT_FOUND)
    try:
        return send_file(archive_path, as_attachment=True)
    except Exception as e:
        return _error_response(str(e), HTTP_SERVER_ERROR)


def _collect_documents(storage_dir):
    docs = []
    for (root, _, files) in os.walk(storage_dir):
        for file in files:
            docs.append(os.path.relpath(os.path.join(root, file), storage_dir))
    return docs


@app.route('/documents', methods=['GET'])
def list_documents():
    try:
        docs = _collect_documents(_document_storage())
        return jsonify({'documents': docs})
    except Exception as e:
        return _error_response(str(e), HTTP_SERVER_ERROR)


@app.route('/cleanup', methods=['POST'])
def cleanup_archives():
    try:
        archiver.cleanup_old_archives()
        return jsonify({'status': 'success'})
    except Exception as e:
        return _error_response(str(e), HTTP_SERVER_ERROR)


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)
