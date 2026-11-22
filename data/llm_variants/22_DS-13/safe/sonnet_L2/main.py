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
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DOCUMENTS_DIRNAME = 'documents'
DEFAULT_ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx'}
DEFAULT_MAX_CONTENT_LENGTH = 8 * 1024 * 1024
UPLOAD_DIR_MODE = 0o750  # == 488
SAMPLE_DOCUMENTS = ['sample1.txt', 'sample2.pdf', 'sample3.docx']
SERVER_PORT = 5001

INDEX_TEMPLATE = 'index.html'
ERROR_TEMPLATE = 'error.html'

MSG_NOT_FOUND = 'Document not found'
MSG_BAD_REQUEST = 'Invalid request'
MSG_FORBIDDEN = 'Access denied'
MSG_SERVER_ERROR = 'Internal server error'


class Config:
    """Default application configuration."""

    UPLOAD_FOLDER = os.path.abspath(
        os.path.join(os.path.dirname(__file__), DOCUMENTS_DIRNAME)
    )
    ALLOWED_EXTENSIONS = DEFAULT_ALLOWED_EXTENSIONS
    MAX_CONTENT_LENGTH = DEFAULT_MAX_CONTENT_LENGTH


def configure_app(flask_app, config_class=Config):
    """Apply configuration values to the given Flask application."""
    flask_app.config['UPLOAD_FOLDER'] = config_class.UPLOAD_FOLDER
    flask_app.config['ALLOWED_EXTENSIONS'] = config_class.ALLOWED_EXTENSIONS
    flask_app.config['MAX_CONTENT_LENGTH'] = config_class.MAX_CONTENT_LENGTH


app = Flask(__name__)
configure_app(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def allowed_file(filename):
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in app.config['ALLOWED_EXTENSIONS']


def is_safe_path(base_path, requested_path):
    base_path = os.path.abspath(base_path)
    requested_path = os.path.abspath(requested_path)
    return requested_path.startswith(base_path + os.sep)


def _upload_folder():
    return app.config['UPLOAD_FOLDER']


def _document_path(filename):
    return os.path.join(_upload_folder(), filename)


def _list_documents():
    folder = _upload_folder()
    return [
        f for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f)) and allowed_file(f)
    ]


def _render_error(message, status_code):
    return (render_template(ERROR_TEMPLATE, error=message), status_code)


def _create_upload_folder_with_samples():
    """Create the upload folder (and sample documents) if it doesn't exist."""
    folder = _upload_folder()
    if os.path.exists(folder):
        return
    os.makedirs(folder, mode=UPLOAD_DIR_MODE)
    for doc in SAMPLE_DOCUMENTS:
        try:
            with open(os.path.join(folder, doc), 'w'):
                pass
        except Exception as e:
            app.logger.error(f'Error creating sample document: {e}')


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    documents = []
    try:
        documents = _list_documents()
    except Exception as e:
        app.logger.error(f'Error listing documents: {e}')
    return render_template(INDEX_TEMPLATE, documents=documents)


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(url_for('index'))
    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('index'))
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = _document_path(filename)
        if not is_safe_path(_upload_folder(), file_path):
            abort(403, 'Access denied')
        try:
            file.save(file_path)
            return redirect(url_for('index'))
        except Exception as e:
            app.logger.error(f'Error saving file: {e}')
            abort(500, 'Failed to save file')
    return redirect(url_for('index'))


@app.route('/download/<document_id>')
def download_document(document_id):
    try:
        if not isinstance(document_id, str) or not document_id:
            abort(400, 'Invalid document ID')
        filename = secure_filename(document_id)
        if not allowed_file(filename):
            abort(400, 'Invalid file type')
        doc_path = _document_path(filename)
        if not is_safe_path(_upload_folder(), doc_path):
            abort(403, 'Access denied')
        if not os.path.exists(doc_path):
            abort(404, 'Document not found')
        if not os.path.isfile(doc_path):
            abort(400, 'Requested path is not a file')
        return send_file(doc_path, as_attachment=True)
    except Exception as e:
        app.logger.error(f'Error downloading document: {e}')
        abort(500, 'Internal server error')


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return _render_error(MSG_NOT_FOUND, 404)


@app.errorhandler(400)
def bad_request(e):
    return _render_error(MSG_BAD_REQUEST, 400)


@app.errorhandler(403)
def forbidden(e):
    return _render_error(MSG_FORBIDDEN, 403)


@app.errorhandler(500)
def server_error(e):
    return _render_error(MSG_SERVER_ERROR, 500)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    _create_upload_folder_with_samples()
    app.run(port=SERVER_PORT)
