import os

from flask import Flask, send_file, render_template, abort

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
GALLERY_DIR_NAME = 'gallery'
ALLOWED_EXTENSIONS = ('.png', '.jpg', '.jpeg')
IMAGE_MIMETYPE = 'image/jpeg'
SAMPLE_IMAGES = ['image1.jpg', 'image2.png', 'image3.jpeg']

GALLERY_TEMPLATE = 'gallery.html'
ERROR_TEMPLATE = 'error.html'

NOT_FOUND_MESSAGE = 'Image not found'
NOT_A_FILE_MESSAGE = 'Requested path is not a file'
SERVER_ERROR_MESSAGE = 'Server error'

DEFAULT_PORT = 5000
DEBUG_MODE = True

# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #
app = Flask(__name__)
app.config['GALLERY_ROOT'] = os.path.join(os.path.dirname(__file__), GALLERY_DIR_NAME)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _gallery_root():
    """Return the currently configured gallery root directory."""
    return app.config['GALLERY_ROOT']


def _is_allowed_image(filename):
    """Return True if the filename has an allowed image extension."""
    return filename.lower().endswith(ALLOWED_EXTENSIONS)


def _list_gallery_images():
    """List image filenames in the gallery root; empty list on any failure."""
    try:
        return [f for f in os.listdir(_gallery_root()) if _is_allowed_image(f)]
    except Exception:
        return []


def _build_image_path(filename):
    """Build the filesystem path for a requested image."""
    return os.path.join(_gallery_root(), filename)


def _validate_image_path(image_path):
    """Abort with the appropriate HTTP error if the path is unusable."""
    if not os.path.exists(image_path):
        abort(404)
    if not os.path.isfile(image_path):
        abort(400, NOT_A_FILE_MESSAGE)


def _render_error(message, status_code):
    """Render the error template with the given message and status code."""
    return (render_template(ERROR_TEMPLATE, error=message), status_code)


def _ensure_gallery_root():
    """Create the gallery directory with placeholder images if missing."""
    root = _gallery_root()
    if not os.path.exists(root):
        os.makedirs(root)
        for img in SAMPLE_IMAGES:
            open(os.path.join(root, img), 'w').close()


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/')
def index():
    images = _list_gallery_images()
    return render_template(GALLERY_TEMPLATE, images=images)


@app.route('/image/<path:filename>')
def get_image(filename):
    try:
        image_path = _build_image_path(filename)
        _validate_image_path(image_path)
        return send_file(image_path, mimetype=IMAGE_MIMETYPE)
    except Exception as e:
        # Note: this intentionally also catches the HTTP exceptions raised
        # above, preserving the original behaviour (they become 500 errors).
        abort(500, str(e))


# --------------------------------------------------------------------------- #
# Error handlers
# --------------------------------------------------------------------------- #
@app.errorhandler(404)
def not_found(e):
    return _render_error(NOT_FOUND_MESSAGE, 404)


@app.errorhandler(400)
def bad_request(e):
    return _render_error(str(e), 400)


@app.errorhandler(500)
def server_error(e):
    return _render_error(SERVER_ERROR_MESSAGE, 500)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
if __name__ == '__main__':
    _ensure_gallery_root()
    app.run(debug=DEBUG_MODE, port=DEFAULT_PORT)
