import os
from flask import Flask, request, send_file, abort
from PIL import Image
import io
import hashlib
from werkzeug.utils import secure_filename

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

UPLOAD_FOLDER_KEY = 'IMAGE_UPLOAD_FOLDER'
THUMBNAIL_FOLDER_KEY = 'THUMBNAIL_FOLDER'
ALLOWED_EXTENSIONS_KEY = 'ALLOWED_EXTENSIONS'

DEFAULT_UPLOAD_FOLDER = './uploads'
DEFAULT_THUMBNAIL_FOLDER = './thumbnails'
DEFAULT_ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

DEFAULT_THUMBNAIL_SIZE = (128, 128)
THUMBNAIL_FORMAT = 'JPEG'
THUMBNAIL_EXTENSION = 'jpg'
THUMBNAIL_MIMETYPE = 'image/jpeg'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
SERVER_DEBUG = True


class DefaultConfig:
    """Default application settings."""

    @classmethod
    def as_dict(cls):
        return {
            UPLOAD_FOLDER_KEY: DEFAULT_UPLOAD_FOLDER,
            THUMBNAIL_FOLDER_KEY: DEFAULT_THUMBNAIL_FOLDER,
            ALLOWED_EXTENSIONS_KEY: set(DEFAULT_ALLOWED_EXTENSIONS),
        }


app = Flask(__name__)
app.config.update(DefaultConfig.as_dict())


# --------------------------------------------------------------------------- #
# Configuration accessors (read at call time so runtime changes are honoured)
# --------------------------------------------------------------------------- #

def _upload_folder():
    return app.config[UPLOAD_FOLDER_KEY]


def _thumbnail_folder():
    return app.config[THUMBNAIL_FOLDER_KEY]


def _allowed_extensions():
    return app.config[ALLOWED_EXTENSIONS_KEY]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _file_extension(filename):
    return filename.rsplit('.', 1)[1].lower()


def allowed_file(filename):
    return '.' in filename and _file_extension(filename) in _allowed_extensions()


def ensure_directories():
    os.makedirs(_upload_folder(), exist_ok=True)
    os.makedirs(_thumbnail_folder(), exist_ok=True)


def _thumbnail_filename(source_path):
    digest = hashlib.md5(source_path.encode()).hexdigest()
    return f'{digest}.{THUMBNAIL_EXTENSION}'


def _thumbnail_destination(source_path):
    return os.path.join(_thumbnail_folder(), _thumbnail_filename(source_path))


def generate_thumbnail(source_path, size=DEFAULT_THUMBNAIL_SIZE):
    try:
        with Image.open(source_path) as img:
            img.thumbnail(size)
            thumb_path = _thumbnail_destination(source_path)
            img.save(thumb_path, THUMBNAIL_FORMAT)
            return thumb_path
    except Exception as e:
        print(f'Error generating thumbnail: {e}')
        return None


def _delete_file(file_path):
    """Delete a regular file, logging (not raising) any failure."""
    try:
        if os.path.isfile(file_path):
            os.unlink(file_path)
    except Exception as e:
        print(f'Error deleting {file_path}: {e}')


def _clear_folder(folder):
    for filename in os.listdir(folder):
        _delete_file(os.path.join(folder, filename))


def _get_uploaded_file():
    """Validate the upload request and return the file object."""
    if 'file' not in request.files:
        abort(400, description='No file part')
    file = request.files['file']
    if file.filename == '':
        abort(400, description='No selected file')
    if not allowed_file(file.filename):
        abort(400, description='File type not allowed')
    return file


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

@app.route('/upload', methods=['POST'])
def upload_image():
    file = _get_uploaded_file()
    filename = secure_filename(file.filename)
    save_path = os.path.join(_upload_folder(), filename)
    file.save(save_path)
    return ({'status': 'success', 'path': save_path}, 201)


@app.route('/thumbnail', methods=['POST'])
def create_thumbnail():
    data = request.get_json()
    if not data or 'image_path' not in data:
        abort(400, description='No image path provided')
    thumb_path = generate_thumbnail(data['image_path'])
    if not thumb_path:
        abort(500, description='Failed to generate thumbnail')
    return {'status': 'success', 'thumbnail_path': thumb_path}


@app.route('/thumbnail/<path:thumb_path>')
def get_thumbnail(thumb_path):
    try:
        full_path = os.path.join(_thumbnail_folder(), thumb_path)
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
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)
