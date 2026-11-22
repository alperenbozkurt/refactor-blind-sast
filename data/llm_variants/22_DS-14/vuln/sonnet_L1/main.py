import os
import tarfile

from flask import Flask, request, send_file, render_template, abort, flash, redirect

BACKUP_EXTENSION = '.tar.gz'
DEFAULT_BACKUP_NAME = 'config_backup'
DEFAULT_CONFIG_FILE_COUNT = 3

app = Flask(__name__)
app.secret_key = 'super_secret_key'
app.config['BACKUP_DIR'] = '/var/backups/configs'
app.config['CONFIG_DIR'] = '/etc/appconfigs'


def _list_backups():
    """Return the names of all backup archives in the backup directory."""
    return [
        name
        for name in os.listdir(app.config['BACKUP_DIR'])
        if name.endswith(BACKUP_EXTENSION)
    ]


def _add_config_files_to_archive(tar):
    """Add every regular file from the config directory to the archive."""
    config_dir = app.config['CONFIG_DIR']
    for config_file in os.listdir(config_dir):
        full_path = os.path.join(config_dir, config_file)
        if os.path.isfile(full_path):
            tar.add(full_path, arcname=config_file)


def _restore_archive(backup_file):
    """Validate the requested backup and extract it into the config directory."""
    backup_path = os.path.join(app.config['BACKUP_DIR'], backup_file)
    if not os.path.exists(backup_path):
        abort(404, 'Backup file not found')
    if not tarfile.is_tarfile(backup_path):
        abort(400, 'Invalid backup file format')
    with tarfile.open(backup_path, 'r:gz') as tar:
        tar.extractall(path=app.config['CONFIG_DIR'])


def _render_error(error, status_code):
    return render_template('error.html', error=str(error)), status_code


@app.route('/')
def index():
    backups = []
    try:
        backups = _list_backups()
    except Exception:
        flash('Error accessing backup directory')
    return render_template('backup.html', backups=backups)


@app.route('/create_backup', methods=['POST'])
def create_backup():
    backup_name = request.form.get('backup_name', DEFAULT_BACKUP_NAME) + BACKUP_EXTENSION
    backup_path = os.path.join(app.config['BACKUP_DIR'], backup_name)
    try:
        with tarfile.open(backup_path, 'w:gz') as tar:
            _add_config_files_to_archive(tar)
        flash('Backup created successfully')
    except Exception as e:
        flash(f'Backup failed: {str(e)}')
    return redirect('/')


@app.route('/restore_backup/<backup_file>')
def restore_config(backup_file):
    try:
        _restore_archive(backup_file)
        flash('Configuration restored successfully')
        return redirect('/')
    except Exception as e:
        abort(500, f'Restoration failed: {str(e)}')


@app.errorhandler(404)
def not_found(e):
    return _render_error(e, 404)


@app.errorhandler(400)
def bad_request(e):
    return _render_error(e, 400)


@app.errorhandler(500)
def server_error(e):
    return _render_error(e, 500)


def _create_default_config_files(config_dir):
    for i in range(1, DEFAULT_CONFIG_FILE_COUNT + 1):
        with open(os.path.join(config_dir, f'config{i}.ini'), 'w') as f:
            f.write(f'[DEFAULT]\nsetting{i} = value{i}\n')


def _prepare_directories():
    """Ensure the backup and config directories exist, seeding defaults if needed."""
    if not os.path.exists(app.config['BACKUP_DIR']):
        os.makedirs(app.config['BACKUP_DIR'])
    if not os.path.exists(app.config['CONFIG_DIR']):
        os.makedirs(app.config['CONFIG_DIR'])
        _create_default_config_files(app.config['CONFIG_DIR'])


if __name__ == '__main__':
    _prepare_directories()
    app.run(host='0.0.0.0', port=8080)
