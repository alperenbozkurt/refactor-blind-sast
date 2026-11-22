import os
import tarfile
import shutil
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
DEFAULT_BACKUP_DIR = '/var/backups/configs'
DEFAULT_MAX_BACKUPS = 10
DEFAULT_ALLOWED_RESTORE_PATHS = ['/etc/appconfig', '/var/appconfig']

BACKUP_EXTENSION = '.tar.gz'
BACKUP_PREFIX = 'config_backup_'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
TAR_WRITE_MODE = 'w:gz'
TAR_READ_MODE = 'r:gz'

HOST = '0.0.0.0'
PORT = 5000

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_SERVER_ERROR = 500


# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #
def _configure_app(flask_app):
    flask_app.config['BACKUP_DIR'] = os.path.abspath(DEFAULT_BACKUP_DIR)
    flask_app.config['MAX_BACKUPS'] = DEFAULT_MAX_BACKUPS
    flask_app.config['ALLOWED_RESTORE_PATHS'] = list(DEFAULT_ALLOWED_RESTORE_PATHS)


app = Flask(__name__)
_configure_app(app)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _backup_dir():
    return app.config['BACKUP_DIR']


def _max_backups():
    return app.config['MAX_BACKUPS']


def _allowed_paths():
    return app.config['ALLOWED_RESTORE_PATHS']


def _is_valid_backup_name(name):
    """A backup name must have the archive extension and no '../' sequence."""
    return name.endswith(BACKUP_EXTENSION) and '../' not in name


def _generate_backup_name():
    timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
    return f'{BACKUP_PREFIX}{timestamp}{BACKUP_EXTENSION}'


def _error_response(message, status):
    return (jsonify({'error': message}), status)


# --------------------------------------------------------------------------- #
# Backup management
# --------------------------------------------------------------------------- #
class BackupManager:

    def __init__(self):
        os.makedirs(_backup_dir(), exist_ok=True)

    def is_safe_path(self, base, path):
        base = os.path.abspath(base)
        path = os.path.abspath(path)
        return path.startswith(base + os.sep)

    def _is_allowed_path(self, path):
        return any(
            (self.is_safe_path(allowed_path, path) for allowed_path in _allowed_paths())
        )

    def _resolve_backup_path(self, backup_file):
        return os.path.join(_backup_dir(), backup_file)

    def list_backup_names(self):
        return [
            f for f in os.listdir(_backup_dir())
            if f.endswith(BACKUP_EXTENSION)
            and self.is_safe_path(_backup_dir(), self._resolve_backup_path(f))
        ]

    def create_backup(self, config_path):
        if not os.path.exists(config_path):
            return None
        if not self._is_allowed_path(config_path):
            return None
        backup_path = self._resolve_backup_path(_generate_backup_name())
        try:
            with tarfile.open(backup_path, TAR_WRITE_MODE) as tar:
                tar.add(config_path, arcname=os.path.basename(config_path))
            self._cleanup_old_backups()
            return backup_path
        except Exception as e:
            app.logger.error(f'Backup failed: {e}')
            return None

    def restore_backup(self, backup_file, restore_path=None):
        if not _is_valid_backup_name(backup_file):
            return False
        full_backup_path = self._resolve_backup_path(backup_file)
        if not self.is_safe_path(_backup_dir(), full_backup_path):
            return False
        if not os.path.exists(full_backup_path):
            return False
        try:
            with tarfile.open(full_backup_path, TAR_READ_MODE) as tar:
                if restore_path:
                    if not self._is_allowed_path(restore_path):
                        return False
                    os.makedirs(restore_path, exist_ok=True)
                    tar.extractall(path=restore_path)
                else:
                    tar.extractall(path=_backup_dir())
            return True
        except Exception as e:
            app.logger.error(f'Restore failed: {e}')
            return False

    def _cleanup_old_backups(self):
        backups = sorted(
            [self._resolve_backup_path(f) for f in self.list_backup_names()],
            key=os.path.getmtime,
        )
        while len(backups) > _max_backups():
            try:
                os.remove(backups.pop(0))
            except Exception as e:
                app.logger.error(f'Failed to remove old backup: {e}')


backup_manager = BackupManager()


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/backup', methods=['POST'])
def create_config_backup():
    data = request.get_json()
    if not data or 'config_path' not in data:
        return _error_response('Missing config_path', HTTP_BAD_REQUEST)
    backup_path = backup_manager.create_backup(data['config_path'])
    if backup_path:
        return (
            jsonify({'status': 'success', 'backup_path': os.path.basename(backup_path)}),
            HTTP_CREATED,
        )
    else:
        return _error_response('Backup failed', HTTP_SERVER_ERROR)


@app.route('/restore', methods=['POST'])
def restore_config_backup():
    data = request.get_json()
    if not data or 'backup_file' not in data:
        return _error_response('Missing backup_file', HTTP_BAD_REQUEST)
    restore_path = data.get('restore_path')
    if backup_manager.restore_backup(data['backup_file'], restore_path):
        return (jsonify({'status': 'success'}), HTTP_OK)
    else:
        return _error_response('Restore failed', HTTP_SERVER_ERROR)


@app.route('/backups', methods=['GET'])
def list_backups():
    try:
        backups = backup_manager.list_backup_names()
        return jsonify({'backups': backups})
    except Exception as e:
        app.logger.error(f'Error listing backups: {e}')
        return _error_response('Internal server error', HTTP_SERVER_ERROR)


@app.route('/download/<backup_file>')
def download_backup(backup_file):
    if not _is_valid_backup_name(backup_file):
        return _error_response('Invalid backup file', HTTP_BAD_REQUEST)
    backup_path = os.path.join(_backup_dir(), backup_file)
    if not backup_manager.is_safe_path(_backup_dir(), backup_path):
        return _error_response('Access denied', HTTP_FORBIDDEN)
    if not os.path.exists(backup_path):
        return _error_response('Backup not found', HTTP_NOT_FOUND)
    return send_file(backup_path, as_attachment=True)


if __name__ == '__main__':
    app.run(host=HOST, port=PORT)
