import os
from flask import Flask, send_file, render_template, abort
from werkzeug.utils import secure_filename

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------
GALLERY_DIR_NAME = 'gallery'
DEFAULT_ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg'}
GALLERY_DIR_MODE = 488  # equivalent to 0o750
SAMPLE_IMAGES = ['image1.jpg', 'image2.png', 'image3.jpeg']
SERVER_PORT = 5000

GALLERY_TEMPLATE = 'gallery.html'
ERROR_TEMPLATE = 'error.html'

# Ordered mapping of file suffix -> mimetype
MIMETYPES_BY_SUFFIX = (
    ('.png', 'image/png'),
    ('.jpg', 'image/jpeg'),
    ('.jpeg', 'image/jpeg'),
)

MSG_NOT_FOUND = 'Image not found'
MSG_BAD_REQUEST = 'Invalid request'
MSG_FORBIDDEN = 'Access denied'
MSG_SERVER_ERROR = 'Internal server error'


# --------------------------------------------------------------------------
# Application setup
# --------------------------------------------------------------------------
def _default_gallery_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), GALLERY_DIR_NAME))


app = Flask(__name__)
app.config['GALLERY_ROOT'] = _default_gallery_root()
app.config['ALLOWED_EXTENSIONS'] = set(DEFAULT_ALLOWED_EXTENSIONS)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _gallery_root():
    return app.config['GALLERY_ROOT']


def _allowed_suffixes():
    """Allowed extensions without the leading dot."""
    return {ext[1:] for ext in app.config['ALLOWED_EXTENSIONS']}


def is_safe_path(base_path, requested_path):
    base_path = os.path.abspath(base_path)
    requested_path = os.path.abspath(requested_path)
    return requested_path.startswith(base_path + os.sep)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in _allowed_suffixes()


def _guess_mimetype(filename):
    lowered = filename.lower()
    for suffix, mimetype in MIMETYPES_BY_SUFFIX:
        if lowered.endswith(suffix):
            return mimetype
    return None


def _list_gallery_images():
    root = _gallery_root()
    return [
        f for f in os.listdir(root)
        if allowed_file(f) and is_safe_path(root, os.path.join(root, f))
    ]


def _render_error(message, status_code):
    return (render_template(ERROR_TEMPLATE, error=message), status_code)


def _create_sample_images(root):
    for img in SAMPLE_IMAGES:
        try:
            with open(os.path.join(root, img), 'wb') as f:
                pass
        except Exception as e:
            app.logger.error(f'Error creating sample image: {e}')


def _initialize_gallery():
    root = _gallery_root()
    if not os.path.exists(root):
        os.makedirs(root, mode=GALLERY_DIR_MODE)
        _create_sample_images(root)


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route('/')
def index():
    images = []
    try:
        images = _list_gallery_images()
    except Exception as e:
        app.logger.error(f'Error listing images: {e}')
    return render_template(GALLERY_TEMPLATE, images=images)


@app.route('/image/<path:filename>')
def get_image(filename):
    try:
        if not allowed_file(filename):
            abort(400, 'Invalid file type')
        safe_filename = secure_filename(filename)
        image_path = os.path.join(_gallery_root(), safe_filename)
        if not is_safe_path(_gallery_root(), image_path):
            abort(403, 'Access denied')
        if not os.path.exists(image_path):
            abort(404)
        if not os.path.isfile(image_path):
            abort(400, 'Requested path is not a file')
        mimetype = _guess_mimetype(filename)
        return send_file(image_path, mimetype=mimetype)
    except Exception as e:
        app.logger.error(f'Error serving image: {e}')
        abort(500, 'Internal server error')


# --------------------------------------------------------------------------
# Error handlers
# --------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return _render_error(MSG_NOT_FOUND, 404)


@app.errorhandler(400)
def bad_request(e):
    return _render_error(MSG_BAD_REQUEST, 400)


@app.errorhandler(403)
def forbidden(e):
    return _render_error(MSG_FORBIDDEN, 403)


@app.errorhandler(500)
def server_error(e):
    return _render_error(MSG_SERVER_ERROR, 500)


# --------------------------------------------------------------------------
# CLI entry point
# --------------------------------------------------------------------------
if __name__ == '__main__':
    _initialize_gallery()
    app.run(port=SERVER_PORT)
