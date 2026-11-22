import os
import tarfile

from flask import (
    Flask,
    request,
    send_file,
    render_template,
    abort,
    flash,
    redirect,
)

app = Flask(__name__)
app.secret_key = 'super_secret_key'
app.config['BACKUP_DIR'] = '/var/backups/configs'
app.config['CONFIG_DIR'] = '/etc/appconfigs'

BACKUP_EXTENSION = '.tar.gz'


def _list_backups():
    backup_dir = app.config['BACKUP_DIR']
    return [f for f in os.listdir(backup_dir) if f.endswith(BACKUP_EXTENSION)]


def _add_config_files(tar):
    config_dir = app.config['CONFIG_DIR']
    for config_file in os.listdir(config_dir):
        full_path = os.path.join(config_dir, config_file)
        if os.path.isfile(full_path):
            tar.add(full_path, arcname=config_file)


def _render_error(e, status_code):
    return render_template('error.html', error=str(e)), status_code


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
    backup_name = request.form.get('backup_name', 'config_backup') + BACKUP_EXTENSION
    backup_path = os.path.join(app.config['BACKUP_DIR'], backup_name)
    try:
        with tarfile.open(backup_path, 'w:gz') as tar:
            _add_config_files(tar)
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


def _ensure_directories():
    backup_dir = app.config['BACKUP_DIR']
    config_dir = app.config['CONFIG_DIR']

    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
        for i in range(1, 4):
            path = os.path.join(config_dir, f'config{i}.ini')
            with open(path, 'w') as f:
                f.write(f'[DEFAULT]\nsetting{i} = value{i}\n')


if __name__ == '__main__':
    _ensure_directories()
    app.run(host='0.0.0.0', port=8080)
