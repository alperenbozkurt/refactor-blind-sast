"""File upload/download Flask service.

Refactored into named constants, a small configuration object and helper
functions while preserving the original module's exact behaviour.
"""

import os
import uuid
from dataclasses import dataclass

from flask import Flask, request, send_file, abort

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}


@dataclass(frozen=True)
class ServerConfig:
    """Settings for the built-in development server."""

    host: str = '0.0.0.0'
    port: int = 5000
    debug: bool = False


SERVER_CONFIG = ServerConfig()


def _configure_app(application):
    application.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    application.config['ALLOWED_EXTENSIONS'] = ALLOWED_EXTENSIONS


app = Flask(__name__)
_configure_app(app)


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def _extension_of(filename):
    """Lower-cased extension of *filename* (which must contain a dot)."""
    return filename.rsplit('.', 1)[1].lower()


def allowed_file(filename):
    return '.' in filename and _extension_of(filename) in app.config['ALLOWED_EXTENSIONS']


def _stored_filename(original_filename):
    """Unique on-disk filename preserving the lower-cased extension."""
    return '{}.{}'.format(uuid.uuid4(), _extension_of(original_filename))


def _upload_path(filename):
    return os.path.join(app.config['UPLOAD_FOLDER'], filename)


def _resolve_download_path(filename):
    upload_dir = os.path.abspath(app.config['UPLOAD_FOLDER'])
    file_path = os.path.abspath(os.path.join(upload_dir, filename))
    if not file_path.startswith(upload_dir):
        abort(403, description='Access denied')
    return file_path


def _validate_download(file_path, filename):
    if not os.path.exists(file_path):
        abort(404)
    if not os.path.isfile(file_path):
        abort(400, description='Requested path is not a file')
    if not allowed_file(filename):
        abort(400, description='Invalid file type')


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return ({'error': 'No file part'}, 400)
    file = request.files['file']
    if file.filename == '':
        return ({'error': 'No selected file'}, 400)
    if file and allowed_file(file.filename):
        filename = _stored_filename(file.filename)
        file.save(_upload_path(filename))
        return ({'message': 'File uploaded successfully', 'filename': filename}, 200)
    return ({'error': 'Invalid file type'}, 400)


@app.route('/download/<path:filename>')
def download_image(filename):
    try:
        file_path = _resolve_download_path(filename)
        _validate_download(file_path, filename)
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        abort(500, description=str(e))


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def create_upload_folder():
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])


if __name__ == '__main__':
    create_upload_folder()
    app.run(debug=SERVER_CONFIG.debug, host=SERVER_CONFIG.host, port=SERVER_CONFIG.port)
