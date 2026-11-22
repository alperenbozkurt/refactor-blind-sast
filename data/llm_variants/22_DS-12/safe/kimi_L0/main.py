"""Flask application serving a small image gallery."""

import os

from flask import Flask, abort, render_template, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['GALLERY_ROOT'] = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'gallery')
)
app.config['ALLOWED_EXTENSIONS'] = {'.png', '.jpg', '.jpeg'}

MIMETYPES = {
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
}

SAMPLE_IMAGES = ('image1.jpg', 'image2.png', 'image3.jpeg')


def is_safe_path(base_path, requested_path):
    """Return True if requested_path resolves to a location inside base_path."""
    base_path = os.path.abspath(base_path)
    requested_path = os.path.abspath(requested_path)
    return requested_path.startswith(base_path + os.sep)


def allowed_file(filename):
    """Return True if filename ends with one of the configured extensions."""
    if '.' not in filename:
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in {ext[1:] for ext in app.config['ALLOWED_EXTENSIONS']}


@app.route('/')
def index():
    images = []
    try:
        root = app.config['GALLERY_ROOT']
        images = [
            name
            for name in os.listdir(root)
            if allowed_file(name) and is_safe_path(root, os.path.join(root, name))
        ]
    except Exception as e:
        app.logger.error(f'Error listing images: {e}')
    return render_template('gallery.html', images=images)


@app.route('/image/<path:filename>')
def get_image(filename):
    try:
        if not allowed_file(filename):
            abort(400, 'Invalid file type')
        safe_filename = secure_filename(filename)
        image_path = os.path.join(app.config['GALLERY_ROOT'], safe_filename)
        if not is_safe_path(app.config['GALLERY_ROOT'], image_path):
            abort(403, 'Access denied')
        if not os.path.exists(image_path):
            abort(404)
        if not os.path.isfile(image_path):
            abort(400, 'Requested path is not a file')
        mimetype = MIMETYPES.get(filename.rsplit('.', 1)[1].lower())
        return send_file(image_path, mimetype=mimetype)
    except Exception as e:
        app.logger.error(f'Error serving image: {e}')
        abort(500, 'Internal server error')


def _render_error(message, status_code):
    return render_template('error.html', error=message), status_code


@app.errorhandler(404)
def not_found(e):
    return _render_error('Image not found', 404)


@app.errorhandler(400)
def bad_request(e):
    return _render_error('Invalid request', 400)


@app.errorhandler(403)
def forbidden(e):
    return _render_error('Access denied', 403)


@app.errorhandler(500)
def server_error(e):
    return _render_error('Internal server error', 500)


if __name__ == '__main__':
    gallery_root = app.config['GALLERY_ROOT']
    if not os.path.exists(gallery_root):
        os.makedirs(gallery_root, mode=0o750)
        for image_name in SAMPLE_IMAGES:
            try:
                with open(os.path.join(gallery_root, image_name), 'wb'):
                    pass
            except Exception as e:
                app.logger.error(f'Error creating sample image: {e}')
    app.run(port=5000)
