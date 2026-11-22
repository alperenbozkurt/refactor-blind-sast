import os
import uuid
import zipfile
from datetime import datetime

from flask import Flask, request, jsonify, send_file

app = Flask(__name__)
app.config['ARCHIVE_DIR'] = '/var/archives'
app.config['DOCUMENT_STORAGE'] = '/var/documents'
app.config['MAX_ARCHIVE_SIZE'] = 100 * 1024 * 1024


def _error_response(message, status):
    return jsonify({'error': message}), status


class DocumentArchiver:

    def __init__(self):
        os.makedirs(app.config['ARCHIVE_DIR'], exist_ok=True)
        os.makedirs(app.config['DOCUMENT_STORAGE'], exist_ok=True)

    def validate_document_path(self, doc_path):
        return os.path.exists(doc_path)

    @staticmethod
    def _add_to_zip(zipf, doc_path):
        if os.path.isfile(doc_path):
            zipf.write(doc_path, os.path.basename(doc_path))
        elif os.path.isdir(doc_path):
            base_dir = os.path.dirname(doc_path)
            for root, _, files in os.walk(doc_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.relpath(file_path, base_dir))

    def archive_document(self, doc_path, compression_level=6):
        if not self.validate_document_path(doc_path):
            return None

        archive_name = f'doc_archive_{uuid.uuid4().hex}.zip'
        archive_path = os.path.join(app.config['ARCHIVE_DIR'], archive_name)

        try:
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED,
                                 compresslevel=compression_level) as zipf:
                self._add_to_zip(zipf, doc_path)

            if os.path.getsize(archive_path) > app.config['MAX_ARCHIVE_SIZE']:
                os.remove(archive_path)
                return None
            return archive_path
        except Exception as e:
            print(f'Archive failed: {str(e)}')
            if os.path.exists(archive_path):
                os.remove(archive_path)
            return None

    def cleanup_old_archives(self, max_age_days=30):
        now = datetime.now()
        archive_dir = app.config['ARCHIVE_DIR']
        for archive in os.listdir(archive_dir):
            archive_path = os.path.join(archive_dir, archive)
            if not os.path.isfile(archive_path):
                continue
            mtime = datetime.fromtimestamp(os.path.getmtime(archive_path))
            if (now - mtime).days > max_age_days:
                try:
                    os.remove(archive_path)
                except Exception as e:
                    print(f'Failed to remove old archive: {str(e)}')


archiver = DocumentArchiver()


@app.route('/archive', methods=['POST'])
def create_archive():
    data = request.get_json()
    if not data or 'document_path' not in data:
        return _error_response('Missing document_path', 400)

    compression = data.get('compression_level', 6)
    archive_path = archiver.archive_document(data['document_path'], compression)
    if archive_path:
        return jsonify({
            'status': 'success',
            'archive_path': os.path.basename(archive_path),
        }), 201
    return _error_response('Archive creation failed', 500)


@app.route('/archive/<archive_name>', methods=['GET'])
def download_archive(archive_name):
    archive_path = os.path.join(app.config['ARCHIVE_DIR'], archive_name)
    if not os.path.exists(archive_path):
        return _error_response('Archive not found', 404)
    try:
        return send_file(archive_path, as_attachment=True)
    except Exception as e:
        return _error_response(str(e), 500)


@app.route('/documents', methods=['GET'])
def list_documents():
    try:
        storage = app.config['DOCUMENT_STORAGE']
        docs = [
            os.path.relpath(os.path.join(root, file), storage)
            for root, _, files in os.walk(storage)
            for file in files
        ]
        return jsonify({'documents': docs})
    except Exception as e:
        return _error_response(str(e), 500)


@app.route('/cleanup', methods=['POST'])
def cleanup_archives():
    try:
        archiver.cleanup_old_archives()
        return jsonify({'status': 'success'})
    except Exception as e:
        return _error_response(str(e), 500)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
