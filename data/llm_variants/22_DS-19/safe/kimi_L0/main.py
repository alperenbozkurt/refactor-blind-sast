import os
import tarfile
import zipfile

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = os.path.abspath('/var/archive_uploads')
EXTRACT_FOLDER = os.path.abspath('/var/archive_contents')
ALLOWED_EXTENSIONS = {'zip', 'tar', 'gz', 'bz2'}
MAX_CONTENT_LENGTH = 100 * 1024 * 1024
DIR_MODE = 0o750
FILE_MODE = 0o640
SAMPLE_ARCHIVES = ('docs.zip', 'backup.tar.gz')

app = Flask(__name__)
app.config.update(
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    EXTRACT_FOLDER=EXTRACT_FOLDER,
    ALLOWED_EXTENSIONS=ALLOWED_EXTENSIONS,
    MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH,
)


def _error_response(message, status_code):
    return jsonify({'error': message}), status_code


def allowed_file(filename):
    if not filename or '.' not in filename:
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in app.config['ALLOWED_EXTENSIONS']


def is_safe_path(base_path, requested_path):
    base_path = os.path.abspath(base_path)
    requested_path = os.path.abspath(requested_path)
    return requested_path.startswith(base_path + os.sep)


def _ensure_safe_member_path(extract_dir, member_name, archive_type):
    member_path = os.path.abspath(os.path.join(extract_dir, member_name))
    if not is_safe_path(extract_dir, member_path):
        raise ValueError(
            f'Attempted path traversal in {archive_type} file: {member_name}'
        )


def safe_extract_zip(zip_path, extract_dir):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for member in zip_ref.infolist():
            _ensure_safe_member_path(extract_dir, member.filename, 'zip')
            zip_ref.extract(member, extract_dir)


def safe_extract_tar(tar_path, extract_dir):
    with tarfile.open(tar_path) as tar_ref:
        for member in tar_ref.getmembers():
            _ensure_safe_member_path(extract_dir, member.name, 'tar')
            tar_ref.extract(member, extract_dir)


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
        os.makedirs(extract_dir, mode=DIR_MODE, exist_ok=True)

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


def _create_sample_archives():
    for archive in SAMPLE_ARCHIVES:
        path = os.path.join(app.config['UPLOAD_FOLDER'], archive)
        if os.path.exists(path):
            continue
        try:
            with open(path, 'wb'):
                pass
            os.chmod(path, FILE_MODE)
        except Exception as e:
            app.logger.error(f'Error creating sample archive {archive}: {e}')


def main():
    os.makedirs(app.config['UPLOAD_FOLDER'], mode=DIR_MODE, exist_ok=True)
    os.makedirs(app.config['EXTRACT_FOLDER'], mode=DIR_MODE, exist_ok=True)
    _create_sample_archives()
    app.run(host='0.0.0.0', port=8000)


if __name__ == '__main__':
    main()
