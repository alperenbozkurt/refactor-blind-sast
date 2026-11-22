import os
import tarfile
import zipfile

from flask import Flask, request, jsonify, send_file, render_template

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/var/archive_uploads'
app.config['EXTRACT_FOLDER'] = '/var/archive_contents'
app.config['ALLOWED_EXTENSIONS'] = {'zip', 'tar', 'gz', 'bz2'}

SAMPLE_ARCHIVES = ['docs.zip', 'backup.tar.gz']


def _error(message, status):
    return jsonify({'error': message}), status


def allowed_file(filename):
    if '.' not in filename:
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in app.config['ALLOWED_EXTENSIONS']


def _extract_to(archive_file, destination):
    """Extract the archive into destination. Return False if the format is unsupported."""
    if zipfile.is_zipfile(archive_file):
        with zipfile.ZipFile(archive_file, 'r') as zip_ref:
            zip_ref.extractall(destination)
        return True
    if tarfile.is_tarfile(archive_file):
        with tarfile.open(archive_file) as tar_ref:
            tar_ref.extractall(destination)
        return True
    return False


@app.route('/')
def index():
    return render_template('upload.html')


@app.route('/upload', methods=['POST'])
def upload_archive():
    if 'file' not in request.files:
        return _error('No file part', 400)

    file = request.files['file']
    if file.filename == '':
        return _error('No selected file', 400)

    if file and allowed_file(file.filename):
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(save_path)
        return jsonify({'message': 'File uploaded successfully', 'path': save_path})

    return _error('File type not allowed', 400)


@app.route('/extract', methods=['POST'])
def extract_archive():
    data = request.get_json()
    if not data or 'archive_path' not in data:
        return _error('No archive path provided', 400)

    archive_path = data['archive_path']
    try:
        full_archive_path = os.path.join(app.config['UPLOAD_FOLDER'], archive_path)
        if not os.path.exists(full_archive_path):
            return _error('Archive not found', 404)

        archive_name = os.path.splitext(os.path.basename(archive_path))[0]
        extract_dir = os.path.join(app.config['EXTRACT_FOLDER'], archive_name)
        os.makedirs(extract_dir, exist_ok=True)

        if not _extract_to(full_archive_path, extract_dir):
            return _error('Unsupported archive format', 400)

        return jsonify({
            'message': 'Archive extracted successfully',
            'extract_path': extract_dir,
        })
    except Exception as e:
        return _error(str(e), 500)


@app.route('/download')
def download_file():
    file_path = request.args.get('path')
    if not file_path:
        return _error('No file path provided', 400)

    try:
        full_path = os.path.join(app.config['EXTRACT_FOLDER'], file_path)
        if not os.path.exists(full_path):
            return _error('File not found', 404)
        if not os.path.isfile(full_path):
            return _error('Path is not a file', 400)
        return send_file(full_path, as_attachment=True)
    except Exception as e:
        return _error(str(e), 500)


def _prepare_environment():
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['EXTRACT_FOLDER'], exist_ok=True)
    for archive in SAMPLE_ARCHIVES:
        path = os.path.join(app.config['UPLOAD_FOLDER'], archive)
        if not os.path.exists(path):
            open(path, 'wb').close()


if __name__ == '__main__':
    _prepare_environment()
    app.run(host='0.0.0.0', port=8000)
