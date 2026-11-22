import os

from flask import Flask, send_file, render_template, abort
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['GALLERY_ROOT'] = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'gallery')
)
app.config['ALLOWED_EXTENSIONS'] = {'.png', '.jpg', '.jpeg'}

GALLERY_DIR_MODE = 0o750  # same value as the previous decimal 488
SAMPLE_IMAGES = ['image1.jpg', 'image2.png', 'image3.jpeg']


def is_safe_path(base_path, requested_path):
    base_path = os.path.abspath(base_path)
    requested_path = os.path.abspath(requested_path)
    return requested_path.startswith(base_path + os.sep)


def allowed_file(filename):
    if '.' not in filename:
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    allowed_extensions = {ext[1:] for ext in app.config['ALLOWED_EXTENSIONS']}
    return extension in allowed_extensions


def _guess_mimetype(filename):
    lowered = filename.lower()
    if lowered.endswith('.png'):
        return 'image/png'
    if lowered.endswith('.jpg') or lowered.endswith('.jpeg'):
        return 'image/jpeg'
    return None


def _list_gallery_images():
    gallery_root = app.config['GALLERY_ROOT']
    return [
        name
        for name in os.listdir(gallery_root)
        if allowed_file(name)
        and is_safe_path(gallery_root, os.path.join(gallery_root, name))
    ]


@app.route('/')
def index():
    images = []
    try:
        images = _list_gallery_images()
    except Exception as e:
        app.logger.error(f'Error listing images: {e}')
    return render_template('gallery.html', images=images)


@app.route('/image/<path:filename>')
def get_image(filename):
    try:
        if not allowed_file(filename):
            abort(400, 'Invalid file type')

        gallery_root = app.config['GALLERY_ROOT']
        safe_filename = secure_filename(filename)
        image_path = os.path.join(gallery_root, safe_filename)

        if not is_safe_path(gallery_root, image_path):
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
    return (render_template('error.html', error='Image not found'), 404)


@app.errorhandler(400)
def bad_request(e):
    return (render_template('error.html', error='Invalid request'), 400)


@app.errorhandler(403)
def forbidden(e):
    return (render_template('error.html', error='Access denied'), 403)


@app.errorhandler(500)
def server_error(e):
    return (render_template('error.html', error='Internal server error'), 500)


def _create_sample_gallery():
    gallery_root = app.config['GALLERY_ROOT']
    os.makedirs(gallery_root, mode=GALLERY_DIR_MODE)
    for image_name in SAMPLE_IMAGES:
        try:
            with open(os.path.join(gallery_root, image_name), 'wb'):
                pass
        except Exception as e:
            app.logger.error(f'Error creating sample image: {e}')


if __name__ == '__main__':
    if not os.path.exists(app.config['GALLERY_ROOT']):
        _create_sample_gallery()
    app.run(port=5000)
