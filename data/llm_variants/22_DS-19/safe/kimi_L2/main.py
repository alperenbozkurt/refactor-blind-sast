"""Archive upload, extraction and download service.

A small Flask application that lets clients upload zip/tar archives,
extract them safely on the server and download the extracted files.
"""

import os
import tarfile
import zipfile
from dataclasses import dataclass

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ArchiveConfig:
    """Runtime configuration for the archive service."""

    upload_folder: str = os.path.abspath('/var/archive_uploads')
    extract_folder: str = os.path.abspath('/var/archive_contents')
    allowed_extensions: frozenset = frozenset({'zip', 'tar', 'gz', 'bz2'})
    max_content_length: int = 100 * 1024 * 1024


DEFAULT_CONFIG = ArchiveConfig()

DIRECTORY_MODE = 0o750
SAMPLE_ARCHIVE_MODE = 0o640
SAMPLE_ARCHIVES = ('docs.zip', 'backup.tar.gz')

INDEX_TEMPLATE = 'upload.html'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000


app = Flask(__name__)


def _configure_app(application, config=DEFAULT_CONFIG):
    application.config['UPLOAD_FOLDER'] = config.upload_folder
    application.config['EXTRACT_FOLDER'] = config.extract_folder
    application.config['ALLOWED_EXTENSIONS'] = set(config.allowed_extensions)
    application.config['MAX_CONTENT_LENGTH'] = config.max_content_length


_configure_app(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error_response(message, status_code):
    """Build a JSON error response tuple."""
    return jsonify({'error': message}), status_code


def allowed_file(filename):
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in app.config['ALLOWED_EXTENSIONS']


def is_safe_path(base_path, requested_path):
    base_path = os.path.abspath(base_path)
    requested_path = os.path.abspath(requested_path)
    return requested_path.startswith(base_path + os.sep)


def _resolve_secure_path(base_folder, user_path):
    """Resolve *user_path* inside *base_folder*.

    Returns a ``(secure_name, full_path)`` tuple, or ``(None, None)`` when the
    sanitised path would escape the base folder.
    """
    secure_name = secure_filename(user_path)
    full_path = os.path.join(base_folder, secure_name)
    if not is_safe_path(base_folder, full_path):
        return None, None
    return secure_name, full_path


def _validate_member_path(extract_dir, member_name, archive_format):
    member_path = os.path.abspath(os.path.join(extract_dir, member_name))
    if not is_safe_path(extract_dir, member_path):
        raise ValueError(
            f'Attempted path traversal in {archive_format} file: {member_name}'
        )


def safe_extract_zip(zip_path, extract_dir):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for member in zip_ref.infolist():
            _validate_member_path(extract_dir, member.filename, 'zip')
            zip_ref.extract(member, extract_dir)


def safe_extract_tar(tar_path, extract_dir):
    with tarfile.open(tar_path) as tar_ref:
        for member in tar_ref.getmembers():
            _validate_member_path(extract_dir, member.name, 'tar')
            tar_ref.extract(member, extract_dir)


_ARCHIVE_EXTRACTORS = (
    (zipfile.is_zipfile, safe_extract_zip),
    (tarfile.is_tarfile, safe_extract_tar),
)


def _extract_supported_archive(archive_path, extract_dir):
    """Extract *archive_path* into *extract_dir* if the format is supported."""
    for detector, extractor in _ARCHIVE_EXTRACTORS:
        if detector(archive_path):
            extractor(archive_path, extract_dir)
            return True
    return False


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template(INDEX_TEMPLATE)


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
        _, save_path = _resolve_secure_path(
            app.config['UPLOAD_FOLDER'], file.filename
        )
        if save_path is None:
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
        archive_name, full_archive_path = _resolve_secure_path(
            app.config['UPLOAD_FOLDER'], data['archive_path']
        )
        if full_archive_path is None:
            return _error_response('Invalid archive path', 400)
        if not os.path.exists(full_archive_path):
            return _error_response('Archive not found', 404)
        extract_dir_name = secure_filename(os.path.splitext(archive_name)[0])
        extract_dir = os.path.join(app.config['EXTRACT_FOLDER'], extract_dir_name)
        os.makedirs(extract_dir, mode=DIRECTORY_MODE, exist_ok=True)
        if not _extract_supported_archive(full_archive_path, extract_dir):
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
        _, full_path = _resolve_secure_path(
            app.config['EXTRACT_FOLDER'], file_path
        )
        if full_path is None:
            return _error_response('Invalid file path', 400)
        if not os.path.exists(full_path):
            return _error_response('File not found', 404)
        if not os.path.isfile(full_path):
            return _error_response('Path is not a file', 400)
        return send_file(full_path, as_attachment=True)
    except Exception as e:
        app.logger.error(f'Download error: {e}')
        return _error_response('File download failed', 500)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _ensure_directories():
    os.makedirs(app.config['UPLOAD_FOLDER'], mode=DIRECTORY_MODE, exist_ok=True)
    os.makedirs(app.config['EXTRACT_FOLDER'], mode=DIRECTORY_MODE, exist_ok=True)


def _create_sample_archives():
    for archive in SAMPLE_ARCHIVES:
        path = os.path.join(app.config['UPLOAD_FOLDER'], archive)
        if not os.path.exists(path):
            try:
                with open(path, 'wb'):
                    pass
                os.chmod(path, SAMPLE_ARCHIVE_MODE)
            except Exception as e:
                app.logger.error(f'Error creating sample archive {archive}: {e}')


def main():
    _ensure_directories()
    _create_sample_archives()
    app.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
