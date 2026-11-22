"""Simple Flask application for uploading and downloading documents."""

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

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'documents')
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'pdf', 'doc', 'docx'}


def allowed_file(filename):
    """Return True if the filename has an allowed extension."""
    if '.' not in filename:
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in app.config['ALLOWED_EXTENSIONS']


@app.route('/')
def index():
    """Render the home page listing all uploaded documents."""
    upload_folder = app.config['UPLOAD_FOLDER']
    try:
        documents = [
            name
            for name in os.listdir(upload_folder)
            if os.path.isfile(os.path.join(upload_folder, name))
        ]
    except Exception:
        documents = []
    return render_template('index.html', documents=documents)


@app.route('/upload', methods=['POST'])
def upload_file():
    """Save an uploaded document, then redirect back to the home page."""
    if 'file' not in request.files:
        return redirect(url_for('index'))

    uploaded_file = request.files['file']
    if uploaded_file.filename == '':
        return redirect(url_for('index'))

    if uploaded_file and allowed_file(uploaded_file.filename):
        filename = uploaded_file.filename
        uploaded_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    return redirect(url_for('index'))


@app.route('/download/<document_id>')
def download_document(document_id):
    """Send the requested document to the client as an attachment."""
    try:
        doc_path = os.path.join(app.config['UPLOAD_FOLDER'], document_id)
        if not os.path.exists(doc_path):
            abort(404, 'Document not found')
        if not os.path.isfile(doc_path):
            abort(400, 'Requested path is not a file')
        return send_file(doc_path, as_attachment=True)
    except Exception as error:
        abort(500, str(error))


@app.errorhandler(404)
def not_found(e):
    """Render the error page for 404 responses."""
    return render_template('error.html', error=str(e)), 404


@app.errorhandler(400)
def bad_request(e):
    """Render the error page for 400 responses."""
    return render_template('error.html', error=str(e)), 400


@app.errorhandler(500)
def server_error(e):
    """Render a generic error page for 500 responses."""
    return render_template('error.html', error='Internal server error'), 500


if __name__ == '__main__':
    upload_folder = app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
        sample_docs = ['sample1.txt', 'sample2.pdf', 'sample3.docx']
        for doc in sample_docs:
            with open(os.path.join(upload_folder, doc), 'w'):
                pass
    app.run(debug=True, port=5001)
