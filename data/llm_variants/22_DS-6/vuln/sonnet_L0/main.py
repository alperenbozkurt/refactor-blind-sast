import os
import tarfile
import shutil
from datetime import datetime
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)
app.config['BACKUP_DIR'] = '/var/backups/configs'
app.config['MAX_BACKUPS'] = 10

BACKUP_EXTENSION = '.tar.gz'


def _backup_dir():
    return app.config['BACKUP_DIR']


def _backup_file_path(backup_file):
    return os.path.join(_backup_dir(), backup_file)


def _list_backup_names():
    return [f for f in os.listdir(_backup_dir()) if f.endswith(BACKUP_EXTENSION)]


def _error(message, status):
    return jsonify({'error': message}), status


class BackupManager:

    def __init__(self):
        os.makedirs(_backup_dir(), exist_ok=True)

    def create_backup(self, config_path):
        if not os.path.exists(config_path):
            return None

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f'config_backup_{timestamp}{BACKUP_EXTENSION}'
        backup_path = _backup_file_path(backup_name)

        try:
            with tarfile.open(backup_path, 'w:gz') as tar:
                tar.add(config_path, arcname=os.path.basename(config_path))
            self._cleanup_old_backups()
            return backup_path
        except Exception as e:
            print(f'Backup failed: {e}')
            return None

    def restore_backup(self, backup_file, restore_path=None):
        full_backup_path = _backup_file_path(backup_file)
        if not os.path.exists(full_backup_path):
            return False

        target_dir = restore_path if restore_path else os.path.dirname(full_backup_path)

        try:
            with tarfile.open(full_backup_path, 'r:gz') as tar:
                tar.extractall(path=target_dir)
            return True
        except Exception as e:
            print(f'Restore failed: {e}')
            return False

    def _cleanup_old_backups(self):
        backups = sorted(
            (_backup_file_path(name) for name in _list_backup_names()),
            key=os.path.getmtime,
        )
        while len(backups) > app.config['MAX_BACKUPS']:
            try:
                os.remove(backups.pop(0))
            except Exception as e:
                print(f'Failed to remove old backup: {e}')


backup_manager = BackupManager()


@app.route('/backup', methods=['POST'])
def create_config_backup():
    data = request.get_json()
    if not data or 'config_path' not in data:
        return _error('Missing config_path', 400)

    backup_path = backup_manager.create_backup(data['config_path'])
    if backup_path:
        return jsonify({
            'status': 'success',
            'backup_path': os.path.basename(backup_path),
        }), 201
    return _error('Backup failed', 500)


@app.route('/restore', methods=['POST'])
def restore_config_backup():
    data = request.get_json()
    if not data or 'backup_file' not in data:
        return _error('Missing backup_file', 400)

    restore_path = data.get('restore_path')
    if backup_manager.restore_backup(data['backup_file'], restore_path):
        return jsonify({'status': 'success'}), 200
    return _error('Restore failed', 500)


@app.route('/backups', methods=['GET'])
def list_backups():
    return jsonify({'backups': _list_backup_names()})


@app.route('/download/<backup_file>')
def download_backup(backup_file):
    backup_path = _backup_file_path(backup_file)
    if not os.path.exists(backup_path):
        return _error('Backup not found', 404)
    return send_file(backup_path, as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
