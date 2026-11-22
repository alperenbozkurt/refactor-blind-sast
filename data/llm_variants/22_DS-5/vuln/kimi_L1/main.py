"""A small Flask service for uploading images and generating thumbnails."""

import hashlib
import io  # noqa: F401  (unused, but kept to preserve the original module namespace)
import os

from flask import Flask, abort, request, send_file
from PIL import Image
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['IMAGE_UPLOAD_FOLDER'] = './uploads'
app.config['THUMBNAIL_FOLDER'] = './thumbnails'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}


def allowed_file(filename):
    """Return True if *filename* has an allowed image extension."""
    if '.' not in filename:
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in app.config['ALLOWED_EXTENSIONS']


def ensure_directories():
    """Create the upload and thumbnail directories if they do not exist."""
    folders = (app.config['IMAGE_UPLOAD_FOLDER'], app.config['THUMBNAIL_FOLDER'])
    for folder in folders:
        os.makedirs(folder, exist_ok=True)


def generate_thumbnail(source_path, size=(128, 128)):
    """Generate a JPEG thumbnail for the image at *source_path*.

    The thumbnail file is named after the MD5 hex digest of *source_path*.
    Return the thumbnail path, or None if generation failed.
    """
    try:
        with Image.open(source_path) as img:
            img.thumbnail(size)
            thumb_filename = f'{hashlib.md5(source_path.encode()).hexdigest()}.jpg'
            thumb_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumb_filename)
            img.save(thumb_path, 'JPEG')
            return thumb_path
    except Exception as e:
        print(f'Error generating thumbnail: {e}')
        return None


@app.route('/upload', methods=['POST'])
def upload_image():
    """Validate and store an uploaded image file."""
    if 'file' not in request.files:
        abort(400, description='No file part')
    file = request.files['file']
    if file.filename == '':
        abort(400, description='No selected file')
    if not allowed_file(file.filename):
        abort(400, description='File type not allowed')
    filename = secure_filename(file.filename)
    save_path = os.path.join(app.config['IMAGE_UPLOAD_FOLDER'], filename)
    file.save(save_path)
    return ({'status': 'success', 'path': save_path}, 201)


@app.route('/thumbnail', methods=['POST'])
def create_thumbnail():
    """Generate a thumbnail for the image path given in the JSON body."""
    data = request.get_json()
    if not data or 'image_path' not in data:
        abort(400, description='No image path provided')
    thumb_path = generate_thumbnail(data['image_path'])
    if not thumb_path:
        abort(500, description='Failed to generate thumbnail')
    return {'status': 'success', 'thumbnail_path': thumb_path}


@app.route('/thumbnail/<path:thumb_path>')
def get_thumbnail(thumb_path):
    """Serve a previously generated thumbnail as a JPEG image."""
    try:
        full_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumb_path)
        if not os.path.exists(full_path):
            abort(404)
        return send_file(full_path, mimetype='image/jpeg')
    except Exception as e:
        # Any failure here, including the 404 raised above, becomes a 500.
        abort(500, description=str(e))


@app.route('/cleanup', methods=['POST'])
def cleanup_files():
    """Delete every file in the upload and thumbnail folders."""
    try:
        folders = (
            app.config['IMAGE_UPLOAD_FOLDER'],
            app.config['THUMBNAIL_FOLDER'],
        )
        for folder in folders:
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    print(f'Error deleting {file_path}: {e}')
        return ({'status': 'success'}, 200)
    except Exception as e:
        abort(500, description=str(e))


if __name__ == '__main__':
    ensure_directories()
    app.run(host='0.0.0.0', port=5000, debug=True)
