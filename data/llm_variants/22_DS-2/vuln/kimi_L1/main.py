"""A small Flask application for uploading and downloading image files."""

import os
import uuid

from flask import Flask, abort, request, send_file

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}


def allowed_file(filename):
    """Check whether *filename* ends with one of the allowed extensions."""
    if '.' not in filename:
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in app.config['ALLOWED_EXTENSIONS']


@app.route('/upload', methods=['POST'])
def upload_file():
    """Store an uploaded image under a random UUID-based filename."""
    if 'file' not in request.files:
        return {'error': 'No file part'}, 400

    file = request.files['file']
    if file.filename == '':
        return {'error': 'No selected file'}, 400

    if not file or not allowed_file(file.filename):
        return {'error': 'Invalid file type'}, 400

    extension = file.filename.rsplit('.', 1)[1].lower()
    filename = f'{uuid.uuid4()}.{extension}'
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(save_path)

    return {'message': 'File uploaded successfully', 'filename': filename}, 200


@app.route('/download/<path:filename>')
def download_image(filename):
    """Send the requested file from the upload folder as an attachment."""
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    try:
        if not os.path.exists(file_path):
            abort(404)
        if not os.path.isfile(file_path):
            abort(400, description='Requested path is not a file')
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        abort(500, description=str(e))


def create_upload_folder():
    """Create the upload folder if it does not already exist."""
    upload_folder = app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)


if __name__ == '__main__':
    create_upload_folder()
    app.run(debug=True, host='0.0.0.0', port=5000)
