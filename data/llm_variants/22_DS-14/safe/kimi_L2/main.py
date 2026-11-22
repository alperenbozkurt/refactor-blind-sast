import os
import tarfile
from flask import Flask, request, send_file, render_template, abort, flash, redirect
from werkzeug.utils import secure_filename
import secrets

BACKUP_DIR = os.path.abspath('/var/backups/configs')
CONFIG_DIR = os.path.abspath('/etc/appconfigs')
MAX_BACKUP_SIZE = 10 * 1024 * 1024
BACKUP_EXTENSION = '.tar.gz'
DEFAULT_BACKUP_NAME = 'config_backup'
DIRECTORY_MODE = 0o750
CONFIG_FILE_MODE = 0o640
SAMPLE_CONFIG_COUNT = 3
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8080

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config['BACKUP_DIR'] = BACKUP_DIR
app.config['CONFIG_DIR'] = CONFIG_DIR
app.config['MAX_BACKUP_SIZE'] = MAX_BACKUP_SIZE


def is_safe_path(base_path, requested_path):
    base_path = os.path.abspath(base_path)
    requested_path = os.path.abspath(requested_path)
    return requested_path.startswith(base_path + os.sep)


def validate_backup_filename(filename):
    if not filename or not isinstance(filename, str):
        return False
    if not filename.endswith(BACKUP_EXTENSION):
        return False
    if '../' in filename or '~' in filename:
        return False
    return True


def _extract_member(tar, member, path):
    member_path = os.path.abspath(os.path.join(path, member.name))
    if not is_safe_path(path, member_path):
        raise ValueError(f'Attempted path traversal in tar file: {member.name}')
    tar.extract(member, path)


def safe_extract(tar, path):
    for member in tar.getmembers():
        _extract_member(tar, member, path)


def _list_backup_files(backup_dir):
    return [
        filename
        for filename in os.listdir(backup_dir)
        if filename.endswith(BACKUP_EXTENSION)
        and is_safe_path(backup_dir, os.path.join(backup_dir, filename))
    ]


def _add_config_files(tar, config_dir):
    for config_file in os.listdir(config_dir):
        full_path = os.path.join(config_dir, config_file)
        if os.path.isfile(full_path) and is_safe_path(config_dir, full_path):
            tar.add(full_path, arcname=config_file)


def _remove_backup_if_too_large(backup_path, max_backup_size):
    if os.path.getsize(backup_path) > max_backup_size:
        os.remove(backup_path)
        return True
    return False


def _error_response(message, status_code):
    return (render_template('error.html', error=message), status_code)


@app.route('/')
def index():
    backups = []
    try:
        backups = _list_backup_files(app.config['BACKUP_DIR'])
    except Exception as e:
        app.logger.error(f'Error accessing backup directory: {e}')
        flash('Error accessing backup directory')
    return render_template('backup.html', backups=backups)


@app.route('/create_backup', methods=['POST'])
def create_backup():
    backup_name = secure_filename(request.form.get('backup_name', DEFAULT_BACKUP_NAME)) + BACKUP_EXTENSION
    backup_path = os.path.join(app.config['BACKUP_DIR'], backup_name)
    if not is_safe_path(app.config['BACKUP_DIR'], backup_path):
        flash('Invalid backup name')
        return redirect('/')
    try:
        with tarfile.open(backup_path, 'w:gz') as tar:
            _add_config_files(tar, app.config['CONFIG_DIR'])
        if _remove_backup_if_too_large(backup_path, app.config['MAX_BACKUP_SIZE']):
            flash('Backup too large')
            return redirect('/')
        flash('Backup created successfully')
    except Exception as e:
        app.logger.error(f'Backup failed: {e}')
        flash('Backup failed')
    return redirect('/')


@app.route('/restore_backup/<backup_file>')
def restore_config(backup_file):
    try:
        if not validate_backup_filename(backup_file):
            abort(400, 'Invalid backup file')
        backup_path = os.path.join(app.config['BACKUP_DIR'], backup_file)
        if not is_safe_path(app.config['BACKUP_DIR'], backup_path):
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


@app.errorhandler(404)
def not_found(e):
    return _error_response('Resource not found', 404)


@app.errorhandler(400)
def bad_request(e):
    return _error_response('Invalid request', 400)


@app.errorhandler(403)
def forbidden(e):
    return _error_response('Access denied', 403)


@app.errorhandler(500)
def server_error(e):
    return _error_response('Internal server error', 500)


def _create_sample_config(config_dir, config_index):
    config_path = os.path.join(config_dir, f'config{config_index}.ini')
    try:
        with open(config_path, 'w') as f:
            f.write(f'[DEFAULT]\nsetting{config_index} = value{config_index}\n')
        os.chmod(config_path, CONFIG_FILE_MODE)
    except Exception as e:
        app.logger.error(f'Error creating sample config: {e}')


def main():
    os.makedirs(app.config['BACKUP_DIR'], mode=DIRECTORY_MODE, exist_ok=True)
    os.makedirs(app.config['CONFIG_DIR'], mode=DIRECTORY_MODE, exist_ok=True)
    for i in range(1, SAMPLE_CONFIG_COUNT + 1):
        _create_sample_config(app.config['CONFIG_DIR'], i)
    app.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
