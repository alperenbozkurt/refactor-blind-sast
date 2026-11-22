import os
import tarfile
import zipfile

from flask import Flask, jsonify, render_template, request, send_file

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000
SAMPLE_ARCHIVES = ('docs.zip', 'backup.tar.gz')


class Config:
    """Configuration for the archive upload service."""

    UPLOAD_FOLDER = '/var/archive_uploads'
    EXTRACT_FOLDER = '/var/archive_contents'
    ALLOWED_EXTENSIONS = {'zip', 'tar', 'gz', 'bz2'}


app = Flask(__name__)
app.config.from_object(Config)


def _error_response(message, status_code):
    """Build a JSON error response tuple."""
    return jsonify({'error': message}), status_code


def _get_extension(filename):
    """Return the lowercased extension of a filename."""
    return filename.rsplit('.', 1)[1].lower()


def allowed_file(filename):
    return '.' in filename and _get_extension(filename) in app.config['ALLOWED_EXTENSIONS']


def _upload_path(filename):
    """Resolve a filename against the upload folder."""
    return os.path.join(app.config['UPLOAD_FOLDER'], filename)


def _extraction_dir_for(archive_path):
    """Build the destination directory for extracting an archive."""
    archive_name = os.path.splitext(os.path.basename(archive_path))[0]
    return os.path.join(app.config['EXTRACT_FOLDER'], archive_name)


def _save_upload(file):
    """Persist an uploaded file and return its save path."""
    save_path = _upload_path(file.filename)
    file.save(save_path)
    return save_path


def _extract_archive(archive_file, extract_dir):
    """Extract a zip or tar archive; return False for unsupported formats."""
    if zipfile.is_zipfile(archive_file):
        with zipfile.ZipFile(archive_file, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        return True
    if tarfile.is_tarfile(archive_file):
        with tarfile.open(archive_file) as tar_ref:
            tar_ref.extractall(extract_dir)
        return True
    return False


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
    if file and allowed_file(file.filename):
        save_path = _save_upload(file)
        return jsonify({'message': 'File uploaded successfully', 'path': save_path})
    return _error_response('File type not allowed', 400)


@app.route('/extract', methods=['POST'])
def extract_archive():
    data = request.get_json()
    if not data or 'archive_path' not in data:
        return _error_response('No archive path provided', 400)
    archive_path = data['archive_path']
    try:
        full_archive_path = _upload_path(archive_path)
        if not os.path.exists(full_archive_path):
            return _error_response('Archive not found', 404)
        extract_dir = _extraction_dir_for(archive_path)
        os.makedirs(extract_dir, exist_ok=True)
        if not _extract_archive(full_archive_path, extract_dir):
            return _error_response('Unsupported archive format', 400)
        return jsonify({'message': 'Archive extracted successfully', 'extract_path': extract_dir})
    except Exception as e:
        return _error_response(str(e), 500)


@app.route('/download')
def download_file():
    file_path = request.args.get('path')
    if not file_path:
        return _error_response('No file path provided', 400)
    try:
        full_path = os.path.join(app.config['EXTRACT_FOLDER'], file_path)
        if not os.path.exists(full_path):
            return _error_response('File not found', 404)
        if not os.path.isfile(full_path):
            return _error_response('Path is not a file', 400)
        return send_file(full_path, as_attachment=True)
    except Exception as e:
        return _error_response(str(e), 500)


def _ensure_directories():
    """Create the upload and extraction directories if needed."""
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['EXTRACT_FOLDER'], exist_ok=True)


def _create_sample_archives():
    """Create empty placeholder archives for local development."""
    for archive in SAMPLE_ARCHIVES:
        path = _upload_path(archive)
        if not os.path.exists(path):
            open(path, 'wb').close()


def main():
    """Entry point: prepare local state and run the development server."""
    _ensure_directories()
    _create_sample_archives()
    app.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
