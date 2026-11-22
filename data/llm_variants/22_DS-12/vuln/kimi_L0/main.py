"""Minimal Flask image gallery.

Lists the image files stored in the ``gallery`` directory located next to
this module and serves each of them under ``/image/<filename>``.
"""

import os

from flask import Flask, abort, render_template, send_file

IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg')

app = Flask(__name__)
app.config['GALLERY_ROOT'] = os.path.join(os.path.dirname(__file__), 'gallery')


@app.route('/')
def index():
    """Render the gallery page listing every image in the gallery folder."""
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
    """Serve the requested image file from the gallery folder."""
    try:
        image_path = os.path.join(app.config['GALLERY_ROOT'], filename)
        if not os.path.exists(image_path):
            abort(404)
        if not os.path.isfile(image_path):
            abort(400, 'Requested path is not a file')
        return send_file(image_path, mimetype='image/jpeg')
    except Exception as e:
        # abort() raises an HTTPException, which is itself an Exception, so
        # the 404 and 400 aborts above are also caught here and re-raised as
        # a 500. This catch-all behaviour is preserved from the original.
        abort(500, str(e))


@app.errorhandler(404)
def not_found(e):
    """Render the error page for missing images."""
    return (render_template('error.html', error='Image not found'), 404)


@app.errorhandler(400)
def bad_request(e):
    """Render the error page for invalid requests."""
    return (render_template('error.html', error=str(e)), 400)


@app.errorhandler(500)
def server_error(e):
    """Render the error page for unexpected failures."""
    return (render_template('error.html', error='Server error'), 500)


if __name__ == '__main__':
    if not os.path.exists(app.config['GALLERY_ROOT']):
        os.makedirs(app.config['GALLERY_ROOT'])
        sample_images = ['image1.jpg', 'image2.png', 'image3.jpeg']
        for img in sample_images:
            with open(os.path.join(app.config['GALLERY_ROOT'], img), 'w'):
                pass
    app.run(debug=True, port=5000)
