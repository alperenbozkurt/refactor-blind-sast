import os
import tarfile
from flask import Flask, request, send_file, render_template, abort, flash, redirect
from werkzeug.utils import secure_filename
import secrets

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------
DEFAULT_BACKUP_DIR = '/var/backups/configs'
DEFAULT_CONFIG_DIR = '/etc/appconfigs'
DEFAULT_MAX_BACKUP_SIZE = 10 * 1024 * 1024

BACKUP_EXTENSION = '.tar.gz'
DEFAULT_BACKUP_NAME = 'config_backup'
SECRET_KEY_BYTES = 32

DIR_MODE = 0o750          # 488
CONFIG_FILE_MODE = 0o640  # 416

SAMPLE_CONFIG_COUNT = 3
SAMPLE_CONFIG_TEMPLATE = '[DEFAULT]\nsetting{i} = value{i}\n'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8080

INDEX_URL = '/'
BACKUP_TEMPLATE = 'backup.html'
ERROR_TEMPLATE = 'error.html'


# --------------------------------------------------------------------------
# Application setup
# --------------------------------------------------------------------------
class AppConfig:
    """Default configuration values for the application."""
    BACKUP_DIR = os.path.abspath(DEFAULT_BACKUP_DIR)
    CONFIG_DIR = os.path.abspath(DEFAULT_CONFIG_DIR)
    MAX_BACKUP_SIZE = DEFAULT_MAX_BACKUP_SIZE


app = Flask(__name__)
app.secret_key = secrets.token_hex(SECRET_KEY_BYTES)
app.config['BACKUP_DIR'] = AppConfig.BACKUP_DIR
app.config['CONFIG_DIR'] = AppConfig.CONFIG_DIR
app.config['MAX_BACKUP_SIZE'] = AppConfig.MAX_BACKUP_SIZE


# --------------------------------------------------------------------------
# Path / validation helpers
# --------------------------------------------------------------------------
def _backup_dir():
    return app.config['BACKUP_DIR']


def _config_dir():
    return app.config['CONFIG_DIR']


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


def safe_extract(tar, path):
    for member in tar.getmembers():
        member_path = os.path.abspath(os.path.join(path, member.name))
        if not is_safe_path(path, member_path):
            raise ValueError(f'Attempted path traversal in tar file: {member.name}')
        tar.extract(member, path)


# --------------------------------------------------------------------------
# Backup operations
# --------------------------------------------------------------------------
def _list_backups():
    backup_dir = _backup_dir()
    return [
        f for f in os.listdir(backup_dir)
        if f.endswith(BACKUP_EXTENSION)
        and is_safe_path(backup_dir, os.path.join(backup_dir, f))
    ]


def _build_backup_path(form_name):
    return os.path.join(_backup_dir(), secure_filename(form_name) + BACKUP_EXTENSION)


def _write_backup_archive(backup_path):
    config_dir = _config_dir()
    with tarfile.open(backup_path, 'w:gz') as tar:
        for config_file in os.listdir(config_dir):
            full_path = os.path.join(config_dir, config_file)
            if os.path.isfile(full_path) and is_safe_path(config_dir, full_path):
                tar.add(full_path, arcname=config_file)


def _backup_too_large(backup_path):
    return os.path.getsize(backup_path) > app.config['MAX_BACKUP_SIZE']


def _validate_restore_request(backup_file):
    """Validate a restore request, aborting with the proper HTTP status."""
    if not validate_backup_filename(backup_file):
        abort(400, 'Invalid backup file')
    backup_path = os.path.join(_backup_dir(), backup_file)
    if not is_safe_path(_backup_dir(), backup_path):
        abort(403, 'Access denied')
    if not os.path.exists(backup_path):
        abort(404, 'Backup file not found')
    if not tarfile.is_tarfile(backup_path):
        abort(400, 'Invalid backup file format')
    return backup_path


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route('/')
def index():
    backups = []
    try:
        backups = _list_backups()
    except Exception as e:
        app.logger.error(f'Error accessing backup directory: {e}')
        flash('Error accessing backup directory')
    return render_template(BACKUP_TEMPLATE, backups=backups)


@app.route('/create_backup', methods=['POST'])
def create_backup():
    backup_path = _build_backup_path(request.form.get('backup_name', DEFAULT_BACKUP_NAME))
    if not is_safe_path(_backup_dir(), backup_path):
        flash('Invalid backup name')
        return redirect(INDEX_URL)
    try:
        _write_backup_archive(backup_path)
        if _backup_too_large(backup_path):
            os.remove(backup_path)
            flash('Backup too large')
            return redirect(INDEX_URL)
        flash('Backup created successfully')
    except Exception as e:
        app.logger.error(f'Backup failed: {e}')
        flash('Backup failed')
    return redirect(INDEX_URL)


@app.route('/restore_backup/<backup_file>')
def restore_config(backup_file):
    try:
        backup_path = _validate_restore_request(backup_file)
        with tarfile.open(backup_path, 'r:gz') as tar:
            safe_extract(tar, path=_config_dir())
        flash('Configuration restored successfully')
        return redirect(INDEX_URL)
    except ValueError as e:
        app.logger.error(f'Security violation during restore: {e}')
        abort(400, 'Invalid backup contents')
    except Exception as e:
        app.logger.error(f'Restoration failed: {e}')
        abort(500, 'Restoration failed')


# --------------------------------------------------------------------------
# Error handlers
# --------------------------------------------------------------------------
def _render_error(message, status):
    return (render_template(ERROR_TEMPLATE, error=message), status)


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


# --------------------------------------------------------------------------
# Startup helpers
# --------------------------------------------------------------------------
def _ensure_directories():
    os.makedirs(_backup_dir(), mode=DIR_MODE, exist_ok=True)
    os.makedirs(_config_dir(), mode=DIR_MODE, exist_ok=True)


def _create_sample_configs():
    for i in range(1, SAMPLE_CONFIG_COUNT + 1):
        config_path = os.path.join(_config_dir(), f'config{i}.ini')
        try:
            with open(config_path, 'w') as f:
                f.write(SAMPLE_CONFIG_TEMPLATE.format(i=i))
            os.chmod(config_path, CONFIG_FILE_MODE)
        except Exception as e:
            app.logger.error(f'Error creating sample config: {e}')


def main():
    _ensure_directories()
    _create_sample_configs()
    app.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
