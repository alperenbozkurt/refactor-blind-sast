"""Simple image gallery web application.

Serves a gallery page listing the images stored in the local ``gallery``
directory and exposes each image through its own URL.
"""

import os

from flask import Flask, abort, render_template, send_file

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GALLERY_DIR_NAME = 'gallery'
GALLERY_ROOT = os.path.join(os.path.dirname(__file__), GALLERY_DIR_NAME)

ALLOWED_IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg')
SAMPLE_IMAGE_FILENAMES = ('image1.jpg', 'image2.png', 'image3.jpeg')
DEFAULT_IMAGE_MIMETYPE = 'image/jpeg'

GALLERY_TEMPLATE = 'gallery.html'
ERROR_TEMPLATE = 'error.html'

INDEX_ROUTE = '/'
IMAGE_ROUTE = '/image/<path:filename>'

ERROR_IMAGE_NOT_FOUND = 'Image not found'
ERROR_PATH_NOT_A_FILE = 'Requested path is not a file'
ERROR_SERVER = 'Server error'

DEBUG_MODE = True
SERVER_PORT = 5000

# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config['GALLERY_ROOT'] = GALLERY_ROOT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_allowed_image(filename):
    """Return True if *filename* has a supported image extension."""
    return filename.lower().endswith(ALLOWED_IMAGE_EXTENSIONS)


def _list_gallery_images(gallery_root):
    """Return the supported image files in *gallery_root* ([] on failure)."""
    try:
        return [name for name in os.listdir(gallery_root)
                if _is_allowed_image(name)]
    except Exception:
        return []


def _resolve_image_path(filename):
    """Return the path of *filename* inside the gallery.

    Aborts with 404 if the path does not exist and with 400 if it is
    not a regular file.
    """
    image_path = os.path.join(app.config['GALLERY_ROOT'], filename)
    if not os.path.exists(image_path):
        abort(404)
    if not os.path.isfile(image_path):
        abort(400, ERROR_PATH_NOT_A_FILE)
    return image_path


def _create_sample_images(gallery_root):
    """Create the empty sample image files inside *gallery_root*."""
    for name in SAMPLE_IMAGE_FILENAMES:
        with open(os.path.join(gallery_root, name), 'w'):
            pass


def _ensure_gallery_root(gallery_root):
    """Create *gallery_root* (and its sample images) if it does not exist."""
    if os.path.exists(gallery_root):
        return
    os.makedirs(gallery_root)
    _create_sample_images(gallery_root)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route(INDEX_ROUTE)
def index():
    images = _list_gallery_images(app.config['GALLERY_ROOT'])
    return render_template(GALLERY_TEMPLATE, images=images)


@app.route(IMAGE_ROUTE)
def get_image(filename):
    try:
        image_path = _resolve_image_path(filename)
        return send_file(image_path, mimetype=DEFAULT_IMAGE_MIMETYPE)
    except Exception as e:
        abort(500, str(e))


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return (render_template(ERROR_TEMPLATE, error=ERROR_IMAGE_NOT_FOUND), 404)


@app.errorhandler(400)
def bad_request(e):
    return (render_template(ERROR_TEMPLATE, error=str(e)), 400)


@app.errorhandler(500)
def server_error(e):
    return (render_template(ERROR_TEMPLATE, error=ERROR_SERVER), 500)


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def main():
    """Prepare the gallery directory and start the development server."""
    _ensure_gallery_root(app.config['GALLERY_ROOT'])
    app.run(debug=DEBUG_MODE, port=SERVER_PORT)


if __name__ == '__main__':
    main()
