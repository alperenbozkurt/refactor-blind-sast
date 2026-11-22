import os
import shutil
import tarfile
from datetime import datetime

from flask import Flask, jsonify, request, send_file

BACKUP_DIR_CONFIG_KEY = 'BACKUP_DIR'
MAX_BACKUPS_CONFIG_KEY = 'MAX_BACKUPS'
DEFAULT_BACKUP_DIR = '/var/backups/configs'
DEFAULT_MAX_BACKUPS = 10

BACKUP_ARCHIVE_SUFFIX = '.tar.gz'
BACKUP_NAME_PREFIX = 'config_backup_'
BACKUP_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
SERVER_DEBUG = True

app = Flask(__name__)
app.config[BACKUP_DIR_CONFIG_KEY] = DEFAULT_BACKUP_DIR
app.config[MAX_BACKUPS_CONFIG_KEY] = DEFAULT_MAX_BACKUPS


def _backup_dir():
    return app.config[BACKUP_DIR_CONFIG_KEY]


def _max_backups():
    return app.config[MAX_BACKUPS_CONFIG_KEY]


def _is_backup_archive(filename):
    return filename.endswith(BACKUP_ARCHIVE_SUFFIX)


def _backup_path(filename):
    return os.path.join(_backup_dir(), filename)


def _backup_filenames():
    return [f for f in os.listdir(_backup_dir()) if _is_backup_archive(f)]


def _new_backup_name():
    timestamp = datetime.now().strftime(BACKUP_TIMESTAMP_FORMAT)
    return f'{BACKUP_NAME_PREFIX}{timestamp}{BACKUP_ARCHIVE_SUFFIX}'


def _error_response(message, status_code):
    return (jsonify({'error': message}), status_code)


class BackupManager:

    def __init__(self):
        os.makedirs(_backup_dir(), exist_ok=True)

    def create_backup(self, config_path):
        if not os.path.exists(config_path):
            return None

        backup_path = _backup_path(_new_backup_name())
        try:
            self._write_archive(config_path, backup_path)
            self._cleanup_old_backups()
            return backup_path
        except Exception as e:
            print(f'Backup failed: {e}')
            return None

    def restore_backup(self, backup_file, restore_path=None):
        full_backup_path = _backup_path(backup_file)
        if not os.path.exists(full_backup_path):
            return False

        try:
            self._extract_archive(full_backup_path, restore_path)
            return True
        except Exception as e:
            print(f'Restore failed: {e}')
            return False

    def _write_archive(self, config_path, backup_path):
        with tarfile.open(backup_path, 'w:gz') as tar:
            tar.add(config_path, arcname=os.path.basename(config_path))

    def _extract_archive(self, full_backup_path, restore_path=None):
        with tarfile.open(full_backup_path, 'r:gz') as tar:
            if restore_path:
                tar.extractall(path=restore_path)
            else:
                tar.extractall(path=os.path.dirname(full_backup_path))

    def _cleanup_old_backups(self):
        backups = sorted(
            (
                _backup_path(f)
                for f in os.listdir(_backup_dir())
                if _is_backup_archive(f)
            ),
            key=os.path.getmtime,
        )
        while len(backups) > _max_backups():
            try:
                os.remove(backups.pop(0))
            except Exception as e:
                print(f'Failed to remove old backup: {e}')


backup_manager = BackupManager()


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
    return _error_response('Backup failed', HTTP_INTERNAL_SERVER_ERROR)


@app.route('/restore', methods=['POST'])
def restore_config_backup():
    data = request.get_json()
    if not data or 'backup_file' not in data:
        return _error_response('Missing backup_file', HTTP_BAD_REQUEST)

    restore_path = data.get('restore_path')
    if backup_manager.restore_backup(data['backup_file'], restore_path):
        return (jsonify({'status': 'success'}), HTTP_OK)
    return _error_response('Restore failed', HTTP_INTERNAL_SERVER_ERROR)


@app.route('/backups', methods=['GET'])
def list_backups():
    return jsonify({'backups': _backup_filenames()})


@app.route('/download/<backup_file>')
def download_backup(backup_file):
    backup_path = _backup_path(backup_file)
    if not os.path.exists(backup_path):
        return _error_response('Backup not found', HTTP_NOT_FOUND)
    return send_file(backup_path, as_attachment=True)


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)
