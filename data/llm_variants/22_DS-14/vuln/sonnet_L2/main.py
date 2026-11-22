import os
import tarfile

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,  # noqa: F401  (kept for module-level name compatibility)
)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
SECRET_KEY = 'super_secret_key'
DEFAULT_BACKUP_DIR = '/var/backups/configs'
DEFAULT_CONFIG_DIR = '/etc/appconfigs'

BACKUP_EXTENSION = '.tar.gz'
DEFAULT_BACKUP_NAME = 'config_backup'
TAR_WRITE_MODE = 'w:gz'
TAR_READ_MODE = 'r:gz'

INDEX_TEMPLATE = 'backup.html'
ERROR_TEMPLATE = 'error.html'
INDEX_URL = '/'

DEFAULT_CONFIG_FILE_COUNT = 3
DEFAULT_CONFIG_FILE_TEMPLATE = '[DEFAULT]\nsetting{i} = value{i}\n'
DEFAULT_CONFIG_FILENAME_TEMPLATE = 'config{i}.ini'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8080

# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['BACKUP_DIR'] = DEFAULT_BACKUP_DIR
app.config['CONFIG_DIR'] = DEFAULT_CONFIG_DIR


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _backup_dir():
    return app.config['BACKUP_DIR']


def _config_dir():
    return app.config['CONFIG_DIR']


def _list_backups():
    """Return the names of all backup archives in the backup directory."""
    return [f for f in os.listdir(_backup_dir()) if f.endswith(BACKUP_EXTENSION)]


def _requested_backup_filename():
    """Build the backup file name from the submitted form data."""
    return request.form.get('backup_name', DEFAULT_BACKUP_NAME) + BACKUP_EXTENSION


def _write_backup_archive(backup_path):
    """Archive every regular file of the config directory into backup_path."""
    config_dir = _config_dir()
    with tarfile.open(backup_path, TAR_WRITE_MODE) as tar:
        for config_file in os.listdir(config_dir):
            full_path = os.path.join(config_dir, config_file)
            if os.path.isfile(full_path):
                tar.add(full_path, arcname=config_file)


def _extract_backup_archive(backup_path):
    """Extract the archive at backup_path into the config directory."""
    with tarfile.open(backup_path, TAR_READ_MODE) as tar:
        tar.extractall(path=_config_dir())


def _validate_backup_path(backup_path):
    """Abort with an HTTP error if the backup is missing or not a tar file."""
    if not os.path.exists(backup_path):
        abort(404, 'Backup file not found')
    if not tarfile.is_tarfile(backup_path):
        abort(400, 'Invalid backup file format')


def _render_error(error, status_code):
    return (render_template(ERROR_TEMPLATE, error=str(error)), status_code)


def _ensure_directory(path):
    """Create path if missing. Return True if it was created."""
    if not os.path.exists(path):
        os.makedirs(path)
        return True
    return False


def _create_default_configs(config_dir):
    for i in range(1, DEFAULT_CONFIG_FILE_COUNT + 1):
        file_path = os.path.join(
            config_dir, DEFAULT_CONFIG_FILENAME_TEMPLATE.format(i=i)
        )
        with open(file_path, 'w') as f:
            f.write(DEFAULT_CONFIG_FILE_TEMPLATE.format(i=i))


def _prepare_directories():
    """Ensure backup/config directories exist, seeding default configs."""
    _ensure_directory(app.config['BACKUP_DIR'])
    if _ensure_directory(app.config['CONFIG_DIR']):
        _create_default_configs(app.config['CONFIG_DIR'])


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/')
def index():
    backups = []
    try:
        backups = _list_backups()
    except Exception:
        flash('Error accessing backup directory')
    return render_template(INDEX_TEMPLATE, backups=backups)


@app.route('/create_backup', methods=['POST'])
def create_backup():
    backup_name = _requested_backup_filename()
    backup_path = os.path.join(_backup_dir(), backup_name)
    try:
        _write_backup_archive(backup_path)
        flash('Backup created successfully')
    except Exception as e:
        flash(f'Backup failed: {str(e)}')
    return redirect(INDEX_URL)


@app.route('/restore_backup/<backup_file>')
def restore_config(backup_file):
    try:
        backup_path = os.path.join(_backup_dir(), backup_file)
        _validate_backup_path(backup_path)
        _extract_backup_archive(backup_path)
        flash('Configuration restored successfully')
        return redirect(INDEX_URL)
    except Exception as e:
        abort(500, f'Restoration failed: {str(e)}')


# --------------------------------------------------------------------------- #
# Error handlers
# --------------------------------------------------------------------------- #
@app.errorhandler(404)
def not_found(e):
    return _render_error(e, 404)


@app.errorhandler(400)
def bad_request(e):
    return _render_error(e, 400)


@app.errorhandler(500)
def server_error(e):
    return _render_error(e, 500)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
if __name__ == '__main__':
    _prepare_directories()
    app.run(host=SERVER_HOST, port=SERVER_PORT)
