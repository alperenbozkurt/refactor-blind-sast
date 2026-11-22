import os

from flask import (
    Flask,
    request,
    send_file,
    render_template,
    abort,
    redirect,
    url_for,
)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'documents')
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'pdf', 'doc', 'docx'}

SAMPLE_DOCUMENTS = ['sample1.txt', 'sample2.pdf', 'sample3.docx']


def allowed_file(filename):
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']
    )


def _upload_path(filename):
    return os.path.join(app.config['UPLOAD_FOLDER'], filename)


def _list_documents():
    folder = app.config['UPLOAD_FOLDER']
    try:
        return [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
    except Exception:
        return []


@app.route('/')
def index():
    return render_template('index.html', documents=_list_documents())


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' in request.files:
        file = request.files['file']
        if file.filename != '' and file and allowed_file(file.filename):
            file.save(_upload_path(file.filename))
    return redirect(url_for('index'))


@app.route('/download/<document_id>')
def download_document(document_id):
    try:
        doc_path = _upload_path(document_id)
        if not os.path.exists(doc_path):
            abort(404, 'Document not found')
        if not os.path.isfile(doc_path):
            abort(400, 'Requested path is not a file')
        return send_file(doc_path, as_attachment=True)
    except Exception as e:
        abort(500, str(e))


def _render_error(message, status):
    return (render_template('error.html', error=message), status)


@app.errorhandler(404)
def not_found(e):
    return _render_error(str(e), 404)


@app.errorhandler(400)
def bad_request(e):
    return _render_error(str(e), 400)


@app.errorhandler(500)
def server_error(e):
    return _render_error('Internal server error', 500)


def _initialize_upload_folder():
    folder = app.config['UPLOAD_FOLDER']
    if not os.path.exists(folder):
        os.makedirs(folder)
        for doc in SAMPLE_DOCUMENTS:
            open(os.path.join(folder, doc), 'w').close()


if __name__ == '__main__':
    _initialize_upload_folder()
    app.run(debug=True, port=5001)
