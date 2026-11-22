"""Configuration backup and restore HTTP service.

Exposes a small Flask API to create, list, download and restore gzipped
tar backups of configuration files located in approved directories.
"""

import os
import shutil
import tarfile
from datetime import datetime
from http import HTTPStatus

from flask import Flask, jsonify, request, send_file
from werkzeug.utils import secure_filename

# --- Default configuration ---------------------------------------------------
DEFAULT_BACKUP_DIR = '/var/backups/configs'
DEFAULT_MAX_BACKUPS = 10
DEFAULT_ALLOWED_RESTORE_PATHS = ['/etc/appconfig', '/var/appconfig']

# --- Backup archive conventions ----------------------------------------------
BACKUP_ARCHIVE_EXTENSION = '.tar.gz'
BACKUP_NAME_TEMPLATE = 'config_backup_{timestamp}.tar.gz'
BACKUP_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
PATH_TRAVERSAL_MARKER = '../'

# --- Server defaults -----------------------------------------------------------
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000

app = Flask(__name__)
app.config['BACKUP_DIR'] = os.path.abspath(DEFAULT_BACKUP_DIR)
app.config['MAX_BACKUPS'] = DEFAULT_MAX_BACKUPS
app.config['ALLOWED_RESTORE_PATHS'] = DEFAULT_ALLOWED_RESTORE_PATHS


class BackupManager:
    """Creates, restores and prunes configuration backup archives."""

    def __init__(self):
        os.makedirs(self._backup_dir(), exist_ok=True)

    # -- configuration accessors ----------------------------------------------
    @staticmethod
    def _backup_dir():
        return app.config['BACKUP_DIR']

    @staticmethod
    def _max_backups():
        return app.config['MAX_BACKUPS']

    @staticmethod
    def _allowed_restore_paths():
        return app.config['ALLOWED_RESTORE_PATHS']

    # -- path and filename helpers ---------------------------------------------
    def is_safe_path(self, base, path):
        base = os.path.abspath(base)
        path = os.path.abspath(path)
        return path.startswith(base + os.sep)

    def _is_allowed_path(self, path):
        return any(
            self.is_safe_path(allowed_path, path)
            for allowed_path in self._allowed_restore_paths()
        )

    def _full_backup_path(self, backup_file):
        return os.path.join(self._backup_dir(), backup_file)

    @staticmethod
    def _is_valid_backup_filename(backup_file):
        return (
            backup_file.endswith(BACKUP_ARCHIVE_EXTENSION)
            and PATH_TRAVERSAL_MARKER not in backup_file
        )

    def _list_backup_filenames(self):
        return [
            filename
            for filename in os.listdir(self._backup_dir())
            if filename.endswith(BACKUP_ARCHIVE_EXTENSION)
            and self.is_safe_path(self._backup_dir(), self._full_backup_path(filename))
        ]

    @staticmethod
    def _generate_backup_name():
        timestamp = datetime.now().strftime(BACKUP_TIMESTAMP_FORMAT)
        return BACKUP_NAME_TEMPLATE.format(timestamp=timestamp)

    # -- backup operations -------------------------------------------------------
    def create_backup(self, config_path):
        if not os.path.exists(config_path):
            return None
        if not self._is_allowed_path(config_path):
            return None
        backup_path = self._full_backup_path(self._generate_backup_name())
        try:
            self._write_archive(config_path, backup_path)
            self._cleanup_old_backups()
            return backup_path
        except Exception as e:
            app.logger.error(f'Backup failed: {e}')
            return None

    @staticmethod
    def _write_archive(config_path, backup_path):
        with tarfile.open(backup_path, 'w:gz') as tar:
            tar.add(config_path, arcname=os.path.basename(config_path))

    def restore_backup(self, backup_file, restore_path=None):
        if not self._is_valid_backup_filename(backup_file):
            return False
        full_backup_path = self._full_backup_path(backup_file)
        if not self.is_safe_path(self._backup_dir(), full_backup_path):
            return False
        if not os.path.exists(full_backup_path):
            return False
        try:
            with tarfile.open(full_backup_path, 'r:gz') as tar:
                if restore_path:
                    if not self._is_allowed_path(restore_path):
                        return False
                    os.makedirs(restore_path, exist_ok=True)
                    tar.extractall(path=restore_path)
                else:
                    tar.extractall(path=self._backup_dir())
            return True
        except Exception as e:
            app.logger.error(f'Restore failed: {e}')
            return False

    def _cleanup_old_backups(self):
        backups = sorted(
            (self._full_backup_path(name) for name in self._list_backup_filenames()),
            key=os.path.getmtime,
        )
        while len(backups) > self._max_backups():
            self._remove_backup(backups.pop(0))

    @staticmethod
    def _remove_backup(backup_path):
        try:
            os.remove(backup_path)
        except Exception as e:
            app.logger.error(f'Failed to remove old backup: {e}')


backup_manager = BackupManager()


def _error_response(message, status):
    return jsonify({'error': message}), status


@app.route('/backup', methods=['POST'])
def create_config_backup():
    data = request.get_json()
    if not data or 'config_path' not in data:
        return _error_response('Missing config_path', HTTPStatus.BAD_REQUEST)
    backup_path = backup_manager.create_backup(data['config_path'])
    if backup_path:
        return (
            jsonify({
                'status': 'success',
                'backup_path': os.path.basename(backup_path),
            }),
            HTTPStatus.CREATED,
        )
    return _error_response('Backup failed', HTTPStatus.INTERNAL_SERVER_ERROR)


@app.route('/restore', methods=['POST'])
def restore_config_backup():
    data = request.get_json()
    if not data or 'backup_file' not in data:
        return _error_response('Missing backup_file', HTTPStatus.BAD_REQUEST)
    restore_path = data.get('restore_path')
    if backup_manager.restore_backup(data['backup_file'], restore_path):
        return jsonify({'status': 'success'}), HTTPStatus.OK
    return _error_response('Restore failed', HTTPStatus.INTERNAL_SERVER_ERROR)


@app.route('/backups', methods=['GET'])
def list_backups():
    try:
        return jsonify({'backups': backup_manager._list_backup_filenames()})
    except Exception as e:
        app.logger.error(f'Error listing backups: {e}')
        return _error_response('Internal server error', HTTPStatus.INTERNAL_SERVER_ERROR)


@app.route('/download/<backup_file>')
def download_backup(backup_file):
    if not backup_manager._is_valid_backup_filename(backup_file):
        return _error_response('Invalid backup file', HTTPStatus.BAD_REQUEST)
    backup_path = backup_manager._full_backup_path(backup_file)
    if not backup_manager.is_safe_path(app.config['BACKUP_DIR'], backup_path):
        return _error_response('Access denied', HTTPStatus.FORBIDDEN)
    if not os.path.exists(backup_path):
        return _error_response('Backup not found', HTTPStatus.NOT_FOUND)
    return send_file(backup_path, as_attachment=True)


def main():
    app.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
