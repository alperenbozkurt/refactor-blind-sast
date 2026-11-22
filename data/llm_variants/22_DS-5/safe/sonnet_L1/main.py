import hashlib
import io
import os

from flask import Flask, request, send_file, abort
from PIL import Image
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['IMAGE_UPLOAD_FOLDER'] = os.path.abspath('./uploads')
app.config['THUMBNAIL_FOLDER'] = os.path.abspath('./thumbnails')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024

DEFAULT_THUMBNAIL_SIZE = (128, 128)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def allowed_file(filename):
    """Return True if the filename has an allowed extension."""
    if '.' not in filename:
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in app.config['ALLOWED_EXTENSIONS']


def ensure_directories():
    """Create the upload and thumbnail folders if they do not exist."""
    os.makedirs(app.config['IMAGE_UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['THUMBNAIL_FOLDER'], exist_ok=True)


def is_safe_path(basedir, path):
    """Return True if path resolves to a location inside basedir."""
    basedir = os.path.abspath(basedir)
    path = os.path.abspath(path)
    return path.startswith(basedir + os.sep)


def _thumbnail_path_for(source_path):
    """Build the thumbnail file path derived from the source path hash."""
    filename_hash = hashlib.sha256(source_path.encode()).hexdigest()
    return os.path.join(app.config['THUMBNAIL_FOLDER'], f'{filename_hash}.jpg')


def generate_thumbnail(source_path, size=DEFAULT_THUMBNAIL_SIZE):
    """Generate a JPEG thumbnail for source_path.

    Returns the thumbnail path, or None if the source path is unsafe
    or generation fails.
    """
    try:
        if not is_safe_path(app.config['IMAGE_UPLOAD_FOLDER'], source_path):
            return None
        with Image.open(source_path) as img:
            img.thumbnail(size)
            thumb_path = _thumbnail_path_for(source_path)
            os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
            img.save(thumb_path, 'JPEG')
            return thumb_path
    except Exception as e:
        app.logger.error(f'Error generating thumbnail: {e}')
        return None


def _delete_files_in_folder(folder):
    """Delete all regular files directly inside folder, logging failures."""
    for filename in os.listdir(folder):
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
    if 'file' not in request.files:
        abort(400, description='No file part')

    file = request.files['file']
    if file.filename == '':
        abort(400, description='No selected file')
    if not allowed_file(file.filename):
        abort(400, description='File type not allowed')

    filename = secure_filename(file.filename)
    save_path = os.path.join(app.config['IMAGE_UPLOAD_FOLDER'], filename)
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

    image_path = data['image_path']
    if not isinstance(image_path, str) or '../' in image_path:
        abort(400, description='Invalid image path')

    thumb_path = generate_thumbnail(image_path)
    if not thumb_path:
        abort(500, description='Failed to generate thumbnail')
    return {'status': 'success', 'thumbnail_path': thumb_path}


@app.route('/thumbnail/<path:thumb_path>')
def get_thumbnail(thumb_path):
    try:
        if not thumb_path.endswith('.jpg') or '../' in thumb_path:
            abort(400, description='Invalid thumbnail path')

        full_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumb_path)
        if not is_safe_path(app.config['THUMBNAIL_FOLDER'], full_path):
            abort(403, description='Access denied')
        if not os.path.exists(full_path):
            abort(404)

        return send_file(full_path, mimetype='image/jpeg')
    except Exception as e:
        abort(500, description=str(e))


@app.route('/cleanup', methods=['POST'])
def cleanup_files():
    try:
        for folder in [app.config['IMAGE_UPLOAD_FOLDER'],
                       app.config['THUMBNAIL_FOLDER']]:
            _delete_files_in_folder(folder)
        return ({'status': 'success'}, 200)
    except Exception as e:
        abort(500, description=str(e))


if __name__ == '__main__':
    ensure_directories()
    app.run(host='0.0.0.0', port=5000)
