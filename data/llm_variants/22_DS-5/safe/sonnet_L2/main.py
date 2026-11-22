import os
from flask import Flask, request, send_file, abort
from PIL import Image
import io
import hashlib
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_UPLOAD_DIR = './uploads'
DEFAULT_THUMBNAIL_DIR = './thumbnails'
DEFAULT_ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
DEFAULT_MAX_CONTENT_LENGTH = 8 * 1024 * 1024

DEFAULT_THUMBNAIL_SIZE = (128, 128)
THUMBNAIL_FORMAT = 'JPEG'
THUMBNAIL_EXTENSION = '.jpg'
THUMBNAIL_MIMETYPE = 'image/jpeg'
PARENT_TRAVERSAL_TOKEN = '../'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------
def _configure_app(flask_app):
    flask_app.config['IMAGE_UPLOAD_FOLDER'] = os.path.abspath(DEFAULT_UPLOAD_DIR)
    flask_app.config['THUMBNAIL_FOLDER'] = os.path.abspath(DEFAULT_THUMBNAIL_DIR)
    flask_app.config['ALLOWED_EXTENSIONS'] = set(DEFAULT_ALLOWED_EXTENSIONS)
    flask_app.config['MAX_CONTENT_LENGTH'] = DEFAULT_MAX_CONTENT_LENGTH


app = Flask(__name__)
_configure_app(app)


# ---------------------------------------------------------------------------
# Config accessors
# ---------------------------------------------------------------------------
def _upload_folder():
    return app.config['IMAGE_UPLOAD_FOLDER']


def _thumbnail_folder():
    return app.config['THUMBNAIL_FOLDER']


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def ensure_directories():
    os.makedirs(_upload_folder(), exist_ok=True)
    os.makedirs(_thumbnail_folder(), exist_ok=True)


def is_safe_path(basedir, path):
    basedir = os.path.abspath(basedir)
    path = os.path.abspath(path)
    return path.startswith(basedir + os.sep)


def _thumbnail_path_for(source_path):
    filename_hash = hashlib.sha256(source_path.encode()).hexdigest()
    return os.path.join(_thumbnail_folder(), f'{filename_hash}{THUMBNAIL_EXTENSION}')


def generate_thumbnail(source_path, size=DEFAULT_THUMBNAIL_SIZE):
    try:
        if not is_safe_path(_upload_folder(), source_path):
            return None
        with Image.open(source_path) as img:
            img.thumbnail(size)
            thumb_path = _thumbnail_path_for(source_path)
            os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
            img.save(thumb_path, THUMBNAIL_FORMAT)
            return thumb_path
    except Exception as e:
        app.logger.error(f'Error generating thumbnail: {e}')
        return None


def _is_valid_image_path(value):
    return isinstance(value, str) and PARENT_TRAVERSAL_TOKEN not in value


def _is_valid_thumbnail_name(thumb_path):
    return thumb_path.endswith(THUMBNAIL_EXTENSION) and PARENT_TRAVERSAL_TOKEN not in thumb_path


def _delete_file_if_safe(folder, filename):
    file_path = os.path.join(folder, filename)
    try:
        if os.path.isfile(file_path) and is_safe_path(folder, file_path):
            os.unlink(file_path)
    except Exception as e:
        app.logger.error(f'Error deleting {file_path}: {e}')


def _clear_folder(folder):
    for filename in os.listdir(folder):
        _delete_file_if_safe(folder, filename)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/upload', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        abort(400, description='No file part')
    file = request.files['file']
    if file.filename == '':
        abort(400, description='No selected file')
    if not allowed_file(file.filename):
        abort(400, description='File type not allowed')
    filename = secure_filename(file.filename)
    save_path = os.path.join(_upload_folder(), filename)
    try:
        file.save(save_path)
        return ({'status': 'success', 'path': save_path}, 201)
    except Exception as e:
        abort(500, description=f'Failed to save file: {e}')


@app.route('/thumbnail', methods=['POST'])
def create_thumbnail():
    data = request.get_json()
    if not data or 'image_path' not in data:
        abort(400, description='No image path provided')
    if not _is_valid_image_path(data['image_path']):
        abort(400, description='Invalid image path')
    thumb_path = generate_thumbnail(data['image_path'])
    if not thumb_path:
        abort(500, description='Failed to generate thumbnail')
    return {'status': 'success', 'thumbnail_path': thumb_path}


@app.route('/thumbnail/<path:thumb_path>')
def get_thumbnail(thumb_path):
    try:
        if not _is_valid_thumbnail_name(thumb_path):
            abort(400, description='Invalid thumbnail path')
        full_path = os.path.join(_thumbnail_folder(), thumb_path)
        if not is_safe_path(_thumbnail_folder(), full_path):
            abort(403, description='Access denied')
        if not os.path.exists(full_path):
            abort(404)
        return send_file(full_path, mimetype=THUMBNAIL_MIMETYPE)
    except Exception as e:
        abort(500, description=str(e))


@app.route('/cleanup', methods=['POST'])
def cleanup_files():
    try:
        for folder in [_upload_folder(), _thumbnail_folder()]:
            _clear_folder(folder)
        return ({'status': 'success'}, 200)
    except Exception as e:
        abort(500, description=str(e))


if __name__ == '__main__':
    ensure_directories()
    app.run(host=SERVER_HOST, port=SERVER_PORT)
