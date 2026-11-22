import os
import uuid

from flask import Flask, request, send_file, abort

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}


def _get_extension(filename):
    """Return the lower-cased extension after the last dot."""
    return filename.rsplit('.', 1)[1].lower()


def allowed_file(filename):
    return '.' in filename and _get_extension(filename) in app.config['ALLOWED_EXTENSIONS']


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return ({'error': 'No file part'}, 400)

    file = request.files['file']
    if file.filename == '':
        return ({'error': 'No selected file'}, 400)

    if file and allowed_file(file.filename):
        filename = '{}.{}'.format(uuid.uuid4(), _get_extension(file.filename))
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return ({'message': 'File uploaded successfully', 'filename': filename}, 200)

    return ({'error': 'Invalid file type'}, 400)


@app.route('/download/<path:filename>')
def download_image(filename):
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
    except Exception as e:
        abort(500, description=str(e))


def create_upload_folder():
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])


if __name__ == '__main__':
    create_upload_folder()
    app.run(debug=False, host='0.0.0.0', port=5000)
