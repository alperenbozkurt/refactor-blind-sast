import os

from flask import Flask, abort, render_template, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['GALLERY_ROOT'] = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'gallery')
)
app.config['ALLOWED_EXTENSIONS'] = {'.png', '.jpg', '.jpeg'}


def is_safe_path(base_path, requested_path):
    """Return True only when requested_path lies strictly inside base_path."""
    base_path = os.path.abspath(base_path)
    requested_path = os.path.abspath(requested_path)
    return requested_path.startswith(base_path + os.sep)


def allowed_file(filename):
    """Return True when filename has one of the configured extensions."""
    if '.' not in filename:
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in {ext[1:] for ext in app.config['ALLOWED_EXTENSIONS']}


def _mimetype_for(filename):
    """Return the MIME type matching filename's extension, or None."""
    lowered = filename.lower()
    if lowered.endswith('.png'):
        return 'image/png'
    if lowered.endswith(('.jpg', '.jpeg')):
        return 'image/jpeg'
    return None


@app.route('/')
def index():
    images = []
    try:
        gallery_root = app.config['GALLERY_ROOT']
        images = [
            filename
            for filename in os.listdir(gallery_root)
            if allowed_file(filename)
            and is_safe_path(gallery_root, os.path.join(gallery_root, filename))
        ]
    except Exception as e:
        app.logger.error(f'Error listing images: {e}')
    return render_template('gallery.html', images=images)


@app.route('/image/<path:filename>')
def get_image(filename):
    try:
        if not allowed_file(filename):
            abort(400, 'Invalid file type')

        gallery_root = app.config['GALLERY_ROOT']
        image_path = os.path.join(gallery_root, secure_filename(filename))

        if not is_safe_path(gallery_root, image_path):
            abort(403, 'Access denied')
        if not os.path.exists(image_path):
            abort(404)
        if not os.path.isfile(image_path):
            abort(400, 'Requested path is not a file')

        return send_file(image_path, mimetype=_mimetype_for(filename))
    except Exception as e:
        # Deliberately catches everything raised above, including the HTTP
        # exceptions produced by abort(), and reports them as a 500.
        app.logger.error(f'Error serving image: {e}')
        abort(500, 'Internal server error')


@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', error='Image not found'), 404


@app.errorhandler(400)
def bad_request(e):
    return render_template('error.html', error='Invalid request'), 400


@app.errorhandler(403)
def forbidden(e):
    return render_template('error.html', error='Access denied'), 403


@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', error='Internal server error'), 500


if __name__ == '__main__':
    if not os.path.exists(app.config['GALLERY_ROOT']):
        os.makedirs(app.config['GALLERY_ROOT'], mode=0o750)
        sample_images = ['image1.jpg', 'image2.png', 'image3.jpeg']
        for img in sample_images:
            try:
                with open(os.path.join(app.config['GALLERY_ROOT'], img), 'wb') as f:
                    pass
            except Exception as e:
                app.logger.error(f'Error creating sample image: {e}')
    app.run(port=5000)
