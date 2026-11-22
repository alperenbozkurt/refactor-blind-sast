import os

from flask import Flask, abort, redirect, render_template, request, send_file, url_for

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'documents')
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'pdf', 'doc', 'docx'}


def allowed_file(filename):
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']
    )


@app.route('/')
def index():
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
    file = request.files.get('file')
    if file is None or file.filename == '':
        return redirect(url_for('index'))
    if allowed_file(file.filename):
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
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
    return render_template('error.html', error=str(e)), 404


@app.errorhandler(400)
def bad_request(e):
    return render_template('error.html', error=str(e)), 400


@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', error='Internal server error'), 500


if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
        sample_docs = ('sample1.txt', 'sample2.pdf', 'sample3.docx')
        for doc in sample_docs:
            with open(os.path.join(app.config['UPLOAD_FOLDER'], doc), 'w'):
                pass
    app.run(debug=True, port=5001)
