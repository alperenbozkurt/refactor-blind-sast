"""Document store: a small Flask app for uploading and downloading documents."""

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
# Constants and configuration
# ---------------------------------------------------------------------------

INDEX_TEMPLATE = 'index.html'
ERROR_TEMPLATE = 'error.html'

UPLOAD_FOLDER_MODE = 0o750  # 488 decimal
SAMPLE_DOCUMENTS = ('sample1.txt', 'sample2.pdf', 'sample3.docx')
SERVER_PORT = 5001


class Config:
    """Configuration values loaded into the Flask application."""

    UPLOAD_FOLDER = os.path.abspath(
        os.path.join(os.path.dirname(__file__), 'documents')
    )
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx'}
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024


app = Flask(__name__)
app.config.from_object(Config)

# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------


def get_file_extension(filename):
    """Return the lowercase extension of *filename*, or None if it has none."""
    if not filename or '.' not in filename:
        return None
    return filename.rsplit('.', 1)[1].lower()


def allowed_file(filename):
    return get_file_extension(filename) in app.config['ALLOWED_EXTENSIONS']


def is_safe_path(base_path, requested_path):
    base_path = os.path.abspath(base_path)
    requested_path = os.path.abspath(requested_path)
    return requested_path.startswith(base_path + os.sep)


def build_upload_path(filename):
    """Return the absolute path of *filename* inside the upload folder."""
    return os.path.join(app.config['UPLOAD_FOLDER'], filename)


def list_uploaded_documents():
    """Return the names of all allowed files currently in the upload folder."""
    try:
        return [
            name
            for name in os.listdir(app.config['UPLOAD_FOLDER'])
            if os.path.isfile(build_upload_path(name)) and allowed_file(name)
        ]
    except Exception as e:
        app.logger.error(f'Error listing documents: {e}')
        return []


def get_request_file():
    """Return the file uploaded with the current request, or None."""
    if 'file' not in request.files:
        return None
    file = request.files['file']
    if file.filename == '':
        return None
    return file


def save_uploaded_file(file):
    """Validate and save an uploaded file into the upload folder."""
    filename = secure_filename(file.filename)
    file_path = build_upload_path(filename)
    if not is_safe_path(app.config['UPLOAD_FOLDER'], file_path):
        abort(403, 'Access denied')
    try:
        file.save(file_path)
    except Exception as e:
        app.logger.error(f'Error saving file: {e}')
        abort(500, 'Failed to save file')


def resolve_document_path(document_id):
    """Validate *document_id* and return its path inside the upload folder."""
    if not isinstance(document_id, str) or not document_id:
        abort(400, 'Invalid document ID')
    filename = secure_filename(document_id)
    if not allowed_file(filename):
        abort(400, 'Invalid file type')
    doc_path = build_upload_path(filename)
    if not is_safe_path(app.config['UPLOAD_FOLDER'], doc_path):
        abort(403, 'Access denied')
    if not os.path.exists(doc_path):
        abort(404, 'Document not found')
    if not os.path.isfile(doc_path):
        abort(400, 'Requested path is not a file')
    return doc_path


def render_error_page(message, status_code):
    """Render the shared error template for *status_code*."""
    return (render_template(ERROR_TEMPLATE, error=message), status_code)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route('/')
def index():
    documents = list_uploaded_documents()
    return render_template(INDEX_TEMPLATE, documents=documents)


@app.route('/upload', methods=['POST'])
def upload_file():
    file = get_request_file()
    if file is None:
        return redirect(url_for('index'))
    if allowed_file(file.filename):
        save_uploaded_file(file)
        return redirect(url_for('index'))
    return redirect(url_for('index'))


@app.route('/download/<document_id>')
def download_document(document_id):
    try:
        doc_path = resolve_document_path(document_id)
        return send_file(doc_path, as_attachment=True)
    except Exception as e:
        app.logger.error(f'Error downloading document: {e}')
        abort(500, 'Internal server error')


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------


@app.errorhandler(404)
def not_found(e):
    return render_error_page('Document not found', 404)


@app.errorhandler(400)
def bad_request(e):
    return render_error_page('Invalid request', 400)


@app.errorhandler(403)
def forbidden(e):
    return render_error_page('Access denied', 403)


@app.errorhandler(500)
def server_error(e):
    return render_error_page('Internal server error', 500)


# ---------------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------------


def create_sample_documents(upload_folder):
    """Create the empty sample documents shipped with the application."""
    for doc in SAMPLE_DOCUMENTS:
        try:
            with open(os.path.join(upload_folder, doc), 'w'):
                pass
        except Exception as e:
            app.logger.error(f'Error creating sample document: {e}')


def ensure_upload_folder():
    """Create the upload folder and its sample documents if missing."""
    upload_folder = app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder, mode=UPLOAD_FOLDER_MODE)
        create_sample_documents(upload_folder)


def main():
    ensure_upload_folder()
    app.run(port=SERVER_PORT)


if __name__ == '__main__':
    main()
