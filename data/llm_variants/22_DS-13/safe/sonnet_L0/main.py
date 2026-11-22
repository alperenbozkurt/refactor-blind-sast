import os

from flask import Flask, request, send_file, render_template, abort, redirect, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'documents')
)
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'pdf', 'doc', 'docx'}
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024


def allowed_file(filename):
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in app.config['ALLOWED_EXTENSIONS']


def is_safe_path(base_path, requested_path):
    base_path = os.path.abspath(base_path)
    requested_path = os.path.abspath(requested_path)
    return requested_path.startswith(base_path + os.sep)


def _list_documents():
    folder = app.config['UPLOAD_FOLDER']
    return [
        name for name in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, name)) and allowed_file(name)
    ]


def _error_page(message, status):
    return render_template('error.html', error=message), status


@app.route('/')
def index():
    documents = []
    try:
        documents = _list_documents()
    except Exception as e:
        app.logger.error(f'Error listing documents: {e}')
    return render_template('index.html', documents=documents)


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(url_for('index'))

    file = request.files['file']
    if file.filename == '' or not (file and allowed_file(file.filename)):
        return redirect(url_for('index'))

    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not is_safe_path(app.config['UPLOAD_FOLDER'], file_path):
        abort(403, 'Access denied')

    try:
        file.save(file_path)
        return redirect(url_for('index'))
    except Exception as e:
        app.logger.error(f'Error saving file: {e}')
        abort(500, 'Failed to save file')


@app.route('/download/<document_id>')
def download_document(document_id):
    # Note: aborts raised inside the try block are intentionally caught by the
    # generic handler and surface as a 500, preserving the original behaviour.
    try:
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

        return send_file(doc_path, as_attachment=True)
    except Exception as e:
        app.logger.error(f'Error downloading document: {e}')
        abort(500, 'Internal server error')


@app.errorhandler(404)
def not_found(e):
    return _error_page('Document not found', 404)


@app.errorhandler(400)
def bad_request(e):
    return _error_page('Invalid request', 400)


@app.errorhandler(403)
def forbidden(e):
    return _error_page('Access denied', 403)


@app.errorhandler(500)
def server_error(e):
    return _error_page('Internal server error', 500)


def _create_sample_documents():
    folder = app.config['UPLOAD_FOLDER']
    os.makedirs(folder, mode=0o750)
    for doc in ('sample1.txt', 'sample2.pdf', 'sample3.docx'):
        try:
            with open(os.path.join(folder, doc), 'w'):
                pass
        except Exception as e:
            app.logger.error(f'Error creating sample document: {e}')


if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        _create_sample_documents()
    app.run(port=5001)
