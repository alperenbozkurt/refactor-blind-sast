"""Document upload/download Flask application.

Behaviour is identical to the original module; the code has been reorganised
into named constants, small helper functions and a thin entrypoint so it is
easier to maintain in a larger codebase.
"""

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

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

UPLOAD_DIRNAME = 'documents'
ALLOWED_EXTENSIONS = frozenset({'txt', 'pdf', 'doc', 'docx'})
SAMPLE_DOCUMENTS = ('sample1.txt', 'sample2.pdf', 'sample3.docx')

INDEX_TEMPLATE = 'index.html'
ERROR_TEMPLATE = 'error.html'

MSG_DOCUMENT_NOT_FOUND = 'Document not found'
MSG_PATH_NOT_FILE = 'Requested path is not a file'
MSG_INTERNAL_ERROR = 'Internal server error'

SERVER_DEBUG = True
SERVER_PORT = 5001

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), UPLOAD_DIRNAME)
app.config['ALLOWED_EXTENSIONS'] = ALLOWED_EXTENSIONS


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _upload_folder_path():
    """Return the configured upload folder."""
    return app.config['UPLOAD_FOLDER']


def _file_extension(filename):
    """Return the lowercased extension of ``filename`` (assumes one exists)."""
    return filename.rsplit('.', 1)[1].lower()


def _list_documents(folder):
    """Return the regular files in ``folder``, or an empty list on failure."""
    try:
        return [
            entry
            for entry in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, entry))
        ]
    except Exception:
        return []


def _redirect_to_index():
    """Redirect back to the document listing page."""
    return redirect(url_for('index'))


def _render_error_page(message, status_code):
    """Render the shared error template with the given status code."""
    return (render_template(ERROR_TEMPLATE, error=message), status_code)


def _resolve_document_path(document_id):
    """Return the on-disk path for ``document_id`` or abort with an error."""
    doc_path = os.path.join(_upload_folder_path(), document_id)
    if not os.path.exists(doc_path):
        abort(404, MSG_DOCUMENT_NOT_FOUND)
    if not os.path.isfile(doc_path):
        abort(400, MSG_PATH_NOT_FILE)
    return doc_path


def _create_sample_documents(folder):
    """Create the empty sample documents shipped with a fresh upload folder."""
    for name in SAMPLE_DOCUMENTS:
        open(os.path.join(folder, name), 'w').close()


def _ensure_upload_folder(folder):
    """Create the upload folder (and sample docs) if it does not exist yet."""
    if not os.path.exists(folder):
        os.makedirs(folder)
        _create_sample_documents(folder)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def allowed_file(filename):
    return '.' in filename and _file_extension(filename) in app.config['ALLOWED_EXTENSIONS']


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    documents = _list_documents(_upload_folder_path())
    return render_template(INDEX_TEMPLATE, documents=documents)


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return _redirect_to_index()
    file = request.files['file']
    if file.filename == '':
        return _redirect_to_index()
    if file and allowed_file(file.filename):
        file.save(os.path.join(_upload_folder_path(), file.filename))
    return _redirect_to_index()


@app.route('/download/<document_id>')
def download_document(document_id):
    try:
        doc_path = _resolve_document_path(document_id)
        return send_file(doc_path, as_attachment=True)
    except Exception as e:
        abort(500, str(e))


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return _render_error_page(str(e), 404)


@app.errorhandler(400)
def bad_request(e):
    return _render_error_page(str(e), 400)


@app.errorhandler(500)
def server_error(e):
    return _render_error_page(MSG_INTERNAL_ERROR, 500)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    _ensure_upload_folder(app.config['UPLOAD_FOLDER'])
    app.run(debug=SERVER_DEBUG, port=SERVER_PORT)
