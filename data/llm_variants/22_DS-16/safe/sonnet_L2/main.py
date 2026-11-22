import os
from flask import Flask, request, render_template, abort, send_file, Response
from werkzeug.utils import secure_filename

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------
DEFAULT_LOG_DIR = '/var/log'
DEFAULT_MAX_LOG_SIZE = 1024 * 1024
DEFAULT_ALLOWED_LOG_PREFIXES = ['system', 'application', 'security']
LOG_EXTENSION = '.log'

LOG_DIR_MODE = 0o750
SAMPLE_LOG_MODE = 0o640
SAMPLE_LOG_NAMES = ['system.log', 'application.log', 'security.log']
SAMPLE_LOG_REPEAT_LINE = 'Log line\n'
SAMPLE_LOG_REPEAT_COUNT = 20

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

app = Flask(__name__)
app.config['LOG_DIR'] = os.path.abspath(DEFAULT_LOG_DIR)
app.config['MAX_LOG_SIZE'] = DEFAULT_MAX_LOG_SIZE
app.config['ALLOWED_LOG_PREFIXES'] = list(DEFAULT_ALLOWED_LOG_PREFIXES)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _has_allowed_prefix(filename):
    return any((filename.startswith(prefix) for prefix in app.config['ALLOWED_LOG_PREFIXES']))


def _is_allowed_log_name(filename):
    return filename.endswith(LOG_EXTENSION) and _has_allowed_prefix(filename)


def is_safe_log_path(path):
    abs_path = os.path.abspath(path)
    if not abs_path.startswith(app.config['LOG_DIR'] + os.sep):
        return False
    if not abs_path.endswith(LOG_EXTENSION):
        return False
    filename = os.path.basename(abs_path)
    if not _has_allowed_prefix(filename):
        return False
    if os.path.islink(abs_path):
        return False
    return True


def _get_requested_log_file():
    log_file = request.args.get('file')
    if not log_file or not isinstance(log_file, str):
        abort(400, 'Invalid log file request')
    return log_file


def _build_log_path(safe_filename):
    return os.path.join(app.config['LOG_DIR'], safe_filename)


def _ensure_accessible_log(log_path):
    if not is_safe_log_path(log_path):
        abort(403, 'Access denied')
    if not os.path.exists(log_path):
        abort(404, 'Log file not found')
    if not os.path.isfile(log_path):
        abort(400, 'Invalid log file')


def _read_text_file(path):
    with open(path, 'r') as f:
        return f.read()


def _list_log_files():
    return [
        f for f in os.listdir(app.config['LOG_DIR'])
        if _is_allowed_log_name(f)
    ]


def _render_error(message, status):
    return (render_template('error.html', error=message), status)


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route('/')
def index():
    log_files = []
    try:
        log_files = _list_log_files()
    except Exception as e:
        app.logger.error(f'Error listing log files: {e}')
    return render_template('logs.html', log_files=log_files)


@app.route('/view')
def view_log():
    log_file = _get_requested_log_file()
    try:
        safe_filename = secure_filename(log_file)
        log_path = _build_log_path(safe_filename)
        _ensure_accessible_log(log_path)
        file_size = os.path.getsize(log_path)
        if file_size > app.config['MAX_LOG_SIZE']:
            return Response('Log file too large', mimetype='text/plain')
        content = _read_text_file(log_path)
        return render_template('view_log.html', log_name=safe_filename, log_content=content)
    except PermissionError:
        abort(403, 'Permission denied')
    except Exception as e:
        app.logger.error(f'Error reading log: {e}')
        abort(500, 'Internal server error')


@app.route('/download')
def download_log():
    log_file = _get_requested_log_file()
    try:
        safe_filename = secure_filename(log_file)
        log_path = _build_log_path(safe_filename)
        _ensure_accessible_log(log_path)
        return send_file(log_path, as_attachment=True)
    except PermissionError:
        abort(403, 'Permission denied')
    except Exception as e:
        app.logger.error(f'Error downloading log: {e}')
        abort(500, 'Internal server error')


# --------------------------------------------------------------------------
# Error handlers
# --------------------------------------------------------------------------
@app.errorhandler(400)
def bad_request(e):
    return _render_error('Invalid request', 400)


@app.errorhandler(403)
def forbidden(e):
    return _render_error('Access denied', 403)


@app.errorhandler(404)
def not_found(e):
    return _render_error('Resource not found', 404)


@app.errorhandler(500)
def server_error(e):
    return _render_error('Internal server error', 500)


# --------------------------------------------------------------------------
# Startup helpers
# --------------------------------------------------------------------------
def _create_sample_log(log):
    log_path = os.path.join(app.config['LOG_DIR'], log)
    if os.path.exists(log_path):
        return
    try:
        with open(log_path, 'w') as f:
            f.write(f'Sample log entries for {log}\n' + SAMPLE_LOG_REPEAT_LINE * SAMPLE_LOG_REPEAT_COUNT)
        os.chmod(log_path, SAMPLE_LOG_MODE)
    except Exception as e:
        app.logger.error(f'Error creating sample log {log}: {e}')


def _prepare_log_directory():
    os.makedirs(app.config['LOG_DIR'], mode=LOG_DIR_MODE, exist_ok=True)
    for log in SAMPLE_LOG_NAMES:
        _create_sample_log(log)


if __name__ == '__main__':
    _prepare_log_directory()
    app.run(host=SERVER_HOST, port=SERVER_PORT)
