"""Simple document upload and download service built with Flask."""

import os

from flask import Flask, abort, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'documents')
)
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'pdf', 'doc', 'docx'}
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8 MB

_SAMPLE_DOCUMENTS = ('sample1.txt', 'sample2.pdf', 'sample3.docx')
_UPLOAD_FOLDER_MODE = 0o750


def allowed_file(filename):
    """Return True when *filename* carries one of the allowed extensions."""
    if not filename or '.' not in filename:
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in app.config['ALLOWED_EXTENSIONS']


def is_safe_path(base_path, requested_path):
    """Return True when *requested_path* resolves inside *base_path*."""
    base_path = os.path.abspath(base_path)
    requested_path = os.path.abspath(requested_path)
    return requested_path.startswith(base_path + os.sep)


def _list_uploaded_documents():
    """Return the names of the allowed files stored in the upload folder."""
    upload_folder = app.config['UPLOAD_FOLDER']
    return [
        name
        for name in os.listdir(upload_folder)
        if os.path.isfile(os.path.join(upload_folder, name)) and allowed_file(name)
    ]


def _resolve_document_path(document_id):
    """Validate *document_id* and return the path of the requested document."""
    if not isinstance(document_id, str) or not document_id:
        abort(400, 'Invalid document ID')
    filename = secure_filename(document_id)
    if not allowed_file(filename):
        abort(400, 'Invalid file type')
    doc_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not is_safe_path(app.config['UPLOAD_FOLDER'], doc_path):
        abort(403, 'Access denied')
    if not os.path.exists(doc_path):
        abort(404, 'Document not found')
    if not os.path.isfile(doc_path):
        abort(400, 'Requested path is not a file')
    return doc_path


@app.route('/')
def index():
    try:
        documents = _list_uploaded_documents()
    except Exception as e:
        app.logger.error(f'Error listing documents: {e}')
        documents = []
    return render_template('index.html', documents=documents)


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(url_for('index'))

    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('index'))

    if not (file and allowed_file(file.filename)):
        return redirect(url_for('index'))

    upload_folder = app.config['UPLOAD_FOLDER']
    filename = secure_filename(file.filename)
    file_path = os.path.join(upload_folder, filename)
    if not is_safe_path(upload_folder, file_path):
        abort(403, 'Access denied')
    try:
        file.save(file_path)
    except Exception as e:
        app.logger.error(f'Error saving file: {e}')
        abort(500, 'Failed to save file')
    return redirect(url_for('index'))


@app.route('/download/<document_id>')
def download_document(document_id):
    try:
        doc_path = _resolve_document_path(document_id)
        return send_file(doc_path, as_attachment=True)
    except Exception as e:
        app.logger.error(f'Error downloading document: {e}')
        abort(500, 'Internal server error')


def _render_error_page(message, status_code):
    """Render the shared error template with *message* and *status_code*."""
    return render_template('error.html', error=message), status_code


@app.errorhandler(404)
def not_found(e):
    return _render_error_page('Document not found', 404)


@app.errorhandler(400)
def bad_request(e):
    return _render_error_page('Invalid request', 400)


@app.errorhandler(403)
def forbidden(e):
    return _render_error_page('Access denied', 403)


@app.errorhandler(500)
def server_error(e):
    return _render_error_page('Internal server error', 500)


def _initialize_upload_folder():
    """Create the upload folder and populate it with empty sample documents."""
    os.makedirs(app.config['UPLOAD_FOLDER'], mode=_UPLOAD_FOLDER_MODE)
    for doc in _SAMPLE_DOCUMENTS:
        try:
            with open(os.path.join(app.config['UPLOAD_FOLDER'], doc), 'w'):
                pass
        except Exception as e:
            app.logger.error(f'Error creating sample document: {e}')


if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        _initialize_upload_folder()
    app.run(port=5001)
