import os

from flask import (
    Flask,
    abort,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
UPLOAD_FOLDER_NAME = 'documents'
DEFAULT_UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), UPLOAD_FOLDER_NAME)
DEFAULT_ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx'}

UPLOAD_FIELD_NAME = 'file'
SAMPLE_DOCUMENTS = ['sample1.txt', 'sample2.pdf', 'sample3.docx']

INDEX_TEMPLATE = 'index.html'
ERROR_TEMPLATE = 'error.html'
INTERNAL_ERROR_MESSAGE = 'Internal server error'

DEV_SERVER_PORT = 5001
DEV_SERVER_DEBUG = True


# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = DEFAULT_UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = set(DEFAULT_ALLOWED_EXTENSIONS)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _upload_folder():
    return app.config['UPLOAD_FOLDER']


def _document_path(filename):
    return os.path.join(_upload_folder(), filename)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def _list_documents():
    """Return names of regular files in the upload folder (empty on any error)."""
    try:
        return [
            name for name in os.listdir(_upload_folder())
            if os.path.isfile(_document_path(name))
        ]
    except Exception:
        return []


def _redirect_to_index():
    return redirect(url_for('index'))


def _render_error(message, status_code):
    return (render_template(ERROR_TEMPLATE, error=message), status_code)


def _locate_document(document_id):
    """Resolve a document path, aborting if it is missing or not a file."""
    doc_path = _document_path(document_id)
    if not os.path.exists(doc_path):
        abort(404, 'Document not found')
    if not os.path.isfile(doc_path):
        abort(400, 'Requested path is not a file')
    return doc_path


def _create_sample_documents():
    for doc in SAMPLE_DOCUMENTS:
        open(_document_path(doc), 'w').close()


def _initialize_upload_folder():
    """Create the upload folder (with sample documents) if it does not exist."""
    if not os.path.exists(_upload_folder()):
        os.makedirs(_upload_folder())
        _create_sample_documents()


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/')
def index():
    documents = _list_documents()
    return render_template(INDEX_TEMPLATE, documents=documents)


@app.route('/upload', methods=['POST'])
def upload_file():
    if UPLOAD_FIELD_NAME not in request.files:
        return _redirect_to_index()
    file = request.files[UPLOAD_FIELD_NAME]
    if file.filename == '':
        return _redirect_to_index()
    if file and allowed_file(file.filename):
        filename = file.filename
        file.save(_document_path(filename))
    return _redirect_to_index()


@app.route('/download/<document_id>')
def download_document(document_id):
    try:
        doc_path = _locate_document(document_id)
        return send_file(doc_path, as_attachment=True)
    except Exception as e:
        # Note: this intentionally also catches the HTTP aborts raised above,
        # preserving the original behaviour.
        abort(500, str(e))


# --------------------------------------------------------------------------- #
# Error handlers
# --------------------------------------------------------------------------- #
@app.errorhandler(404)
def not_found(e):
    return _render_error(str(e), 404)


@app.errorhandler(400)
def bad_request(e):
    return _render_error(str(e), 400)


@app.errorhandler(500)
def server_error(e):
    return _render_error(INTERNAL_ERROR_MESSAGE, 500)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main():
    _initialize_upload_folder()
    app.run(debug=DEV_SERVER_DEBUG, port=DEV_SERVER_PORT)


if __name__ == '__main__':
    main()
