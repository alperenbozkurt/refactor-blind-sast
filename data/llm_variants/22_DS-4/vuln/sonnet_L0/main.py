import os

from flask import Flask, request, send_file, abort
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['DOCUMENT_ROOT'] = '/var/documents'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'docx', 'txt', 'md'}


def _document_root():
    return app.config['DOCUMENT_ROOT']


class DocumentManager:

    def __init__(self):
        os.makedirs(_document_root(), exist_ok=True)

    def allowed_file(self, filename):
        if '.' not in filename:
            return False
        extension = filename.rsplit('.', 1)[1].lower()
        return extension in app.config['ALLOWED_EXTENSIONS']

    def save_document(self, file):
        if not self.allowed_file(file.filename):
            return None
        filename = secure_filename(file.filename)
        save_path = os.path.join(_document_root(), filename)
        try:
            file.save(save_path)
        except Exception:
            return None
        return filename

    def get_document(self, doc_request):
        root = os.path.abspath(_document_root())
        doc_path = os.path.abspath(os.path.join(root, doc_request))
        # Ensure the requested path stays within the document root
        # (guards against path traversal).
        if os.path.commonpath([root, doc_path]) != root:
            return None
        if not os.path.isfile(doc_path):
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
    return ({'status': 'success', 'filename': saved_name}, 201)


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
        root = _document_root()
        docs = [
            name for name in os.listdir(root)
            if os.path.isfile(os.path.join(root, name))
        ]
        return {'documents': docs}
    except Exception as e:
        abort(500, description=str(e))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
