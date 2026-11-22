import os

from flask import Flask, send_file, render_template, abort

app = Flask(__name__)
app.config['GALLERY_ROOT'] = os.path.join(os.path.dirname(__file__), 'gallery')

IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg')
SAMPLE_IMAGES = ('image1.jpg', 'image2.png', 'image3.jpeg')


def _list_images():
    """Return image filenames in the gallery root, or an empty list on any error."""
    try:
        return [
            name for name in os.listdir(app.config['GALLERY_ROOT'])
            if name.lower().endswith(IMAGE_EXTENSIONS)
        ]
    except Exception:
        return []


def _ensure_gallery_exists():
    """Create the gallery directory with placeholder images if it is missing."""
    root = app.config['GALLERY_ROOT']
    if os.path.exists(root):
        return
    os.makedirs(root)
    for name in SAMPLE_IMAGES:
        open(os.path.join(root, name), 'w').close()


@app.route('/')
def index():
    return render_template('gallery.html', images=_list_images())


@app.route('/image/<path:filename>')
def get_image(filename):
    try:
        image_path = os.path.join(app.config['GALLERY_ROOT'], filename)
        # Note: these aborts are raised inside the try block, so the generic
        # handler below converts them into a 500 response (original behaviour).
        if not os.path.exists(image_path):
            abort(404)
        if not os.path.isfile(image_path):
            abort(400, 'Requested path is not a file')
        return send_file(image_path, mimetype='image/jpeg')
    except Exception as e:
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
    _ensure_gallery_exists()
    app.run(debug=True, port=5000)
