import os
import secrets
import tarfile

from flask import Flask, abort, flash, redirect, render_template, request, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config.update(
    BACKUP_DIR=os.path.abspath('/var/backups/configs'),
    CONFIG_DIR=os.path.abspath('/etc/appconfigs'),
    MAX_BACKUP_SIZE=10 * 1024 * 1024,
)

BACKUP_EXTENSION = '.tar.gz'
DEFAULT_BACKUP_NAME = 'config_backup'


def is_safe_path(base_path, requested_path):
    base_path = os.path.abspath(base_path)
    requested_path = os.path.abspath(requested_path)
    return requested_path.startswith(base_path + os.sep)


def validate_backup_filename(filename):
    return (
        bool(filename)
        and isinstance(filename, str)
        and filename.endswith(BACKUP_EXTENSION)
        and '../' not in filename
        and '~' not in filename
    )


def safe_extract(tar, path):
    for member in tar.getmembers():
        member_path = os.path.abspath(os.path.join(path, member.name))
        if not is_safe_path(path, member_path):
            raise ValueError(f'Attempted path traversal in tar file: {member.name}')
        tar.extract(member, path)


@app.route('/')
def index():
    backups = []
    backup_dir = app.config['BACKUP_DIR']
    try:
        backups = [
            name
            for name in os.listdir(backup_dir)
            if name.endswith(BACKUP_EXTENSION)
            and is_safe_path(backup_dir, os.path.join(backup_dir, name))
        ]
    except Exception as e:
        app.logger.error(f'Error accessing backup directory: {e}')
        flash('Error accessing backup directory')
    return render_template('backup.html', backups=backups)


@app.route('/create_backup', methods=['POST'])
def create_backup():
    backup_dir = app.config['BACKUP_DIR']
    config_dir = app.config['CONFIG_DIR']
    backup_name = secure_filename(request.form.get('backup_name', DEFAULT_BACKUP_NAME)) + BACKUP_EXTENSION
    backup_path = os.path.join(backup_dir, backup_name)
    if not is_safe_path(backup_dir, backup_path):
        flash('Invalid backup name')
        return redirect('/')
    try:
        with tarfile.open(backup_path, 'w:gz') as tar:
            for config_file in os.listdir(config_dir):
                full_path = os.path.join(config_dir, config_file)
                if os.path.isfile(full_path) and is_safe_path(config_dir, full_path):
                    tar.add(full_path, arcname=config_file)
        if os.path.getsize(backup_path) > app.config['MAX_BACKUP_SIZE']:
            os.remove(backup_path)
            flash('Backup too large')
        else:
            flash('Backup created successfully')
    except Exception as e:
        app.logger.error(f'Backup failed: {e}')
        flash('Backup failed')
    return redirect('/')


@app.route('/restore_backup/<backup_file>')
def restore_config(backup_file):
    backup_dir = app.config['BACKUP_DIR']
    try:
        if not validate_backup_filename(backup_file):
            abort(400, 'Invalid backup file')
        backup_path = os.path.join(backup_dir, backup_file)
        if not is_safe_path(backup_dir, backup_path):
            abort(403, 'Access denied')
        if not os.path.exists(backup_path):
            abort(404, 'Backup file not found')
        if not tarfile.is_tarfile(backup_path):
            abort(400, 'Invalid backup file format')
        with tarfile.open(backup_path, 'r:gz') as tar:
            safe_extract(tar, path=app.config['CONFIG_DIR'])
        flash('Configuration restored successfully')
        return redirect('/')
    except ValueError as e:
        app.logger.error(f'Security violation during restore: {e}')
        abort(400, 'Invalid backup contents')
    except Exception as e:
        app.logger.error(f'Restoration failed: {e}')
        abort(500, 'Restoration failed')


def _render_error(message, status_code):
    return render_template('error.html', error=message), status_code


@app.errorhandler(404)
def not_found(e):
    return _render_error('Resource not found', 404)


@app.errorhandler(400)
def bad_request(e):
    return _render_error('Invalid request', 400)


@app.errorhandler(403)
def forbidden(e):
    return _render_error('Access denied', 403)


@app.errorhandler(500)
def server_error(e):
    return _render_error('Internal server error', 500)


def _create_sample_configs():
    for i in range(1, 4):
        config_path = os.path.join(app.config['CONFIG_DIR'], f'config{i}.ini')
        try:
            with open(config_path, 'w') as f:
                f.write(f'[DEFAULT]\nsetting{i} = value{i}\n')
            os.chmod(config_path, 0o640)
        except Exception as e:
            app.logger.error(f'Error creating sample config: {e}')


if __name__ == '__main__':
    os.makedirs(app.config['BACKUP_DIR'], mode=0o750, exist_ok=True)
    os.makedirs(app.config['CONFIG_DIR'], mode=0o750, exist_ok=True)
    _create_sample_configs()
    app.run(host='0.0.0.0', port=8080)
