"""Document storage web service.

A small Flask application for uploading, downloading and listing documents.
"""

import os

from flask import Flask, request, send_file, abort
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DOCUMENT_ROOT = '/var/documents'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt', 'md'}

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000

# HTTP status codes
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_ERROR = 500
HTTP_CREATED = 201

# Error messages
MSG_NO_FILE_UPLOADED = 'No file uploaded'
MSG_EMPTY_FILENAME = 'Empty filename'
MSG_INVALID_FILE = 'Invalid file type or save error'
MSG_DOCUMENT_NOT_FOUND = 'Document not found'

app = Flask(__name__)
app.config['DOCUMENT_ROOT'] = DOCUMENT_ROOT
app.config['ALLOWED_EXTENSIONS'] = ALLOWED_EXTENSIONS


class DocumentManager:
    """Handles validation, storage and retrieval of documents."""

    def __init__(self):
        self._ensure_document_root()

    @staticmethod
    def _ensure_document_root():
        os.makedirs(app.config['DOCUMENT_ROOT'], exist_ok=True)

    @staticmethod
    def _document_path(filename):
        return os.path.join(app.config['DOCUMENT_ROOT'], filename)

    @staticmethod
    def _extension(filename):
        return filename.rsplit('.', 1)[1].lower()

    def allowed_file(self, filename):
        return (
            '.' in filename
            and self._extension(filename) in app.config['ALLOWED_EXTENSIONS']
        )

    def save_document(self, file):
        if not self.allowed_file(file.filename):
            return None
        filename = secure_filename(file.filename)
        save_path = self._document_path(filename)
        try:
            file.save(save_path)
            return filename
        except Exception:
            return None

    def get_document(self, doc_request):
        doc_path = self._document_path(doc_request)
        if not os.path.exists(doc_path):
            return None
        if not os.path.isfile(doc_path):
            return None
        return doc_path

    def list_documents(self):
        root = app.config['DOCUMENT_ROOT']
        return [
            name
            for name in os.listdir(root)
            if os.path.isfile(os.path.join(root, name))
        ]


doc_manager = DocumentManager()


@app.route('/documents', methods=['POST'])
def upload_document():
    if 'file' not in request.files:
        abort(HTTP_BAD_REQUEST, description=MSG_NO_FILE_UPLOADED)
    file = request.files['file']
    if file.filename == '':
        abort(HTTP_BAD_REQUEST, description=MSG_EMPTY_FILENAME)
    saved_name = doc_manager.save_document(file)
    if not saved_name:
        abort(HTTP_BAD_REQUEST, description=MSG_INVALID_FILE)
    return {'status': 'success', 'filename': saved_name}, HTTP_CREATED


@app.route('/documents/<path:doc_request>')
def download_document(doc_request):
    doc_path = doc_manager.get_document(doc_request)
    if not doc_path:
        abort(HTTP_NOT_FOUND, description=MSG_DOCUMENT_NOT_FOUND)
    try:
        return send_file(doc_path, as_attachment=True)
    except Exception as e:
        abort(HTTP_INTERNAL_ERROR, description=str(e))


@app.route('/documents', methods=['GET'])
def list_documents():
    try:
        return {'documents': doc_manager.list_documents()}
    except Exception as e:
        abort(HTTP_INTERNAL_ERROR, description=str(e))


def main():
    app.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
