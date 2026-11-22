"""Flask application for uploading, extracting, and downloading archives."""

import os
import tarfile
import zipfile

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config.update(
    UPLOAD_FOLDER=os.path.abspath('/var/archive_uploads'),
    EXTRACT_FOLDER=os.path.abspath('/var/archive_contents'),
    ALLOWED_EXTENSIONS={'zip', 'tar', 'gz', 'bz2'},
    MAX_CONTENT_LENGTH=100 * 1024 * 1024,
)


def allowed_file(filename):
    """Return True when filename has an allowed archive extension."""
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in app.config['ALLOWED_EXTENSIONS']


def is_safe_path(base_path, requested_path):
    """Return True when requested_path resolves to a location inside base_path."""
    base_path = os.path.abspath(base_path)
    requested_path = os.path.abspath(requested_path)
    return requested_path.startswith(base_path + os.sep)


def _error_response(message, status_code):
    """Build a consistent JSON error response tuple."""
    return jsonify({'error': message}), status_code


def _secure_path_within(folder, filename):
    """Sanitize filename and resolve it inside folder.

    Returns a (sanitized_filename, full_path) tuple, or (None, None) when the
    resulting path would escape folder.
    """
    safe_name = secure_filename(filename)
    full_path = os.path.join(folder, safe_name)
    if not is_safe_path(folder, full_path):
        return None, None
    return safe_name, full_path


def _validate_member_path(extract_dir, member_name, archive_type):
    """Raise ValueError when an archive member would escape extract_dir."""
    member_path = os.path.abspath(os.path.join(extract_dir, member_name))
    if not is_safe_path(extract_dir, member_path):
        raise ValueError(
            f'Attempted path traversal in {archive_type} file: {member_name}'
        )


def safe_extract_zip(zip_path, extract_dir):
    """Extract a zip archive, rejecting members that escape extract_dir."""
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for member in zip_ref.infolist():
            _validate_member_path(extract_dir, member.filename, 'zip')
            zip_ref.extract(member, extract_dir)


def safe_extract_tar(tar_path, extract_dir):
    """Extract a tar archive, rejecting members that escape extract_dir."""
    with tarfile.open(tar_path) as tar_ref:
        for member in tar_ref.getmembers():
            _validate_member_path(extract_dir, member.name, 'tar')
            tar_ref.extract(member, extract_dir)


@app.route('/')
def index():
    """Render the archive upload page."""
    return render_template('upload.html')


@app.route('/upload', methods=['POST'])
def upload_archive():
    """Save an uploaded archive into the upload folder."""
    if 'file' not in request.files:
        return _error_response('No file part', 400)

    file = request.files['file']
    if file.filename == '':
        return _error_response('No selected file', 400)
    if not allowed_file(file.filename):
        return _error_response('File type not allowed', 400)

    try:
        _, save_path = _secure_path_within(
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
    """Extract a previously uploaded archive into the extract folder."""
    data = request.get_json()
    if not data or 'archive_path' not in data:
        return _error_response('No archive path provided', 400)

    try:
        archive_path, full_archive_path = _secure_path_within(
            app.config['UPLOAD_FOLDER'], data['archive_path']
        )
        if full_archive_path is None:
            return _error_response('Invalid archive path', 400)
        if not os.path.exists(full_archive_path):
            return _error_response('Archive not found', 404)

        extract_dir_name = secure_filename(os.path.splitext(archive_path)[0])
        extract_dir = os.path.join(app.config['EXTRACT_FOLDER'], extract_dir_name)
        os.makedirs(extract_dir, mode=0o750, exist_ok=True)

        if zipfile.is_zipfile(full_archive_path):
            safe_extract_zip(full_archive_path, extract_dir)
        elif tarfile.is_tarfile(full_archive_path):
            safe_extract_tar(full_archive_path, extract_dir)
        else:
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
    """Send a single extracted file back to the client as an attachment."""
    file_path = request.args.get('path')
    if not file_path or not isinstance(file_path, str):
        return _error_response('Invalid file path', 400)

    try:
        _, full_path = _secure_path_within(
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


if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], mode=0o750, exist_ok=True)
    os.makedirs(app.config['EXTRACT_FOLDER'], mode=0o750, exist_ok=True)

    sample_zips = ['docs.zip', 'backup.tar.gz']
    for archive in sample_zips:
        path = os.path.join(app.config['UPLOAD_FOLDER'], archive)
        if not os.path.exists(path):
            try:
                with open(path, 'wb') as f:
                    pass
                os.chmod(path, 0o640)
            except Exception as e:
                app.logger.error(f'Error creating sample archive {archive}: {e}')

    app.run(host='0.0.0.0', port=8000)
