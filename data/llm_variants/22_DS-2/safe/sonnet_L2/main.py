from flask import Flask, request, send_file, abort
import os
import uuid

# --------------------------------------------------------------------------- #
# Constants / configuration
# --------------------------------------------------------------------------- #
DEFAULT_UPLOAD_FOLDER = './uploads'
DEFAULT_ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

FILE_FIELD_NAME = 'file'
EXTENSION_SEPARATOR = '.'

HOST = '0.0.0.0'
PORT = 5000
DEBUG = False

MSG_NO_FILE_PART = 'No file part'
MSG_NO_SELECTED_FILE = 'No selected file'
MSG_INVALID_FILE_TYPE = 'Invalid file type'
MSG_UPLOAD_SUCCESS = 'File uploaded successfully'
MSG_ACCESS_DENIED = 'Access denied'
MSG_NOT_A_FILE = 'Requested path is not a file'


class Config:
    """Default application configuration."""
    UPLOAD_FOLDER = DEFAULT_UPLOAD_FOLDER
    ALLOWED_EXTENSIONS = DEFAULT_ALLOWED_EXTENSIONS


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = Config.ALLOWED_EXTENSIONS


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _get_extension(filename):
    """Return the lower-cased extension of a filename (text after last dot)."""
    return filename.rsplit(EXTENSION_SEPARATOR, 1)[1].lower()


def allowed_file(filename):
    return (EXTENSION_SEPARATOR in filename
            and _get_extension(filename) in app.config['ALLOWED_EXTENSIONS'])


def _error_response(message, status):
    return ({'error': message}, status)


def _generate_unique_filename(original_filename):
    return str(uuid.uuid4()) + EXTENSION_SEPARATOR + _get_extension(original_filename)


def _is_within_directory(file_path, directory):
    return file_path.startswith(directory)


def _resolve_download_path(filename):
    upload_dir = os.path.abspath(app.config['UPLOAD_FOLDER'])
    file_path = os.path.abspath(os.path.join(upload_dir, filename))
    return upload_dir, file_path


def _validate_download_path(upload_dir, file_path, filename):
    if not _is_within_directory(file_path, upload_dir):
        abort(403, description=MSG_ACCESS_DENIED)
    if not os.path.exists(file_path):
        abort(404)
    if not os.path.isfile(file_path):
        abort(400, description=MSG_NOT_A_FILE)
    if not allowed_file(filename):
        abort(400, description=MSG_INVALID_FILE_TYPE)


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/upload', methods=['POST'])
def upload_file():
    if FILE_FIELD_NAME not in request.files:
        return _error_response(MSG_NO_FILE_PART, 400)
    file = request.files[FILE_FIELD_NAME]
    if file.filename == '':
        return _error_response(MSG_NO_SELECTED_FILE, 400)
    if file and allowed_file(file.filename):
        filename = _generate_unique_filename(file.filename)
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)
        return ({'message': MSG_UPLOAD_SUCCESS, 'filename': filename}, 200)
    return _error_response(MSG_INVALID_FILE_TYPE, 400)


@app.route('/download/<path:filename>')
def download_image(filename):
    try:
        upload_dir, file_path = _resolve_download_path(filename)
        _validate_download_path(upload_dir, file_path, filename)
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        abort(500, description=str(e))


# --------------------------------------------------------------------------- #
# Setup / entry point
# --------------------------------------------------------------------------- #
def create_upload_folder():
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])


if __name__ == '__main__':
    create_upload_folder()
    app.run(debug=DEBUG, host=HOST, port=PORT)
