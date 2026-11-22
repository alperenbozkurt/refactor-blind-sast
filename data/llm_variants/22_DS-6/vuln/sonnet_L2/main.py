import os
import tarfile
import shutil
from datetime import datetime
from flask import Flask, request, jsonify, send_file

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_BACKUP_DIR = '/var/backups/configs'
DEFAULT_MAX_BACKUPS = 10

CONFIG_KEY_BACKUP_DIR = 'BACKUP_DIR'
CONFIG_KEY_MAX_BACKUPS = 'MAX_BACKUPS'

BACKUP_EXTENSION = '.tar.gz'
BACKUP_NAME_PREFIX = 'config_backup_'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

TAR_WRITE_MODE = 'w:gz'
TAR_READ_MODE = 'r:gz'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
SERVER_DEBUG = True

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_SERVER_ERROR = 500

app = Flask(__name__)
app.config[CONFIG_KEY_BACKUP_DIR] = DEFAULT_BACKUP_DIR
app.config[CONFIG_KEY_MAX_BACKUPS] = DEFAULT_MAX_BACKUPS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _backup_dir():
    return app.config[CONFIG_KEY_BACKUP_DIR]


def _max_backups():
    return app.config[CONFIG_KEY_MAX_BACKUPS]


def _backup_full_path(backup_file):
    return os.path.join(_backup_dir(), backup_file)


def _is_backup_file(filename):
    return filename.endswith(BACKUP_EXTENSION)


def _list_backup_names():
    return [f for f in os.listdir(_backup_dir()) if _is_backup_file(f)]


def _generate_backup_name():
    timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
    return f'{BACKUP_NAME_PREFIX}{timestamp}{BACKUP_EXTENSION}'


def _error_response(message, status_code):
    return (jsonify({'error': message}), status_code)


def _missing_field_response(field_name):
    return _error_response(f'Missing {field_name}', HTTP_BAD_REQUEST)


def _payload_lacks(data, field_name):
    return not data or field_name not in data


# ---------------------------------------------------------------------------
# Backup management
# ---------------------------------------------------------------------------
class BackupManager:

    def __init__(self):
        os.makedirs(_backup_dir(), exist_ok=True)

    def create_backup(self, config_path):
        if not os.path.exists(config_path):
            return None
        backup_path = _backup_full_path(_generate_backup_name())
        try:
            self._write_archive(backup_path, config_path)
            self._cleanup_old_backups()
            return backup_path
        except Exception as e:
            print(f'Backup failed: {e}')
            return None

    def restore_backup(self, backup_file, restore_path=None):
        full_backup_path = _backup_full_path(backup_file)
        if not os.path.exists(full_backup_path):
            return False
        try:
            self._extract_archive(full_backup_path, restore_path)
            return True
        except Exception as e:
            print(f'Restore failed: {e}')
            return False

    @staticmethod
    def _write_archive(backup_path, config_path):
        with tarfile.open(backup_path, TAR_WRITE_MODE) as tar:
            tar.add(config_path, arcname=os.path.basename(config_path))

    @staticmethod
    def _extract_archive(archive_path, restore_path):
        destination = restore_path if restore_path else os.path.dirname(archive_path)
        with tarfile.open(archive_path, TAR_READ_MODE) as tar:
            tar.extractall(path=destination)

    def _sorted_backup_paths(self):
        return sorted(
            [_backup_full_path(f) for f in _list_backup_names()],
            key=os.path.getmtime,
        )

    def _cleanup_old_backups(self):
        backups = self._sorted_backup_paths()
        while len(backups) > _max_backups():
            try:
                os.remove(backups.pop(0))
            except Exception as e:
                print(f'Failed to remove old backup: {e}')


backup_manager = BackupManager()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/backup', methods=['POST'])
def create_config_backup():
    data = request.get_json()
    if _payload_lacks(data, 'config_path'):
        return _missing_field_response('config_path')
    backup_path = backup_manager.create_backup(data['config_path'])
    if backup_path:
        return (jsonify({'status': 'success',
                         'backup_path': os.path.basename(backup_path)}),
                HTTP_CREATED)
    else:
        return _error_response('Backup failed', HTTP_SERVER_ERROR)


@app.route('/restore', methods=['POST'])
def restore_config_backup():
    data = request.get_json()
    if _payload_lacks(data, 'backup_file'):
        return _missing_field_response('backup_file')
    restore_path = data.get('restore_path')
    if backup_manager.restore_backup(data['backup_file'], restore_path):
        return (jsonify({'status': 'success'}), HTTP_OK)
    else:
        return _error_response('Restore failed', HTTP_SERVER_ERROR)


@app.route('/backups', methods=['GET'])
def list_backups():
    return jsonify({'backups': _list_backup_names()})


@app.route('/download/<backup_file>')
def download_backup(backup_file):
    backup_path = _backup_full_path(backup_file)
    if not os.path.exists(backup_path):
        return _error_response('Backup not found', HTTP_NOT_FOUND)
    return send_file(backup_path, as_attachment=True)


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)
