"""Simple Flask image gallery application."""

import os

from flask import Flask, abort, render_template, send_file

app = Flask(__name__)
app.config['GALLERY_ROOT'] = os.path.join(os.path.dirname(__file__), 'gallery')

IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg')
SAMPLE_IMAGES = ('image1.jpg', 'image2.png', 'image3.jpeg')


@app.route('/')
def index():
    """Render the gallery page with the list of available images."""
    try:
        images = [
            filename
            for filename in os.listdir(app.config['GALLERY_ROOT'])
            if filename.lower().endswith(IMAGE_EXTENSIONS)
        ]
    except Exception:
        images = []
    return render_template('gallery.html', images=images)


@app.route('/image/<path:filename>')
def get_image(filename):
    """Serve an image file from the gallery directory."""
    # The broad ``except`` is deliberate: ``abort`` raises HTTP exceptions
    # (subclasses of ``Exception``), so the 404/400 aborts above are caught
    # here and re-raised as a 500. This mirrors the original behaviour.
    try:
        image_path = os.path.join(app.config['GALLERY_ROOT'], filename)
        if not os.path.exists(image_path):
            abort(404)
        if not os.path.isfile(image_path):
            abort(400, 'Requested path is not a file')
        return send_file(image_path, mimetype='image/jpeg')
    except Exception as e:
        abort(500, str(e))


@app.errorhandler(404)
def not_found(e):
    """Render the error page for missing resources."""
    return render_template('error.html', error='Image not found'), 404


@app.errorhandler(400)
def bad_request(e):
    """Render the error page for invalid requests."""
    return render_template('error.html', error=str(e)), 400


@app.errorhandler(500)
def server_error(e):
    """Render the error page for internal server errors."""
    return render_template('error.html', error='Server error'), 500


if __name__ == '__main__':
    gallery_root = app.config['GALLERY_ROOT']
    if not os.path.exists(gallery_root):
        os.makedirs(gallery_root)
        for sample_image in SAMPLE_IMAGES:
            open(os.path.join(gallery_root, sample_image), 'w').close()
    app.run(debug=True, port=5000)
