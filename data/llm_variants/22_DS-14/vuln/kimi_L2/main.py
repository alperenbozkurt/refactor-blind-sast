"""Flask application for creating and restoring configuration file backups."""

import os
import tarfile
from dataclasses import dataclass

from flask import Flask, request, send_file, render_template, abort, flash, redirect

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_SECRET_KEY = 'super_secret_key'
DEFAULT_BACKUP_DIR = '/var/backups/configs'
DEFAULT_CONFIG_DIR = '/etc/appconfigs'

BACKUP_ARCHIVE_EXTENSION = '.tar.gz'
DEFAULT_BACKUP_BASENAME = 'config_backup'
BACKUP_WRITE_MODE = 'w:gz'
BACKUP_READ_MODE = 'r:gz'

INDEX_ROUTE = '/'
BACKUP_TEMPLATE = 'backup.html'
ERROR_TEMPLATE = 'error.html'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8080

SAMPLE_CONFIG_COUNT = 3
SAMPLE_CONFIG_FILENAME = 'config{0}.ini'
SAMPLE_CONFIG_CONTENT = '[DEFAULT]\nsetting{0} = value{0}\n'

HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500

MSG_BACKUP_DIR_ERROR = 'Error accessing backup directory'
MSG_BACKUP_CREATED = 'Backup created successfully'
MSG_BACKUP_FAILED = 'Backup failed: {0}'
MSG_BACKUP_NOT_FOUND = 'Backup file not found'
MSG_BACKUP_INVALID_FORMAT = 'Invalid backup file format'
MSG_RESTORE_SUCCESS = 'Configuration restored successfully'
MSG_RESTORE_FAILED = 'Restoration failed: {0}'


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the backup application."""
    secret_key: str = DEFAULT_SECRET_KEY
    backup_dir: str = DEFAULT_BACKUP_DIR
    config_dir: str = DEFAULT_CONFIG_DIR
    host: str = SERVER_HOST
    port: int = SERVER_PORT


SETTINGS = Settings()


def create_app(settings=SETTINGS):
    """Build and configure the Flask application instance."""
    flask_app = Flask(__name__)
    flask_app.secret_key = settings.secret_key
    flask_app.config['BACKUP_DIR'] = settings.backup_dir
    flask_app.config['CONFIG_DIR'] = settings.config_dir
    return flask_app


app = create_app()


# ---------------------------------------------------------------------------
# Backup helpers
# ---------------------------------------------------------------------------

def _list_backup_archives(backup_dir):
    """Return the names of all backup archives contained in *backup_dir*."""
    return [name for name in os.listdir(backup_dir)
            if name.endswith(BACKUP_ARCHIVE_EXTENSION)]


def _build_backup_archive(archive_path, config_dir):
    """Write every regular file from *config_dir* into a gzipped tarball."""
    with tarfile.open(archive_path, BACKUP_WRITE_MODE) as tar:
        for config_file in os.listdir(config_dir):
            full_path = os.path.join(config_dir, config_file)
            if os.path.isfile(full_path):
                tar.add(full_path, arcname=config_file)


def _validate_backup_archive(archive_path):
    """Abort with the matching HTTP error if the archive cannot be restored."""
    if not os.path.exists(archive_path):
        abort(HTTP_NOT_FOUND, MSG_BACKUP_NOT_FOUND)
    if not tarfile.is_tarfile(archive_path):
        abort(HTTP_BAD_REQUEST, MSG_BACKUP_INVALID_FORMAT)


def _extract_backup_archive(archive_path, config_dir):
    """Extract the contents of the backup archive into *config_dir*."""
    with tarfile.open(archive_path, BACKUP_READ_MODE) as tar:
        tar.extractall(path=config_dir)


def _render_error_page(error, status_code):
    """Render the shared error template for the given status code."""
    return (render_template(ERROR_TEMPLATE, error=str(error)), status_code)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    backups = []
    try:
        backups = _list_backup_archives(app.config['BACKUP_DIR'])
    except Exception:
        flash(MSG_BACKUP_DIR_ERROR)
    return render_template(BACKUP_TEMPLATE, backups=backups)


@app.route('/create_backup', methods=['POST'])
def create_backup():
    backup_name = (request.form.get('backup_name', DEFAULT_BACKUP_BASENAME)
                   + BACKUP_ARCHIVE_EXTENSION)
    backup_path = os.path.join(app.config['BACKUP_DIR'], backup_name)
    try:
        _build_backup_archive(backup_path, app.config['CONFIG_DIR'])
        flash(MSG_BACKUP_CREATED)
    except Exception as e:
        flash(MSG_BACKUP_FAILED.format(str(e)))
    return redirect(INDEX_ROUTE)


@app.route('/restore_backup/<backup_file>')
def restore_config(backup_file):
    try:
        backup_path = os.path.join(app.config['BACKUP_DIR'], backup_file)
        _validate_backup_archive(backup_path)
        _extract_backup_archive(backup_path, app.config['CONFIG_DIR'])
        flash(MSG_RESTORE_SUCCESS)
        return redirect(INDEX_ROUTE)
    except Exception as e:
        abort(HTTP_INTERNAL_SERVER_ERROR, MSG_RESTORE_FAILED.format(str(e)))


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return _render_error_page(e, HTTP_NOT_FOUND)


@app.errorhandler(400)
def bad_request(e):
    return _render_error_page(e, HTTP_BAD_REQUEST)


@app.errorhandler(500)
def server_error(e):
    return _render_error_page(e, HTTP_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# Bootstrap helpers and entry point
# ---------------------------------------------------------------------------

def _ensure_backup_dir(backup_dir):
    """Create the backup directory if it does not exist yet."""
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)


def _ensure_config_dir(config_dir):
    """Create the config directory, seeding sample configs, if missing."""
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
        _create_sample_configs(config_dir)


def _create_sample_configs(config_dir):
    """Write the default sample configuration files into *config_dir*."""
    for i in range(1, SAMPLE_CONFIG_COUNT + 1):
        sample_path = os.path.join(config_dir, SAMPLE_CONFIG_FILENAME.format(i))
        with open(sample_path, 'w') as f:
            f.write(SAMPLE_CONFIG_CONTENT.format(i))


def main():
    """Prepare the working directories and start the web server."""
    _ensure_backup_dir(app.config['BACKUP_DIR'])
    _ensure_config_dir(app.config['CONFIG_DIR'])
    app.run(host=SETTINGS.host, port=SETTINGS.port)


if __name__ == '__main__':
    main()
