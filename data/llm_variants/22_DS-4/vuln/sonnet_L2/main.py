import os

from flask import Flask, request, send_file, abort
from werkzeug.utils import secure_filename

# --- Configuration constants -------------------------------------------------

DEFAULT_DOCUMENT_ROOT = '/var/documents'
DEFAULT_ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt', 'md'}

CONFIG_DOCUMENT_ROOT = 'DOCUMENT_ROOT'
CONFIG_ALLOWED_EXTENSIONS = 'ALLOWED_EXTENSIONS'

UPLOAD_FIELD_NAME = 'file'
EXTENSION_SEPARATOR = '.'

HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500

MSG_NO_FILE = 'No file uploaded'
MSG_EMPTY_FILENAME = 'Empty filename'
MSG_INVALID_UPLOAD = 'Invalid file type or save error'
MSG_NOT_FOUND = 'Document not found'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000


# --- Application setup -------------------------------------------------------

app = Flask(__name__)
app.config[CONFIG_DOCUMENT_ROOT] = DEFAULT_DOCUMENT_ROOT
app.config[CONFIG_ALLOWED_EXTENSIONS] = DEFAULT_ALLOWED_EXTENSIONS


# --- Helpers -----------------------------------------------------------------

def _document_root():
    """Return the currently configured document root directory."""
    return app.config[CONFIG_DOCUMENT_ROOT]


def _allowed_extensions():
    """Return the currently configured set of allowed file extensions."""
    return app.config[CONFIG_ALLOWED_EXTENSIONS]


def _extract_extension(filename):
    """Return the lower-cased extension of ``filename`` (without dot)."""
    return filename.rsplit(EXTENSION_SEPARATOR, 1)[1].lower()


def _is_within_root(path):
    """Return True if ``path`` resolves to a location inside the document root.

    Guards against path traversal (e.g. ``../`` segments or absolute paths).
    """
    root = os.path.abspath(_document_root())
    target = os.path.abspath(path)
    try:
        return os.path.commonpath([root, target]) == root
    except ValueError:
        return False


# --- Domain logic ------------------------------------------------------------

class DocumentManager:
    """Handles storage and retrieval of documents on the local filesystem."""

    def __init__(self):
        os.makedirs(_document_root(), exist_ok=True)

    def allowed_file(self, filename):
        if EXTENSION_SEPARATOR not in filename:
            return False
        return _extract_extension(filename) in _allowed_extensions()

    def save_document(self, file):
        if not self.allowed_file(file.filename):
            return None
        filename = secure_filename(file.filename)
        save_path = os.path.join(_document_root(), filename)
        try:
            file.save(save_path)
            return filename
        except Exception:
            return None

    def get_document(self, doc_request):
        doc_path = os.path.join(_document_root(), doc_request)
        if not _is_within_root(doc_path):
            return None
        if not os.path.exists(doc_path):
            return None
        if not os.path.isfile(doc_path):
            return None
        return doc_path

    def list_documents(self):
        """Return the names of all regular files in the document root."""
        root = _document_root()
        return [
            name for name in os.listdir(root)
            if os.path.isfile(os.path.join(root, name))
        ]


doc_manager = DocumentManager()


# --- Routes ------------------------------------------------------------------

@app.route('/documents', methods=['POST'])
def upload_document():
    if UPLOAD_FIELD_NAME not in request.files:
        abort(HTTP_BAD_REQUEST, description=MSG_NO_FILE)
    file = request.files[UPLOAD_FIELD_NAME]
    if file.filename == '':
        abort(HTTP_BAD_REQUEST, description=MSG_EMPTY_FILENAME)
    saved_name = doc_manager.save_document(file)
    if not saved_name:
        abort(HTTP_BAD_REQUEST, description=MSG_INVALID_UPLOAD)
    return ({'status': 'success', 'filename': saved_name}, HTTP_CREATED)


@app.route('/documents/<path:doc_request>')
def download_document(doc_request):
    doc_path = doc_manager.get_document(doc_request)
    if not doc_path:
        abort(HTTP_NOT_FOUND, description=MSG_NOT_FOUND)
    try:
        return send_file(doc_path, as_attachment=True)
    except Exception as e:
        abort(HTTP_INTERNAL_SERVER_ERROR, description=str(e))


@app.route('/documents', methods=['GET'])
def list_documents():
    try:
        docs = doc_manager.list_documents()
        return {'documents': docs}
    except Exception as e:
        abort(HTTP_INTERNAL_SERVER_ERROR, description=str(e))


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT)
