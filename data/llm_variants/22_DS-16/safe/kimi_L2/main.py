import os
from flask import Flask, request, render_template, abort, send_file, Response
from werkzeug.utils import secure_filename

CONFIG_LOG_DIR = 'LOG_DIR'
CONFIG_MAX_LOG_SIZE = 'MAX_LOG_SIZE'
CONFIG_ALLOWED_LOG_PREFIXES = 'ALLOWED_LOG_PREFIXES'

DEFAULT_LOG_DIR = os.path.abspath('/var/log')
DEFAULT_MAX_LOG_SIZE = 1024 * 1024
DEFAULT_ALLOWED_LOG_PREFIXES = ('system', 'application', 'security')

LOG_FILE_EXTENSION = '.log'
LOG_DIR_MODE = 488
SAMPLE_LOG_MODE = 416
SAMPLE_LOGS = ('system.log', 'application.log', 'security.log')
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

INVALID_LOG_FILE_REQUEST = 'Invalid log file request'
ACCESS_DENIED = 'Access denied'
LOG_FILE_NOT_FOUND = 'Log file not found'
INVALID_LOG_FILE = 'Invalid log file'
PERMISSION_DENIED = 'Permission denied'
INTERNAL_SERVER_ERROR = 'Internal server error'
LOG_FILE_TOO_LARGE = 'Log file too large'
TEXT_MIMETYPE = 'text/plain'

app = Flask(__name__)
app.config[CONFIG_LOG_DIR] = DEFAULT_LOG_DIR
app.config[CONFIG_MAX_LOG_SIZE] = DEFAULT_MAX_LOG_SIZE
app.config[CONFIG_ALLOWED_LOG_PREFIXES] = list(DEFAULT_ALLOWED_LOG_PREFIXES)


def _is_within_log_dir(abs_path):
    return abs_path.startswith(app.config[CONFIG_LOG_DIR] + os.sep)


def _has_allowed_log_prefix(filename):
    return any(
        (filename.startswith(prefix) for prefix in app.config[CONFIG_ALLOWED_LOG_PREFIXES])
    )


def is_safe_log_path(path):
    abs_path = os.path.abspath(path)
    if not _is_within_log_dir(abs_path):
        return False
    if not abs_path.endswith(LOG_FILE_EXTENSION):
        return False
    filename = os.path.basename(abs_path)
    if not _has_allowed_log_prefix(filename):
        return False
    if os.path.islink(abs_path):
        return False
    return True


def _list_log_files():
    try:
        return [
            f
            for f in os.listdir(app.config[CONFIG_LOG_DIR])
            if f.endswith(LOG_FILE_EXTENSION) and _has_allowed_log_prefix(f)
        ]
    except Exception as e:
        app.logger.error(f'Error listing log files: {e}')
        return []


def _required_log_file_argument():
    log_file = request.args.get('file')
    if not log_file or not isinstance(log_file, str):
        abort(400, INVALID_LOG_FILE_REQUEST)
    return log_file


def _validated_log_path(log_file):
    safe_filename = secure_filename(log_file)
    log_path = os.path.join(app.config[CONFIG_LOG_DIR], safe_filename)
    if not is_safe_log_path(log_path):
        abort(403, ACCESS_DENIED)
    if not os.path.exists(log_path):
        abort(404, LOG_FILE_NOT_FOUND)
    if not os.path.isfile(log_path):
        abort(400, INVALID_LOG_FILE)
    return safe_filename, log_path


def _read_log_file(log_path):
    with open(log_path, 'r') as f:
        return f.read()


@app.route('/')
def index():
    log_files = _list_log_files()
    return render_template('logs.html', log_files=log_files)


@app.route('/view')
def view_log():
    log_file = _required_log_file_argument()
    try:
        safe_filename, log_path = _validated_log_path(log_file)
        file_size = os.path.getsize(log_path)
        if file_size > app.config[CONFIG_MAX_LOG_SIZE]:
            return Response(LOG_FILE_TOO_LARGE, mimetype=TEXT_MIMETYPE)
        content = _read_log_file(log_path)
        return render_template('view_log.html', log_name=safe_filename, log_content=content)
    except PermissionError:
        abort(403, PERMISSION_DENIED)
    except Exception as e:
        app.logger.error(f'Error reading log: {e}')
        abort(500, INTERNAL_SERVER_ERROR)


@app.route('/download')
def download_log():
    log_file = _required_log_file_argument()
    try:
        safe_filename, log_path = _validated_log_path(log_file)
        return send_file(log_path, as_attachment=True)
    except PermissionError:
        abort(403, PERMISSION_DENIED)
    except Exception as e:
        app.logger.error(f'Error downloading log: {e}')
        abort(500, INTERNAL_SERVER_ERROR)


def _render_error(error, status_code):
    return (render_template('error.html', error=error), status_code)


@app.errorhandler(400)
def bad_request(e):
    return _render_error('Invalid request', 400)


@app.errorhandler(403)
def forbidden(e):
    return _render_error(ACCESS_DENIED, 403)


@app.errorhandler(404)
def not_found(e):
    return _render_error('Resource not found', 404)


@app.errorhandler(500)
def server_error(e):
    return _render_error(INTERNAL_SERVER_ERROR, 500)


def _sample_log_content(log_name):
    return f'Sample log entries for {log_name}\n' + 'Log line\n' * 20


def _create_sample_log_if_missing(log_name):
    log_path = os.path.join(app.config[CONFIG_LOG_DIR], log_name)
    if os.path.exists(log_path):
        return
    try:
        with open(log_path, 'w') as f:
            f.write(_sample_log_content(log_name))
        os.chmod(log_path, SAMPLE_LOG_MODE)
    except Exception as e:
        app.logger.error(f'Error creating sample log {log_name}: {e}')


if __name__ == '__main__':
    os.makedirs(app.config[CONFIG_LOG_DIR], mode=LOG_DIR_MODE, exist_ok=True)
    sample_logs = list(SAMPLE_LOGS)
    for log in sample_logs:
        _create_sample_log_if_missing(log)
    app.run(host=SERVER_HOST, port=SERVER_PORT)
