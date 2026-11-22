import hashlib
import io
import os

from flask import Flask, abort, request, send_file
from PIL import Image
from werkzeug.utils import secure_filename


# ---------------------------------------------------------------------------
# Application configuration
# ---------------------------------------------------------------------------

class Config:
    """Default configuration for the image/thumbnail service."""

    IMAGE_UPLOAD_FOLDER = os.path.abspath('./uploads')
    THUMBNAIL_FOLDER = os.path.abspath('./thumbnails')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024


# Thumbnail generation defaults.
DEFAULT_THUMBNAIL_SIZE = (128, 128)
THUMBNAIL_IMAGE_FORMAT = 'JPEG'
THUMBNAIL_FILE_EXTENSION = '.jpg'
THUMBNAIL_MIMETYPE = 'image/jpeg'

# Substring rejected in user-supplied paths to guard against path traversal.
PATH_TRAVERSAL_SEQUENCE = '../'

# Development server defaults.
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000

app = Flask(__name__)
app.config.from_object(Config)


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------

def is_safe_path(basedir, path):
    basedir = os.path.abspath(basedir)
    path = os.path.abspath(path)
    return path.startswith(basedir + os.sep)


def _managed_folders():
    return [app.config['IMAGE_UPLOAD_FOLDER'], app.config['THUMBNAIL_FOLDER']]


def ensure_directories():
    for folder in _managed_folders():
        os.makedirs(folder, exist_ok=True)


def _file_extension(filename):
    return filename.rsplit('.', 1)[1].lower()


def allowed_file(filename):
    return (
        '.' in filename
        and _file_extension(filename) in app.config['ALLOWED_EXTENSIONS']
    )


# ---------------------------------------------------------------------------
# Thumbnail generation
# ---------------------------------------------------------------------------

def _thumbnail_path_for(source_path):
    filename_hash = hashlib.sha256(source_path.encode()).hexdigest()
    return os.path.join(
        app.config['THUMBNAIL_FOLDER'],
        f'{filename_hash}{THUMBNAIL_FILE_EXTENSION}',
    )


def _save_thumbnail(image, thumb_path):
    os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
    image.save(thumb_path, THUMBNAIL_IMAGE_FORMAT)


def generate_thumbnail(source_path, size=DEFAULT_THUMBNAIL_SIZE):
    try:
        if not is_safe_path(app.config['IMAGE_UPLOAD_FOLDER'], source_path):
            return None
        with Image.open(source_path) as img:
            img.thumbnail(size)
            thumb_path = _thumbnail_path_for(source_path)
            _save_thumbnail(img, thumb_path)
            return thumb_path
    except Exception as e:
        app.logger.error(f'Error generating thumbnail: {e}')
        return None


# ---------------------------------------------------------------------------
# Request validation helpers
# ---------------------------------------------------------------------------

def _get_uploaded_file():
    if 'file' not in request.files:
        abort(400, description='No file part')
    file = request.files['file']
    if file.filename == '':
        abort(400, description='No selected file')
    if not allowed_file(file.filename):
        abort(400, description='File type not allowed')
    return file


def _extract_image_path(data):
    if not data or 'image_path' not in data:
        abort(400, description='No image path provided')
    image_path = data['image_path']
    if not isinstance(image_path, str) or PATH_TRAVERSAL_SEQUENCE in image_path:
        abort(400, description='Invalid image path')
    return image_path


def _resolve_thumbnail_path(thumb_path):
    if (
        not thumb_path.endswith(THUMBNAIL_FILE_EXTENSION)
        or PATH_TRAVERSAL_SEQUENCE in thumb_path
    ):
        abort(400, description='Invalid thumbnail path')
    full_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumb_path)
    if not is_safe_path(app.config['THUMBNAIL_FOLDER'], full_path):
        abort(403, description='Access denied')
    if not os.path.exists(full_path):
        abort(404)
    return full_path


def _delete_file(folder, filename):
    file_path = os.path.join(folder, filename)
    try:
        if os.path.isfile(file_path) and is_safe_path(folder, file_path):
            os.unlink(file_path)
    except Exception as e:
        app.logger.error(f'Error deleting {file_path}: {e}')


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/upload', methods=['POST'])
def upload_image():
    file = _get_uploaded_file()
    filename = secure_filename(file.filename)
    save_path = os.path.join(app.config['IMAGE_UPLOAD_FOLDER'], filename)
    try:
        file.save(save_path)
        return ({'status': 'success', 'path': save_path}, 201)
    except Exception as e:
        abort(500, description=f'Failed to save file: {e}')


@app.route('/thumbnail', methods=['POST'])
def create_thumbnail():
    image_path = _extract_image_path(request.get_json())
    thumb_path = generate_thumbnail(image_path)
    if not thumb_path:
        abort(500, description='Failed to generate thumbnail')
    return {'status': 'success', 'thumbnail_path': thumb_path}


@app.route('/thumbnail/<path:thumb_path>')
def get_thumbnail(thumb_path):
    try:
        full_path = _resolve_thumbnail_path(thumb_path)
        return send_file(full_path, mimetype=THUMBNAIL_MIMETYPE)
    except Exception as e:
        abort(500, description=str(e))


@app.route('/cleanup', methods=['POST'])
def cleanup_files():
    try:
        for folder in _managed_folders():
            for filename in os.listdir(folder):
                _delete_file(folder, filename)
        return ({'status': 'success'}, 200)
    except Exception as e:
        abort(500, description=str(e))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    ensure_directories()
    app.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
