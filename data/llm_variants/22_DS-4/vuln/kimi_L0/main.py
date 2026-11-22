import os

from flask import Flask, abort, request, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['DOCUMENT_ROOT'] = '/var/documents'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'docx', 'txt', 'md'}


class DocumentManager:
    """Handles validation, storage, and retrieval of documents."""

    def __init__(self):
        os.makedirs(app.config['DOCUMENT_ROOT'], exist_ok=True)

    def allowed_file(self, filename):
        if '.' not in filename:
            return False
        extension = filename.rsplit('.', 1)[1].lower()
        return extension in app.config['ALLOWED_EXTENSIONS']

    def save_document(self, file):
        if not self.allowed_file(file.filename):
            return None
        filename = secure_filename(file.filename)
        save_path = os.path.join(app.config['DOCUMENT_ROOT'], filename)
        try:
            file.save(save_path)
        except Exception:
            return None
        return filename

    def get_document(self, doc_request):
        doc_path = os.path.join(app.config['DOCUMENT_ROOT'], doc_request)
        if not (os.path.exists(doc_path) and os.path.isfile(doc_path)):
            return None
        return doc_path


doc_manager = DocumentManager()


@app.route('/documents', methods=['POST'])
def upload_document():
    if 'file' not in request.files:
        abort(400, description='No file uploaded')
    file = request.files['file']
    if file.filename == '':
        abort(400, description='Empty filename')
    saved_name = doc_manager.save_document(file)
    if not saved_name:
        abort(400, description='Invalid file type or save error')
    return {'status': 'success', 'filename': saved_name}, 201


@app.route('/documents/<path:doc_request>')
def download_document(doc_request):
    doc_path = doc_manager.get_document(doc_request)
    if not doc_path:
        abort(404, description='Document not found')
    try:
        return send_file(doc_path, as_attachment=True)
    except Exception as e:
        abort(500, description=str(e))


@app.route('/documents', methods=['GET'])
def list_documents():
    try:
        root = app.config['DOCUMENT_ROOT']
        docs = [
            name
            for name in os.listdir(root)
            if os.path.isfile(os.path.join(root, name))
        ]
        return {'documents': docs}
    except Exception as e:
        abort(500, description=str(e))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
