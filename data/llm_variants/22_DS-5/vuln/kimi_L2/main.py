"""Image upload and thumbnail service.

A small Flask application that accepts image uploads, generates JPEG
thumbnails and serves them back. Configuration is grouped in ``Config``
and module-level constants; storage handling is split into small helper
functions. Behaviour is identical to the original module.
"""

import hashlib
import io
import os

from flask import Flask, abort, request, send_file
from PIL import Image
from werkzeug.utils import secure_filename


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class Config:
    """Flask configuration values (loaded via ``app.config.from_object``)."""

    IMAGE_UPLOAD_FOLDER = './uploads'
    THUMBNAIL_FOLDER = './thumbnails'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}


DEFAULT_THUMBNAIL_SIZE = (128, 128)
THUMBNAIL_FORMAT = 'JPEG'
THUMBNAIL_EXTENSION = '.jpg'
THUMBNAIL_MIMETYPE = 'image/jpeg'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
SERVER_DEBUG = True

app = Flask(__name__)
app.config.from_object(Config)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _storage_folders():
    """Return the folders managed by this service (uploads, thumbnails)."""
    return (app.config['IMAGE_UPLOAD_FOLDER'], app.config['THUMBNAIL_FOLDER'])


def _extract_extension(filename):
    """Return the lowercased extension of ``filename`` (no leading dot)."""
    return filename.rsplit('.', 1)[1].lower()


def _thumbnail_path_for(source_path):
    """Build the deterministic thumbnail path for a given source image."""
    digest = hashlib.md5(source_path.encode()).hexdigest()
    filename = f'{digest}{THUMBNAIL_EXTENSION}'
    return os.path.join(app.config['THUMBNAIL_FOLDER'], filename)


def _remove_file(file_path):
    """Remove a single regular file, logging instead of raising on failure."""
    try:
        if os.path.isfile(file_path):
            os.unlink(file_path)
    except Exception as e:
        print(f'Error deleting {file_path}: {e}')


def _clear_folder(folder):
    """Delete every regular file directly inside ``folder``."""
    for filename in os.listdir(folder):
        _remove_file(os.path.join(folder, filename))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def allowed_file(filename):
    """Return True if ``filename`` has an allowed image extension."""
    return (
        '.' in filename
        and _extract_extension(filename) in app.config['ALLOWED_EXTENSIONS']
    )


def ensure_directories():
    """Create the upload and thumbnail folders if they do not exist."""
    for folder in _storage_folders():
        os.makedirs(folder, exist_ok=True)


def generate_thumbnail(source_path, size=DEFAULT_THUMBNAIL_SIZE):
    """Generate a JPEG thumbnail for ``source_path``.

    Returns the thumbnail path on success, or ``None`` on failure.
    """
    try:
        with Image.open(source_path) as img:
            img.thumbnail(size)
            thumb_path = _thumbnail_path_for(source_path)
            img.save(thumb_path, THUMBNAIL_FORMAT)
            return thumb_path
    except Exception as e:
        print(f'Error generating thumbnail: {e}')
        return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/upload', methods=['POST'])
def upload_image():
    """Store an uploaded image in the upload folder."""
    if 'file' not in request.files:
        abort(400, description='No file part')
    file = request.files['file']
    if file.filename == '':
        abort(400, description='No selected file')
    if not allowed_file(file.filename):
        abort(400, description='File type not allowed')
    filename = secure_filename(file.filename)
    save_path = os.path.join(app.config['IMAGE_UPLOAD_FOLDER'], filename)
    file.save(save_path)
    return ({'status': 'success', 'path': save_path}, 201)


@app.route('/thumbnail', methods=['POST'])
def create_thumbnail():
    """Generate a thumbnail for the image path given in the JSON body."""
    data = request.get_json()
    if not data or 'image_path' not in data:
        abort(400, description='No image path provided')
    thumb_path = generate_thumbnail(data['image_path'])
    if not thumb_path:
        abort(500, description='Failed to generate thumbnail')
    return {'status': 'success', 'thumbnail_path': thumb_path}


@app.route('/thumbnail/<path:thumb_path>')
def get_thumbnail(thumb_path):
    """Serve a previously generated thumbnail."""
    try:
        full_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumb_path)
        if not os.path.exists(full_path):
            abort(404)
        return send_file(full_path, mimetype=THUMBNAIL_MIMETYPE)
    except Exception as e:
        abort(500, description=str(e))


@app.route('/cleanup', methods=['POST'])
def cleanup_files():
    """Delete all files from the upload and thumbnail folders."""
    try:
        for folder in _storage_folders():
            _clear_folder(folder)
        return ({'status': 'success'}, 200)
    except Exception as e:
        abort(500, description=str(e))


# ---------------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------------

def main():
    """Prepare storage folders and run the development server."""
    ensure_directories()
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)


if __name__ == '__main__':
    main()
