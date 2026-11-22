import os
from flask import Flask, abort, render_template, send_file
from werkzeug.utils import secure_filename

GALLERY_DIR_NAME = 'gallery'
GALLERY_DIR_MODE = 488
SERVER_PORT = 5000
SAMPLE_IMAGE_FILENAMES = ('image1.jpg', 'image2.png', 'image3.jpeg')

ERROR_MESSAGES = {
    400: 'Invalid request',
    403: 'Access denied',
    404: 'Image not found',
    500: 'Internal server error',
}

app = Flask(__name__)
app.config['GALLERY_ROOT'] = os.path.abspath(
    os.path.join(os.path.dirname(__file__), GALLERY_DIR_NAME)
)
app.config['ALLOWED_EXTENSIONS'] = {'.png', '.jpg', '.jpeg'}


def _gallery_root():
    return app.config['GALLERY_ROOT']


def _gallery_path(filename):
    return os.path.join(_gallery_root(), filename)


def _allowed_extensions():
    return {ext[1:] for ext in app.config['ALLOWED_EXTENSIONS']}


def _filename_extension(filename):
    return filename.rsplit('.', 1)[1].lower()


def _mimetype_for_filename(filename):
    if filename.lower().endswith('.png'):
        return 'image/png'
    if filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
        return 'image/jpeg'
    return None


def _log_error(message, error):
    app.logger.error(f'{message}: {error}')


def _render_error(status_code):
    return (
        render_template('error.html', error=ERROR_MESSAGES[status_code]),
        status_code,
    )


def _ensure_gallery_root():
    if os.path.exists(_gallery_root()):
        return False
    os.makedirs(_gallery_root(), mode=GALLERY_DIR_MODE)
    return True


def _create_sample_images():
    for image_filename in SAMPLE_IMAGE_FILENAMES:
        try:
            with open(_gallery_path(image_filename), 'wb'):
                pass
        except Exception as e:
            _log_error('Error creating sample image', e)


def is_safe_path(base_path, requested_path):
    base_path = os.path.abspath(base_path)
    requested_path = os.path.abspath(requested_path)
    return requested_path.startswith(base_path + os.sep)


def allowed_file(filename):
    return (
        '.' in filename
        and _filename_extension(filename) in _allowed_extensions()
    )


@app.route('/')
def index():
    images = []
    try:
        images = [
            filename
            for filename in os.listdir(_gallery_root())
            if allowed_file(filename)
            and is_safe_path(_gallery_root(), _gallery_path(filename))
        ]
    except Exception as e:
        _log_error('Error listing images', e)
    return render_template('gallery.html', images=images)


@app.route('/image/<path:filename>')
def get_image(filename):
    try:
        if not allowed_file(filename):
            abort(400, 'Invalid file type')
        safe_filename = secure_filename(filename)
        image_path = _gallery_path(safe_filename)
        if not is_safe_path(_gallery_root(), image_path):
            abort(403, 'Access denied')
        if not os.path.exists(image_path):
            abort(404)
        if not os.path.isfile(image_path):
            abort(400, 'Requested path is not a file')
        return send_file(image_path, mimetype=_mimetype_for_filename(filename))
    except Exception as e:
        _log_error('Error serving image', e)
        abort(500, 'Internal server error')


@app.errorhandler(404)
def not_found(e):
    return _render_error(404)


@app.errorhandler(400)
def bad_request(e):
    return _render_error(400)


@app.errorhandler(403)
def forbidden(e):
    return _render_error(403)


@app.errorhandler(500)
def server_error(e):
    return _render_error(500)


if __name__ == '__main__':
    if _ensure_gallery_root():
        _create_sample_images()
    app.run(port=SERVER_PORT)
