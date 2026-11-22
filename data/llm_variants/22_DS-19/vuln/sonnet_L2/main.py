import os
import tarfile
import zipfile

from flask import Flask, request, jsonify, send_file, render_template


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
class Config:
    """Application configuration (uppercase attributes are loaded into Flask)."""

    UPLOAD_FOLDER = '/var/archive_uploads'
    EXTRACT_FOLDER = '/var/archive_contents'
    ALLOWED_EXTENSIONS = {'zip', 'tar', 'gz', 'bz2'}


# Server settings
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

# Files created in the upload folder on startup when missing
SAMPLE_ARCHIVES = ['docs.zip', 'backup.tar.gz']

# Template names
UPLOAD_TEMPLATE = 'upload.html'

# HTTP status codes
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_SERVER_ERROR = 500

# Messages
MSG_NO_FILE_PART = 'No file part'
MSG_NO_SELECTED_FILE = 'No selected file'
MSG_FILE_TYPE_NOT_ALLOWED = 'File type not allowed'
MSG_UPLOAD_SUCCESS = 'File uploaded successfully'
MSG_NO_ARCHIVE_PATH = 'No archive path provided'
MSG_ARCHIVE_NOT_FOUND = 'Archive not found'
MSG_UNSUPPORTED_FORMAT = 'Unsupported archive format'
MSG_EXTRACT_SUCCESS = 'Archive extracted successfully'
MSG_NO_FILE_PATH = 'No file path provided'
MSG_FILE_NOT_FOUND = 'File not found'
MSG_NOT_A_FILE = 'Path is not a file'


app = Flask(__name__)
app.config.from_object(Config)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _error_response(message, status):
    """Build a JSON error response tuple."""
    return (jsonify({'error': message}), status)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def _upload_path(name):
    return os.path.join(app.config['UPLOAD_FOLDER'], name)


def _extract_path(name):
    return os.path.join(app.config['EXTRACT_FOLDER'], name)


def _extraction_dir_for(archive_path):
    """Return the destination directory for the given archive path."""
    base_name = os.path.splitext(os.path.basename(archive_path))[0]
    return _extract_path(base_name)


def _extract_zip(archive_path, destination):
    with zipfile.ZipFile(archive_path, 'r') as zip_ref:
        zip_ref.extractall(destination)


def _extract_tar(archive_path, destination):
    with tarfile.open(archive_path) as tar_ref:
        tar_ref.extractall(destination)


def _extract_archive_file(archive_path, destination):
    """Extract an archive; return False if its format is unsupported."""
    if zipfile.is_zipfile(archive_path):
        _extract_zip(archive_path, destination)
    elif tarfile.is_tarfile(archive_path):
        _extract_tar(archive_path, destination)
    else:
        return False
    return True


def _ensure_directories():
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['EXTRACT_FOLDER'], exist_ok=True)


def _create_sample_archives():
    for archive in SAMPLE_ARCHIVES:
        path = _upload_path(archive)
        if not os.path.exists(path):
            open(path, 'wb').close()


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/')
def index():
    return render_template(UPLOAD_TEMPLATE)


@app.route('/upload', methods=['POST'])
def upload_archive():
    if 'file' not in request.files:
        return _error_response(MSG_NO_FILE_PART, HTTP_BAD_REQUEST)
    file = request.files['file']
    if file.filename == '':
        return _error_response(MSG_NO_SELECTED_FILE, HTTP_BAD_REQUEST)
    if file and allowed_file(file.filename):
        filename = file.filename
        save_path = _upload_path(filename)
        file.save(save_path)
        return jsonify({'message': MSG_UPLOAD_SUCCESS, 'path': save_path})
    return _error_response(MSG_FILE_TYPE_NOT_ALLOWED, HTTP_BAD_REQUEST)


@app.route('/extract', methods=['POST'])
def extract_archive():
    data = request.get_json()
    if not data or 'archive_path' not in data:
        return _error_response(MSG_NO_ARCHIVE_PATH, HTTP_BAD_REQUEST)
    archive_path = data['archive_path']
    try:
        full_archive_path = _upload_path(archive_path)
        if not os.path.exists(full_archive_path):
            return _error_response(MSG_ARCHIVE_NOT_FOUND, HTTP_NOT_FOUND)
        extract_dir = _extraction_dir_for(archive_path)
        os.makedirs(extract_dir, exist_ok=True)
        if not _extract_archive_file(full_archive_archive_path := full_archive_path, extract_dir):
            return _error_response(MSG_UNSUPPORTED_FORMAT, HTTP_BAD_REQUEST)
        return jsonify({'message': MSG_EXTRACT_SUCCESS, 'extract_path': extract_dir})
    except Exception as e:
        return _error_response(str(e), HTTP_SERVER_ERROR)


@app.route('/download')
def download_file():
    file_path = request.args.get('path')
    if not file_path:
        return _error_response(MSG_NO_FILE_PATH, HTTP_BAD_REQUEST)
    try:
        full_path = _extract_path(file_path)
        if not os.path.exists(full_path):
            return _error_response(MSG_FILE_NOT_FOUND, HTTP_NOT_FOUND)
        if not os.path.isfile(full_path):
            return _error_response(MSG_NOT_A_FILE, HTTP_BAD_REQUEST)
        return send_file(full_path, as_attachment=True)
    except Exception as e:
        return _error_response(str(e), HTTP_SERVER_ERROR)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main():
    _ensure_directories()
    _create_sample_archives()
    app.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
