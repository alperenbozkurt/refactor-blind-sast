"""A small Flask application for uploading and downloading documents."""

import os

from flask import Flask, abort, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'documents')
)
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'pdf', 'doc', 'docx'}
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024


def allowed_file(filename):
    """Return True if *filename* has an allowed extension."""
    if not filename or '.' not in filename:
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in app.config['ALLOWED_EXTENSIONS']


def is_safe_path(base_path, requested_path):
    """Return True if *requested_path* is located inside *base_path*."""
    base_path = os.path.abspath(base_path)
    requested_path = os.path.abspath(requested_path)
    return requested_path.startswith(base_path + os.sep)


@app.route('/')
def index():
    """Render the index page with the list of stored documents."""
    documents = []
    try:
        upload_folder = app.config['UPLOAD_FOLDER']
        documents = [
            name
            for name in os.listdir(upload_folder)
            if os.path.isfile(os.path.join(upload_folder, name))
            and allowed_file(name)
        ]
    except Exception as e:
        app.logger.error(f'Error listing documents: {e}')
    return render_template('index.html', documents=documents)


@app.route('/upload', methods=['POST'])
def upload_file():
    """Save an uploaded document and redirect back to the index page."""
    if 'file' not in request.files:
        return redirect(url_for('index'))

    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('index'))

    if file and allowed_file(file.filename):
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

    return redirect(url_for('index'))


@app.route('/download/<document_id>')
def download_document(document_id):
    """Send the requested document to the client as an attachment."""
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
    """Render the error page for missing documents."""
    return render_template('error.html', error='Document not found'), 404


@app.errorhandler(400)
def bad_request(e):
    """Render the error page for invalid requests."""
    return render_template('error.html', error='Invalid request'), 400


@app.errorhandler(403)
def forbidden(e):
    """Render the error page for forbidden access."""
    return render_template('error.html', error='Access denied'), 403


@app.errorhandler(500)
def server_error(e):
    """Render the error page for internal server errors."""
    return render_template('error.html', error='Internal server error'), 500


if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'], mode=0o750)
        sample_docs = ['sample1.txt', 'sample2.pdf', 'sample3.docx']
        for doc in sample_docs:
            try:
                with open(os.path.join(app.config['UPLOAD_FOLDER'], doc), 'w'):
                    pass
            except Exception as e:
                app.logger.error(f'Error creating sample document: {e}')
    app.run(port=5001)
