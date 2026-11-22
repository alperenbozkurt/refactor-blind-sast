import os
import zipfile
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['ARCHIVE_DIR'] = os.path.abspath('/var/archives')
app.config['DOCUMENT_STORAGE'] = os.path.abspath('/var/documents')
app.config['MAX_ARCHIVE_SIZE'] = 100 * 1024 * 1024
app.config['ALLOWED_DOCUMENT_EXTENSIONS'] = {'.pdf', '.docx', '.txt', '.md'}


def _error_response(message, status_code):
    """Build a JSON error response with the given HTTP status code."""
    return (jsonify({'error': message}), status_code)


def _remove_if_exists(path):
    """Delete a file if it is present."""
    if os.path.exists(path):
        os.remove(path)


class DocumentArchiver:
    """Creates and maintains zip archives of stored documents."""

    def __init__(self):
        os.makedirs(app.config['ARCHIVE_DIR'], exist_ok=True)
        os.makedirs(app.config['DOCUMENT_STORAGE'], exist_ok=True)

    def is_safe_path(self, base, path):
        """Return True if `path` lies strictly inside `base`."""
        base = os.path.abspath(base)
        path = os.path.abspath(path)
        return path.startswith(base + os.sep)

    def is_allowed_document(self, path):
        """Return True if `path` is an existing, permitted file or directory in document storage."""
        if not self.is_safe_path(app.config['DOCUMENT_STORAGE'], path):
            return False
        if not os.path.exists(path):
            return False
        if os.path.isdir(path):
            return True
        allowed_extensions = app.config['ALLOWED_DOCUMENT_EXTENSIONS']
        return any(path.lower().endswith(ext) for ext in allowed_extensions)

    def _add_directory_to_zip(self, zipf, directory):
        """Add all allowed files below `directory` to an open zip file."""
        parent_dir = os.path.dirname(directory)
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                if self.is_allowed_document(file_path):
                    arcname = os.path.relpath(file_path, parent_dir)
                    zipf.write(file_path, secure_filename(arcname))

    def _write_archive(self, archive_path, doc_path, compression_level):
        """Write the document (file or directory) into a new zip archive."""
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED,
                             compresslevel=compression_level) as zipf:
            if os.path.isfile(doc_path):
                zipf.write(doc_path, secure_filename(os.path.basename(doc_path)))
            elif os.path.isdir(doc_path):
                self._add_directory_to_zip(zipf, doc_path)

    def archive_document(self, doc_path, compression_level=6):
        """Archive a document; return the archive path, or None on failure."""
        if not 0 <= compression_level <= 9:
            return None
        if not isinstance(doc_path, str) or not self.is_allowed_document(doc_path):
            return None

        archive_name = f'doc_archive_{uuid.uuid4().hex}.zip'
        archive_path = os.path.join(app.config['ARCHIVE_DIR'], archive_name)

        try:
            self._write_archive(archive_path, doc_path, compression_level)
            if os.path.getsize(archive_path) > app.config['MAX_ARCHIVE_SIZE']:
                os.remove(archive_path)
                return None
            return archive_path
        except Exception as e:
            app.logger.error(f'Archive failed: {e}')
            _remove_if_exists(archive_path)
            return None

    def cleanup_old_archives(self, max_age_days=30):
        """Remove zip archives older than `max_age_days` days."""
        now = datetime.now()
        archive_dir = app.config['ARCHIVE_DIR']
        for archive in os.listdir(archive_dir):
            archive_path = os.path.join(archive_dir, archive)
            if not (os.path.isfile(archive_path) and archive.endswith('.zip')):
                continue
            if not self.is_safe_path(archive_dir, archive_path):
                continue
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(archive_path))
                if (now - mtime).days > max_age_days:
                    os.remove(archive_path)
            except Exception as e:
                app.logger.error(f'Failed to remove old archive: {e}')


archiver = DocumentArchiver()


@app.route('/archive', methods=['POST'])
def create_archive():
    data = request.get_json()
    if not data or 'document_path' not in data:
        return _error_response('Invalid request', 400)
    if not isinstance(data['document_path'], str):
        return _error_response('Invalid document path', 400)

    compression = data.get('compression_level', 6)
    archive_path = archiver.archive_document(data['document_path'], compression)
    if archive_path:
        return (jsonify({
            'status': 'success',
            'archive_path': os.path.basename(archive_path),
        }), 201)
    return _error_response('Archive creation failed', 500)


@app.route('/archive/<archive_name>')
def download_archive(archive_name):
    if not archive_name.endswith('.zip') or '../' in archive_name:
        return _error_response('Invalid archive name', 400)

    archive_path = os.path.join(app.config['ARCHIVE_DIR'], archive_name)
    if not archiver.is_safe_path(app.config['ARCHIVE_DIR'], archive_path):
        return _error_response('Access denied', 403)
    if not os.path.exists(archive_path):
        return _error_response('Archive not found', 404)

    try:
        return send_file(archive_path, as_attachment=True)
    except Exception as e:
        app.logger.error(f'Download error: {e}')
        return _error_response('Internal server error', 500)


@app.route('/documents', methods=['GET'])
def list_documents():
    try:
        storage_dir = app.config['DOCUMENT_STORAGE']
        docs = []
        for root, _, files in os.walk(storage_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if archiver.is_allowed_document(file_path):
                    docs.append(os.path.relpath(file_path, storage_dir))
        return jsonify({'documents': docs})
    except Exception as e:
        app.logger.error(f'Document list error: {e}')
        return _error_response('Internal server error', 500)


@app.route('/cleanup', methods=['POST'])
def cleanup_archives():
    try:
        archiver.cleanup_old_archives()
        return jsonify({'status': 'success'})
    except Exception as e:
        app.logger.error(f'Cleanup error: {e}')
        return _error_response('Internal server error', 500)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
