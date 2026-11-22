"""Simple archive upload, extraction and download service."""

import os
import tarfile
import zipfile

from flask import Flask, jsonify, render_template, request, send_file

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/var/archive_uploads'
app.config['EXTRACT_FOLDER'] = '/var/archive_contents'
app.config['ALLOWED_EXTENSIONS'] = {'zip', 'tar', 'gz', 'bz2'}


def allowed_file(filename):
    """Check whether *filename* has an allowed archive extension."""
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']
    )


def _error_response(message, status_code):
    """Build a JSON error response tuple."""
    return jsonify({'error': message}), status_code


def _extract_into(full_archive_path, extract_dir):
    """Extract a zip or tar archive into *extract_dir*.

    Return True when the archive was extracted, False when its
    format is not supported.
    """
    if zipfile.is_zipfile(full_archive_path):
        with zipfile.ZipFile(full_archive_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        return True
    if tarfile.is_tarfile(full_archive_path):
        with tarfile.open(full_archive_path) as tar_ref:
            tar_ref.extractall(extract_dir)
        return True
    return False


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

    if file and allowed_file(file.filename):
        filename = file.filename
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)
        return jsonify({'message': 'File uploaded successfully', 'path': save_path})

    return _error_response('File type not allowed', 400)


@app.route('/extract', methods=['POST'])
def extract_archive():
    """Extract a previously uploaded archive into the extract folder."""
    data = request.get_json()
    if not data or 'archive_path' not in data:
        return _error_response('No archive path provided', 400)

    archive_path = data['archive_path']
    try:
        full_archive_path = os.path.join(app.config['UPLOAD_FOLDER'], archive_path)
        if not os.path.exists(full_archive_path):
            return _error_response('Archive not found', 404)

        archive_name = os.path.splitext(os.path.basename(archive_path))[0]
        extract_dir = os.path.join(app.config['EXTRACT_FOLDER'], archive_name)
        os.makedirs(extract_dir, exist_ok=True)

        if not _extract_into(full_archive_path, extract_dir):
            return _error_response('Unsupported archive format', 400)

        return jsonify({
            'message': 'Archive extracted successfully',
            'extract_path': extract_dir,
        })
    except Exception as e:
        return _error_response(str(e), 500)


@app.route('/download')
def download_file():
    """Send an extracted file back to the client as an attachment."""
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


if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['EXTRACT_FOLDER'], exist_ok=True)

    sample_zips = ['docs.zip', 'backup.tar.gz']
    for archive in sample_zips:
        path = os.path.join(app.config['UPLOAD_FOLDER'], archive)
        if not os.path.exists(path):
            with open(path, 'wb'):
                pass

    app.run(host='0.0.0.0', port=8000)
