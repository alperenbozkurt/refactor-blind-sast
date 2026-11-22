from flask import Flask, request, send_file, abort
import os
import uuid

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_UPLOAD_FOLDER = './uploads'
DEFAULT_ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

FILE_FIELD_NAME = 'file'
EXTENSION_SEPARATOR = '.'

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500

MSG_NO_FILE_PART = 'No file part'
MSG_NO_SELECTED_FILE = 'No selected file'
MSG_INVALID_FILE_TYPE = 'Invalid file type'
MSG_UPLOAD_SUCCESS = 'File uploaded successfully'
MSG_NOT_A_FILE = 'Requested path is not a file'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
SERVER_DEBUG = True

# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = DEFAULT_UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = DEFAULT_ALLOWED_EXTENSIONS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _extract_extension(filename):
    """Return the lower-cased extension following the last separator."""
    return filename.rsplit(EXTENSION_SEPARATOR, 1)[1].lower()


def _generate_unique_filename(original_filename):
    """Build a random filename preserving the original (lower-cased) extension."""
    return str(uuid.uuid4()) + EXTENSION_SEPARATOR + _extract_extension(original_filename)


def _upload_path_for(filename):
    """Resolve a filename against the configured upload folder."""
    return os.path.join(app.config['UPLOAD_FOLDER'], filename)


def _error_response(message, status=HTTP_BAD_REQUEST):
    return ({'error': message}, status)


def _success_response(filename):
    return ({'message': MSG_UPLOAD_SUCCESS, 'filename': filename}, HTTP_OK)


def allowed_file(filename):
    return (
        EXTENSION_SEPARATOR in filename
        and _extract_extension(filename) in app.config['ALLOWED_EXTENSIONS']
    )


def _serve_file(file_path):
    """Validate the path and send it as an attachment."""
    if not os.path.exists(file_path):
        abort(HTTP_NOT_FOUND)
    if not os.path.isfile(file_path):
        abort(HTTP_BAD_REQUEST, description=MSG_NOT_A_FILE)
    return send_file(file_path, as_attachment=True)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/upload', methods=['POST'])
def upload_file():
    if FILE_FIELD_NAME not in request.files:
        return _error_response(MSG_NO_FILE_PART)
    file = request.files[FILE_FIELD_NAME]
    if file.filename == '':
        return _error_response(MSG_NO_SELECTED_FILE)
    if file and allowed_file(file.filename):
        filename = _generate_unique_filename(file.filename)
        file.save(_upload_path_for(filename))
        return _success_response(filename)
    return _error_response(MSG_INVALID_FILE_TYPE)


@app.route('/download/<path:filename>')
def download_image(filename):
    file_path = _upload_path_for(filename)
    try:
        # Note: HTTP exceptions raised inside _serve_file are intentionally
        # caught below to preserve the original behaviour.
        return _serve_file(file_path)
    except Exception as e:
        abort(HTTP_INTERNAL_SERVER_ERROR, description=str(e))


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
def create_upload_folder():
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])


def main():
    create_upload_folder()
    app.run(debug=SERVER_DEBUG, host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
