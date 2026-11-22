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

SAMPLE_DOCUMENTS = ['sample1.txt', 'sample2.pdf', 'sample3.docx']


def allowed_file(filename):
    if '.' not in filename:
        return False
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in app.config['ALLOWED_EXTENSIONS']


def _list_documents():
    """Return the names of all files in the upload folder (empty on any error)."""
    folder = app.config['UPLOAD_FOLDER']
    try:
        return [
            name for name in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, name))
        ]
    except Exception:
        return []


def _create_sample_documents():
    """Create the upload folder populated with empty sample documents."""
    folder = app.config['UPLOAD_FOLDER']
    os.makedirs(folder)
    for name in SAMPLE_DOCUMENTS:
        open(os.path.join(folder, name), 'w').close()


@app.route('/')
def index():
    return render_template('index.html', documents=_list_documents())


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' in request.files:
        file = request.files['file']
        if file.filename != '' and file and allowed_file(file.filename):
            filename = file.filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return redirect(url_for('index'))


@app.route('/download/<document_id>')
def download_document(document_id):
    try:
        doc_path = os.path.join(app.config['UPLOAD_FOLDER'], document_id)
        if not os.path.exists(doc_path):
            abort(404, 'Document not found')
        if not os.path.isfile(doc_path):
            abort(400, 'Requested path is not a file')
        return send_file(doc_path, as_attachment=True)
    except Exception as e:
        abort(500, str(e))


@app.errorhandler(404)
def not_found(e):
    return (render_template('error.html', error=str(e)), 404)


@app.errorhandler(400)
def bad_request(e):
    return (render_template('error.html', error=str(e)), 400)


@app.errorhandler(500)
def server_error(e):
    return (render_template('error.html', error='Internal server error'), 500)


if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        _create_sample_documents()
    app.run(debug=True, port=5001)
