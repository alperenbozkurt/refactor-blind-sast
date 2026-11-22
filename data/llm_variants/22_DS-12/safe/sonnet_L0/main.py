import os
from flask import Flask, send_file, render_template, abort
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['GALLERY_ROOT'] = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'gallery')
)
app.config['ALLOWED_EXTENSIONS'] = {'.png', '.jpg', '.jpeg'}

_SAMPLE_IMAGES = ('image1.jpg', 'image2.png', 'image3.jpeg')
_GALLERY_DIR_MODE = 0o750  # 488


def is_safe_path(base_path, requested_path):
    base_path = os.path.abspath(base_path)
    requested_path = os.path.abspath(requested_path)
    return requested_path.startswith(base_path + os.sep)


def allowed_file(filename):
    if '.' not in filename:
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    allowed = {ext[1:] for ext in app.config['ALLOWED_EXTENSIONS']}
    return extension in allowed


def _guess_mimetype(filename):
    lowered = filename.lower()
    if lowered.endswith('.png'):
        return 'image/png'
    if lowered.endswith(('.jpg', '.jpeg')):
        return 'image/jpeg'
    return None


def _render_error(message, status):
    return render_template('error.html', error=message), status


@app.route('/')
def index():
    images = []
    try:
        root = app.config['GALLERY_ROOT']
        images = [
            name for name in os.listdir(root)
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
        root = app.config['GALLERY_ROOT']
        image_path = os.path.join(root, secure_filename(filename))
        if not is_safe_path(root, image_path):
            abort(403, 'Access denied')
        if not os.path.exists(image_path):
            abort(404)
        if not os.path.isfile(image_path):
            abort(400, 'Requested path is not a file')
        return send_file(image_path, mimetype=_guess_mimetype(filename))
    except Exception as e:
        app.logger.error(f'Error serving image: {e}')
        abort(500, 'Internal server error')


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


def _create_sample_gallery():
    root = app.config['GALLERY_ROOT']
    os.makedirs(root, mode=_GALLERY_DIR_MODE)
    for img in _SAMPLE_IMAGES:
        try:
            with open(os.path.join(root, img), 'wb'):
                pass
        except Exception as e:
            app.logger.error(f'Error creating sample image: {e}')


if __name__ == '__main__':
    if not os.path.exists(app.config['GALLERY_ROOT']):
        _create_sample_gallery()
    app.run(port=5000)
