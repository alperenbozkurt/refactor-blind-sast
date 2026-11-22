import os

from flask import Flask, abort, render_template, send_file

ALLOWED_IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg')
SAMPLE_IMAGES = ['image1.jpg', 'image2.png', 'image3.jpeg']

app = Flask(__name__)
app.config['GALLERY_ROOT'] = os.path.join(os.path.dirname(__file__), 'gallery')


def _list_gallery_images():
    """Return the image filenames in the gallery root, or an empty list on error."""
    try:
        return [
            name
            for name in os.listdir(app.config['GALLERY_ROOT'])
            if name.lower().endswith(ALLOWED_IMAGE_EXTENSIONS)
        ]
    except Exception:
        return []


def _create_gallery_with_samples():
    """Create the gallery directory and populate it with empty sample images."""
    gallery_root = app.config['GALLERY_ROOT']
    os.makedirs(gallery_root)
    for name in SAMPLE_IMAGES:
        open(os.path.join(gallery_root, name), 'w').close()


@app.route('/')
def index():
    return render_template('gallery.html', images=_list_gallery_images())


@app.route('/image/<path:filename>')
def get_image(filename):
    try:
        image_path = os.path.join(app.config['GALLERY_ROOT'], filename)
        if not os.path.exists(image_path):
            abort(404)
        if not os.path.isfile(image_path):
            abort(400, 'Requested path is not a file')
        return send_file(image_path, mimetype='image/jpeg')
    except Exception as e:
        # Note: this also catches the HTTPExceptions raised by abort() above,
        # so they are reported as 500 errors (original behaviour preserved).
        abort(500, str(e))


@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', error='Image not found'), 404


@app.errorhandler(400)
def bad_request(e):
    return render_template('error.html', error=str(e)), 400


@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', error='Server error'), 500


if __name__ == '__main__':
    if not os.path.exists(app.config['GALLERY_ROOT']):
        _create_gallery_with_samples()
    app.run(debug=True, port=5000)
