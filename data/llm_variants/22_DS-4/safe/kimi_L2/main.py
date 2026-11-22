"""Document storage web service.

A small Flask API for uploading, downloading and listing documents stored
under a configured document root.
"""

import os

from flask import Flask, abort, request, send_file
from werkzeug.utils import secure_filename


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class Config:
    """Flask application configuration."""

    DOCUMENT_ROOT = '/var/documents'
    ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt', 'md'}


class ServerConfig:
    """Network binding used when running the module directly."""

    HOST = '0.0.0.0'
    PORT = 5000


# HTTP status codes.
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_ERROR = 500
HTTP_CREATED = 201

# Response and error message strings.
STATUS_SUCCESS = 'success'
ERR_NO_FILE_UPLOADED = 'No file uploaded'
ERR_EMPTY_FILENAME = 'Empty filename'
ERR_INVALID_FILE = 'Invalid file type or save error'
ERR_DOCUMENT_NOT_FOUND = 'Document not found'

app = Flask(__name__)
app.config.from_object(Config)


# ---------------------------------------------------------------------------
# Document management
# ---------------------------------------------------------------------------

class DocumentManager:
    """Validates, stores and retrieves documents under the document root."""

    def __init__(self):
        os.makedirs(app.config['DOCUMENT_ROOT'], exist_ok=True)

    # -- internal helpers --------------------------------------------------

    @staticmethod
    def _document_path(filename):
        """Return the path of *filename* inside the document root."""
        return os.path.join(app.config['DOCUMENT_ROOT'], filename)

    @staticmethod
    def _is_within_document_root(path):
        """Return True if *path* stays inside the document root."""
        root_prefix = os.path.abspath(app.config['DOCUMENT_ROOT']) + os.sep
        return path.startswith(root_prefix)

    @staticmethod
    def _extension(filename):
        """Return the lower-cased extension of *filename*."""
        return filename.rsplit('.', 1)[1].lower()

    # -- public API --------------------------------------------------------

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
        filename = secure_filename(doc_request)
        if not filename:
            return None
        doc_path = os.path.normpath(self._document_path(filename))
        if not self._is_within_document_root(doc_path):
            return None
        if not os.path.exists(doc_path):
            return None
        if not os.path.isfile(doc_path):
            return None
        return doc_path


doc_manager = DocumentManager()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _list_document_files():
    """Return the names of all regular files in the document root."""
    root = app.config['DOCUMENT_ROOT']
    return [
        name
        for name in os.listdir(root)
        if os.path.isfile(os.path.join(root, name))
    ]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/documents', methods=['POST'])
def upload_document():
    if 'file' not in request.files:
        abort(HTTP_BAD_REQUEST, description=ERR_NO_FILE_UPLOADED)
    file = request.files['file']
    if file.filename == '':
        abort(HTTP_BAD_REQUEST, description=ERR_EMPTY_FILENAME)
    saved_name = doc_manager.save_document(file)
    if not saved_name:
        abort(HTTP_BAD_REQUEST, description=ERR_INVALID_FILE)
    return ({'status': STATUS_SUCCESS, 'filename': saved_name}, HTTP_CREATED)


@app.route('/documents/<path:doc_request>')
def download_document(doc_request):
    doc_path = doc_manager.get_document(doc_request)
    if not doc_path:
        abort(HTTP_NOT_FOUND, description=ERR_DOCUMENT_NOT_FOUND)
    try:
        return send_file(doc_path, as_attachment=True)
    except Exception as e:
        abort(HTTP_INTERNAL_ERROR, description=str(e))


@app.route('/documents', methods=['GET'])
def list_documents():
    try:
        return {'documents': _list_document_files()}
    except Exception as e:
        abort(HTTP_INTERNAL_ERROR, description=str(e))


# ---------------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    app.run(host=ServerConfig.HOST, port=ServerConfig.PORT)
