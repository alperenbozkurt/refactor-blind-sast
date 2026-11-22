"""Simple image upload/download Flask service.

Refactored for modularity: configuration lives in a single object, magic
values are named constants, and the route handlers delegate to small,
single-purpose helper functions. External behaviour is unchanged.
"""

import os
import uuid

from flask import Flask, request, send_file, abort


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class Config:
    """Default configuration values for the application."""

    UPLOAD_FOLDER = './uploads'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}


# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
SERVER_DEBUG = True

UPLOAD_ROUTE = '/upload'
DOWNLOAD_ROUTE = '/download/<path:filename>'

FILE_FIELD_NAME = 'file'
EXTENSION_SEPARATOR = '.'

ERROR_NO_FILE_PART = 'No file part'
ERROR_NO_SELECTED_FILE = 'No selected file'
ERROR_INVALID_FILE_TYPE = 'Invalid file type'
ERROR_PATH_NOT_A_FILE = 'Requested path is not a file'
MESSAGE_UPLOAD_SUCCESS = 'File uploaded successfully'


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

def _create_app():
    """Build and configure the Flask application instance."""
    flask_app = Flask(__name__)
    flask_app.config.from_object(Config)
    return flask_app


app = _create_app()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error_response(message, status_code):
    """Build a consistent JSON error response."""
    return ({'error': message}, status_code)


def _extract_extension(filename):
    """Return the lowercased extension of a filename (without the dot)."""
    return filename.rsplit(EXTENSION_SEPARATOR, 1)[1].lower()


def _unique_upload_filename(original_filename):
    """Generate a collision-resistant filename preserving the extension."""
    return str(uuid.uuid4()) + EXTENSION_SEPARATOR + _extract_extension(original_filename)


def _upload_path(filename):
    """Resolve a filename to a path inside the configured upload folder."""
    return os.path.join(app.config['UPLOAD_FOLDER'], filename)


def allowed_file(filename):
    """Check whether a filename has an allowed extension."""
    return (
        EXTENSION_SEPARATOR in filename
        and _extract_extension(filename) in app.config['ALLOWED_EXTENSIONS']
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route(UPLOAD_ROUTE, methods=['POST'])
def upload_file():
    if FILE_FIELD_NAME not in request.files:
        return _error_response(ERROR_NO_FILE_PART, HTTP_BAD_REQUEST)

    file = request.files[FILE_FIELD_NAME]
    if file.filename == '':
        return _error_response(ERROR_NO_SELECTED_FILE, HTTP_BAD_REQUEST)

    if file and allowed_file(file.filename):
        filename = _unique_upload_filename(file.filename)
        file.save(_upload_path(filename))
        return (
            {'message': MESSAGE_UPLOAD_SUCCESS, 'filename': filename},
            HTTP_OK,
        )

    return _error_response(ERROR_INVALID_FILE_TYPE, HTTP_BAD_REQUEST)


def _ensure_downloadable(file_path):
    """Abort with the appropriate error unless the path is a real file."""
    if not os.path.exists(file_path):
        abort(HTTP_NOT_FOUND)
    if not os.path.isfile(file_path):
        abort(HTTP_BAD_REQUEST, description=ERROR_PATH_NOT_A_FILE)


@app.route(DOWNLOAD_ROUTE)
def download_image(filename):
    file_path = _upload_path(filename)
    try:
        _ensure_downloadable(file_path)
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        abort(HTTP_INTERNAL_SERVER_ERROR, description=str(e))


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

def create_upload_folder():
    upload_folder = app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)


def main():
    create_upload_folder()
    app.run(debug=SERVER_DEBUG, host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
