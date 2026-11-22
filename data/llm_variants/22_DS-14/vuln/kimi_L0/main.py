import os
import tarfile

from flask import Flask, abort, flash, redirect, render_template, request, send_file

app = Flask(__name__)
app.secret_key = 'super_secret_key'
app.config['BACKUP_DIR'] = '/var/backups/configs'
app.config['CONFIG_DIR'] = '/etc/appconfigs'

BACKUP_EXTENSION = '.tar.gz'
SAMPLE_CONFIG_COUNT = 3


def _list_backups():
    """Return the available backup archives, flashing on directory errors."""
    try:
        return [
            filename
            for filename in os.listdir(app.config['BACKUP_DIR'])
            if filename.endswith(BACKUP_EXTENSION)
        ]
    except Exception:
        flash('Error accessing backup directory')
        return []


def _iter_config_files():
    """Yield (name, path) pairs for each regular file in the config directory."""
    for filename in os.listdir(app.config['CONFIG_DIR']):
        full_path = os.path.join(app.config['CONFIG_DIR'], filename)
        if os.path.isfile(full_path):
            yield filename, full_path


def _render_error(error, status_code):
    """Render the error template paired with the given HTTP status code."""
    return render_template('error.html', error=str(error)), status_code


@app.route('/')
def index():
    return render_template('backup.html', backups=_list_backups())


@app.route('/create_backup', methods=['POST'])
def create_backup():
    backup_name = request.form.get('backup_name', 'config_backup') + BACKUP_EXTENSION
    backup_path = os.path.join(app.config['BACKUP_DIR'], backup_name)
    try:
        with tarfile.open(backup_path, 'w:gz') as tar:
            for filename, full_path in _iter_config_files():
                tar.add(full_path, arcname=filename)
        flash('Backup created successfully')
    except Exception as e:
        flash(f'Backup failed: {str(e)}')
    return redirect('/')


@app.route('/restore_backup/<backup_file>')
def restore_config(backup_file):
    try:
        backup_path = os.path.join(app.config['BACKUP_DIR'], backup_file)
        if not os.path.exists(backup_path):
            abort(404, 'Backup file not found')
        if not tarfile.is_tarfile(backup_path):
            abort(400, 'Invalid backup file format')
        with tarfile.open(backup_path, 'r:gz') as tar:
            tar.extractall(path=app.config['CONFIG_DIR'])
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


def _create_sample_configs():
    for i in range(1, SAMPLE_CONFIG_COUNT + 1):
        sample_path = os.path.join(app.config['CONFIG_DIR'], f'config{i}.ini')
        with open(sample_path, 'w') as f:
            f.write(f'[DEFAULT]\nsetting{i} = value{i}\n')


def _ensure_directories():
    if not os.path.exists(app.config['BACKUP_DIR']):
        os.makedirs(app.config['BACKUP_DIR'])
    if not os.path.exists(app.config['CONFIG_DIR']):
        os.makedirs(app.config['CONFIG_DIR'])
        _create_sample_configs()


if __name__ == '__main__':
    _ensure_directories()
    app.run(host='0.0.0.0', port=8080)
