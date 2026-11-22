"""Flask service for archiving documents into zip files.

Exposes endpoints to create, download, and list document archives, and to
remove archives that have aged past a retention period.
"""

import os
import uuid
import zipfile
from datetime import datetime

from flask import Flask, jsonify, request, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['ARCHIVE_DIR'] = os.path.abspath('/var/archives')
app.config['DOCUMENT_STORAGE'] = os.path.abspath('/var/documents')
app.config['MAX_ARCHIVE_SIZE'] = 100 * 1024 * 1024  # 100 MiB
app.config['ALLOWED_DOCUMENT_EXTENSIONS'] = {'.pdf', '.docx', '.txt', '.md'}


class DocumentArchiver:
    """Creates zip archives of allowed documents and prunes old archives."""

    def __init__(self):
        os.makedirs(app.config['ARCHIVE_DIR'], exist_ok=True)
        os.makedirs(app.config['DOCUMENT_STORAGE'], exist_ok=True)

    def is_safe_path(self, base, path):
        """Return True if ``path`` resolves to a location inside ``base``."""
        base_path = os.path.abspath(base)
        target_path = os.path.abspath(path)
        return target_path.startswith(base_path + os.sep)

    def is_allowed_document(self, path):
        """Return True if ``path`` is an existing directory or allowed file."""
        if not self.is_safe_path(app.config['DOCUMENT_STORAGE'], path):
            return False
        if not os.path.exists(path):
            return False
        if os.path.isdir(path):
            return True
        lowered_path = path.lower()
        return any(
            lowered_path.endswith(ext)
            for ext in app.config['ALLOWED_DOCUMENT_EXTENSIONS']
        )

    def archive_document(self, doc_path, compression_level=6):
        """Archive ``doc_path`` into a new zip file.

        Returns the path of the created archive, or None on failure.
        """
        if not 0 <= compression_level <= 9:
            return None
        if not isinstance(doc_path, str) or not self.is_allowed_document(doc_path):
            return None

        archive_name = f'doc_archive_{uuid.uuid4().hex}.zip'
        archive_path = os.path.join(app.config['ARCHIVE_DIR'], archive_name)

        try:
            with zipfile.ZipFile(
                archive_path, 'w', zipfile.ZIP_DEFLATED,
                compresslevel=compression_level,
            ) as zipf:
                if os.path.isfile(doc_path):
                    arcname = secure_filename(os.path.basename(doc_path))
                    zipf.write(doc_path, arcname)
                elif os.path.isdir(doc_path):
                    for root, _, files in os.walk(doc_path):
                        for filename in files:
                            file_path = os.path.join(root, filename)
                            if not self.is_allowed_document(file_path):
                                continue
                            arcname = os.path.relpath(
                                file_path, os.path.dirname(doc_path)
                            )
                            zipf.write(file_path, secure_filename(arcname))

            if os.path.getsize(archive_path) > app.config['MAX_ARCHIVE_SIZE']:
                os.remove(archive_path)
                return None
            return archive_path
        except Exception as e:
            app.logger.error(f'Archive failed: {e}')
            if os.path.exists(archive_path):
                os.remove(archive_path)
            return None

    def cleanup_old_archives(self, max_age_days=30):
        """Delete zip archives older than ``max_age_days`` days."""
        now = datetime.now()
        for archive_name in os.listdir(app.config['ARCHIVE_DIR']):
            archive_path = os.path.join(app.config['ARCHIVE_DIR'], archive_name)
            if not os.path.isfile(archive_path) or not archive_name.endswith('.zip'):
                continue
            if not self.is_safe_path(app.config['ARCHIVE_DIR'], archive_path):
                continue
            try:
                modified_at = datetime.fromtimestamp(os.path.getmtime(archive_path))
                if (now - modified_at).days > max_age_days:
                    os.remove(archive_path)
            except Exception as e:
                app.logger.error(f'Failed to remove old archive: {e}')


archiver = DocumentArchiver()


@app.route('/archive', methods=['POST'])
def create_archive():
    """Create an archive for the document path given in the JSON body."""
    data = request.get_json()
    if not data or 'document_path' not in data:
        return jsonify({'error': 'Invalid request'}), 400

    document_path = data['document_path']
    if not isinstance(document_path, str):
        return jsonify({'error': 'Invalid document path'}), 400

    compression_level = data.get('compression_level', 6)
    archive_path = archiver.archive_document(document_path, compression_level)
    if archive_path:
        return jsonify({
            'status': 'success',
            'archive_path': os.path.basename(archive_path),
        }), 201
    return jsonify({'error': 'Archive creation failed'}), 500


@app.route('/archive/<archive_name>')
def download_archive(archive_name):
    """Send a previously created archive to the client as an attachment."""
    if not archive_name.endswith('.zip') or '../' in archive_name:
        return jsonify({'error': 'Invalid archive name'}), 400

    archive_path = os.path.join(app.config['ARCHIVE_DIR'], archive_name)
    if not archiver.is_safe_path(app.config['ARCHIVE_DIR'], archive_path):
        return jsonify({'error': 'Access denied'}), 403
    if not os.path.exists(archive_path):
        return jsonify({'error': 'Archive not found'}), 404

    try:
        return send_file(archive_path, as_attachment=True)
    except Exception as e:
        app.logger.error(f'Download error: {e}')
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/documents', methods=['GET'])
def list_documents():
    """List all allowed documents relative to the document storage root."""
    try:
        documents = []
        for root, _, files in os.walk(app.config['DOCUMENT_STORAGE']):
            for filename in files:
                file_path = os.path.join(root, filename)
                if archiver.is_allowed_document(file_path):
                    documents.append(
                        os.path.relpath(file_path, app.config['DOCUMENT_STORAGE'])
                    )
        return jsonify({'documents': documents})
    except Exception as e:
        app.logger.error(f'Document list error: {e}')
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/cleanup', methods=['POST'])
def cleanup_archives():
    """Remove archives older than the default retention period."""
    try:
        archiver.cleanup_old_archives()
        return jsonify({'status': 'success'})
    except Exception as e:
        app.logger.error(f'Cleanup error: {e}')
        return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
