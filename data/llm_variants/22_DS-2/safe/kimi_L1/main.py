"""Minimal Flask service for uploading and downloading image files.

Uploaded files are stored under ``UPLOAD_FOLDER`` with a random UUID
name, keeping only the extensions listed in ``ALLOWED_EXTENSIONS``.
"""

import os
import uuid

from flask import Flask, abort, request, send_file

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}


def allowed_file(filename):
    """Return True if *filename* has an allowed extension."""
    if '.' not in filename:
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in app.config['ALLOWED_EXTENSIONS']


@app.route('/upload', methods=['POST'])
def upload_file():
    """Save the uploaded file under a random UUID-based name."""
    if 'file' not in request.files:
        return ({'error': 'No file part'}, 400)

    uploaded_file = request.files['file']
    if uploaded_file.filename == '':
        return ({'error': 'No selected file'}, 400)

    if uploaded_file and allowed_file(uploaded_file.filename):
        extension = uploaded_file.filename.rsplit('.', 1)[1].lower()
        filename = f'{uuid.uuid4()}.{extension}'
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        uploaded_file.save(save_path)
        return (
            {'message': 'File uploaded successfully', 'filename': filename},
            200,
        )

    return ({'error': 'Invalid file type'}, 400)


@app.route('/download/<path:filename>')
def download_image(filename):
    """Send the file *filename* from the upload folder as an attachment."""
    try:
        upload_dir = os.path.abspath(app.config['UPLOAD_FOLDER'])
        file_path = os.path.abspath(os.path.join(upload_dir, filename))

        if not file_path.startswith(upload_dir):
            abort(403, description='Access denied')
        if not os.path.exists(file_path):
            abort(404)
        if not os.path.isfile(file_path):
            abort(400, description='Requested path is not a file')
        if not allowed_file(filename):
            abort(400, description='Invalid file type')

        return send_file(file_path, as_attachment=True)
    except Exception as exc:
        abort(500, description=str(exc))


def create_upload_folder():
    """Create the upload folder if it does not exist yet."""
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])


if __name__ == '__main__':
    create_upload_folder()
    app.run(debug=False, host='0.0.0.0', port=5000)
