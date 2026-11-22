import os
import tarfile
import zipfile

from flask import Flask, request, jsonify, send_file, render_template
from werkzeug.utils import secure_filename

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------
DEFAULT_UPLOAD_FOLDER = '/var/archive_uploads'
DEFAULT_EXTRACT_FOLDER = '/var/archive_contents'
DEFAULT_ALLOWED_EXTENSIONS = {'zip', 'tar', 'gz', 'bz2'}
DEFAULT_MAX_CONTENT_LENGTH = 100 * 1024 * 1024

DIRECTORY_MODE = 0o750  # 488
SAMPLE_FILE_MODE = 0o640  # 416

SAMPLE_ARCHIVES = ['docs.zip', 'backup.tar.gz']

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000


# --------------------------------------------------------------------------
# Application setup
# --------------------------------------------------------------------------
class Config:
    """Default application configuration values."""

    UPLOAD_FOLDER = os.path.abspath(DEFAULT_UPLOAD_FOLDER)
    EXTRACT_FOLDER = os.path.abspath(DEFAULT_EXTRACT_FOLDER)
    ALLOWED_EXTENSIONS = DEFAULT_ALLOWED_EXTENSIONS
    MAX_CONTENT_LENGTH = DEFAULT_MAX_CONTENT_LENGTH


def _configure_app(flask_app):
    flask_app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER
    flask_app.config['EXTRACT_FOLDER'] = Config.EXTRACT_FOLDER
    flask_app.config['ALLOWED_EXTENSIONS'] = Config.ALLOWED_EXTENSIONS
    flask_app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH
    return flask_app


app = Flask(__name__)
_configure_app(app)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _error_response(message, status):
    return (jsonify({'error': message}), status)


def allowed_file(filename):
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in app.config['ALLOWED_EXTENSIONS']


def is_safe_path(base_path, requested_path):
    base_path = os.path.abspath(base_path)
    requested_path = os.path.abspath(requested_path)
    return requested_path.startswith(base_path + os.sep)


def _resolve_member_path(extract_dir, member_name):
    return os.path.abspath(os.path.join(extract_dir, member_name))


def _ensure_member_safe(extract_dir, member_name, kind):
    member_path = _resolve_member_path(extract_dir, member_name)
    if not is_safe_path(extract_dir, member_path):
        raise ValueError(f'Attempted path traversal in {kind} file: {member_name}')


def safe_extract_zip(zip_path, extract_dir):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for member in zip_ref.infolist():
            _ensure_member_safe(extract_dir, member.filename, 'zip')
            zip_ref.extract(member, extract_dir)


def safe_extract_tar(tar_path, extract_dir):
    with tarfile.open(tar_path) as tar_ref:
        for member in tar_ref.getmembers():
            _ensure_member_safe(extract_dir, member.name, 'tar')
            tar_ref.extract(member, extract_dir)


def _extract_by_format(archive_path, extract_dir):
    """Extract the archive; return False if the format is unsupported."""
    if zipfile.is_zipfile(archive_path):
        safe_extract_zip(archive_path, extract_dir)
    elif tarfile.is_tarfile(archive_path):
        safe_extract_tar(archive_path, extract_dir)
    else:
        return False
    return True


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route('/')
def index():
    return render_template('upload.html')


@app.route('/upload', methods=['POST'])
def upload_archive():
    if 'file' not in request.files:
        return _error_response('No file part', 400)
    file = request.files['file']
    if file.filename == '':
        return _error_response('No selected file', 400)
    if not allowed_file(file.filename):
        return _error_response('File type not allowed', 400)
    try:
        filename = secure_filename(file.filename)
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not is_safe_path(app.config['UPLOAD_FOLDER'], save_path):
            return _error_response('Invalid file path', 400)
        file.save(save_path)
        return jsonify({
            'message': 'File uploaded successfully',
            'path': os.path.basename(save_path),
        })
    except Exception as e:
        app.logger.error(f'Upload error: {e}')
        return _error_response('File upload failed', 500)


@app.route('/extract', methods=['POST'])
def extract_archive():
    data = request.get_json()
    if not data or 'archive_path' not in data:
        return _error_response('No archive path provided', 400)
    try:
        archive_path = secure_filename(data['archive_path'])
        full_archive_path = os.path.join(app.config['UPLOAD_FOLDER'], archive_path)
        if not is_safe_path(app.config['UPLOAD_FOLDER'], full_archive_path):
            return _error_response('Invalid archive path', 400)
        if not os.path.exists(full_archive_path):
            return _error_response('Archive not found', 404)
        extract_dir_name = secure_filename(os.path.splitext(archive_path)[0])
        extract_dir = os.path.join(app.config['EXTRACT_FOLDER'], extract_dir_name)
        os.makedirs(extract_dir, mode=DIRECTORY_MODE, exist_ok=True)
        if not _extract_by_format(full_archive_path, extract_dir):
            return _error_response('Unsupported archive format', 400)
        return jsonify({
            'message': 'Archive extracted successfully',
            'extract_path': extract_dir_name,
        })
    except ValueError:
        return _error_response('Invalid archive contents', 400)
    except Exception as e:
        app.logger.error(f'Extraction error: {e}')
        return _error_response('Archive extraction failed', 500)


@app.route('/download')
def download_file():
    file_path = request.args.get('path')
    if not file_path or not isinstance(file_path, str):
        return _error_response('Invalid file path', 400)
    try:
        safe_path = secure_filename(file_path)
        full_path = os.path.join(app.config['EXTRACT_FOLDER'], safe_path)
        if not is_safe_path(app.config['EXTRACT_FOLDER'], full_path):
            return _error_response('Invalid file path', 400)
        if not os.path.exists(full_path):
            return _error_response('File not found', 404)
        if not os.path.isfile(full_path):
            return _error_response('Path is not a file', 400)
        return send_file(full_path, as_attachment=True)
    except Exception as e:
        app.logger.error(f'Download error: {e}')
        return _error_response('File download failed', 500)


# --------------------------------------------------------------------------
# Startup helpers / CLI
# --------------------------------------------------------------------------
def _ensure_storage_directories():
    os.makedirs(app.config['UPLOAD_FOLDER'], mode=DIRECTORY_MODE, exist_ok=True)
    os.makedirs(app.config['EXTRACT_FOLDER'], mode=DIRECTORY_MODE, exist_ok=True)


def _create_sample_archive(archive):
    path = os.path.join(app.config['UPLOAD_FOLDER'], archive)
    if not os.path.exists(path):
        try:
            with open(path, 'wb'):
                pass
            os.chmod(path, SAMPLE_FILE_MODE)
        except Exception as e:
            app.logger.error(f'Error creating sample archive {archive}: {e}')


def _create_sample_archives():
    for archive in SAMPLE_ARCHIVES:
        _create_sample_archive(archive)


def main():
    _ensure_storage_directories()
    _create_sample_archives()
    app.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
