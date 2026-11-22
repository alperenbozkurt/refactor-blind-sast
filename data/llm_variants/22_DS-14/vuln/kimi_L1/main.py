"""Flask application for creating and restoring configuration backups."""

import os
import tarfile

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
)

app = Flask(__name__)
app.secret_key = 'super_secret_key'
app.config['BACKUP_DIR'] = '/var/backups/configs'
app.config['CONFIG_DIR'] = '/etc/appconfigs'

BACKUP_FILE_EXTENSION = '.tar.gz'
DEFAULT_BACKUP_NAME = 'config_backup'
INDEX_URL = '/'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8080

SAMPLE_CONFIG_COUNT = 3


def list_backup_files():
    """Return the names of all backup archives in the backup directory."""
    try:
        return [
            filename
            for filename in os.listdir(app.config['BACKUP_DIR'])
            if filename.endswith(BACKUP_FILE_EXTENSION)
        ]
    except Exception:
        flash('Error accessing backup directory')
        return []


def add_config_files_to_archive(tar):
    """Add every regular file from the config directory to the archive."""
    for config_file in os.listdir(app.config['CONFIG_DIR']):
        full_path = os.path.join(app.config['CONFIG_DIR'], config_file)
        if os.path.isfile(full_path):
            tar.add(full_path, arcname=config_file)


def extract_backup_archive(backup_path):
    """Extract the given backup archive into the config directory."""
    with tarfile.open(backup_path, 'r:gz') as tar:
        tar.extractall(path=app.config['CONFIG_DIR'])


@app.route('/')
def index():
    backups = list_backup_files()
    return render_template('backup.html', backups=backups)


@app.route('/create_backup', methods=['POST'])
def create_backup():
    backup_name = (
        request.form.get('backup_name', DEFAULT_BACKUP_NAME)
        + BACKUP_FILE_EXTENSION
    )
    backup_path = os.path.join(app.config['BACKUP_DIR'], backup_name)
    try:
        with tarfile.open(backup_path, 'w:gz') as tar:
            add_config_files_to_archive(tar)
        flash('Backup created successfully')
    except Exception as e:
        flash(f'Backup failed: {str(e)}')
    return redirect(INDEX_URL)


@app.route('/restore_backup/<backup_file>')
def restore_config(backup_file):
    try:
        backup_path = os.path.join(app.config['BACKUP_DIR'], backup_file)
        if not os.path.exists(backup_path):
            abort(404, 'Backup file not found')
        if not tarfile.is_tarfile(backup_path):
            abort(400, 'Invalid backup file format')
        extract_backup_archive(backup_path)
        flash('Configuration restored successfully')
        return redirect(INDEX_URL)
    except Exception as e:
        abort(500, f'Restoration failed: {str(e)}')


@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', error=str(e)), 404


@app.errorhandler(400)
def bad_request(e):
    return render_template('error.html', error=str(e)), 400


@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', error=str(e)), 500


def ensure_directory_exists(path):
    """Create the given directory if it does not already exist."""
    if not os.path.exists(path):
        os.makedirs(path)


def create_sample_configs():
    """Write the default sample configuration files."""
    for i in range(1, SAMPLE_CONFIG_COUNT + 1):
        config_path = os.path.join(
            app.config['CONFIG_DIR'], f'config{i}.ini'
        )
        with open(config_path, 'w') as f:
            f.write(f'[DEFAULT]\nsetting{i} = value{i}\n')


def prepare_config_directory():
    """Create the config directory and seed it with sample files if missing."""
    if not os.path.exists(app.config['CONFIG_DIR']):
        os.makedirs(app.config['CONFIG_DIR'])
        create_sample_configs()


def main():
    ensure_directory_exists(app.config['BACKUP_DIR'])
    prepare_config_directory()
    app.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
