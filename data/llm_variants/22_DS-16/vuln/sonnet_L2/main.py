import os
from flask import Flask, request, render_template, abort, send_file, Response

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
DEFAULT_LOG_DIR = '/var/log'
DEFAULT_MAX_LOG_SIZE = 1024 * 1024
LOG_EXTENSION = '.log'

FILE_PARAM = 'file'

INDEX_TEMPLATE = 'logs.html'
VIEW_TEMPLATE = 'view_log.html'
ERROR_TEMPLATE = 'error.html'

SAMPLE_LOGS = ['system.log', 'application.log', 'security.log']
SAMPLE_LOG_LINE = 'Log line\n'
SAMPLE_LOG_LINE_COUNT = 20

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #
app = Flask(__name__)
app.config['LOG_DIR'] = DEFAULT_LOG_DIR
app.config['MAX_LOG_SIZE'] = DEFAULT_MAX_LOG_SIZE


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def is_safe_log_path(path):
    return path.endswith(LOG_EXTENSION)


def _list_log_files():
    """Return log file names in the log directory (empty list on any error)."""
    try:
        return [f for f in os.listdir(app.config['LOG_DIR'])
                if f.endswith(LOG_EXTENSION)]
    except Exception:
        return []


def _get_requested_log_file():
    """Return the requested log file name, aborting with 400 if missing."""
    log_file = request.args.get(FILE_PARAM)
    if not log_file:
        abort(400, 'No log file specified')
    return log_file


def _build_log_path(log_file):
    # NOTE: behaviour intentionally preserved; the name is joined as-is and
    # only the extension is validated (see is_safe_log_path).
    return os.path.join(app.config['LOG_DIR'], log_file)


def _validate_log_path(log_path):
    """Abort with 404/403 if the path is missing or not an allowed log type."""
    if not os.path.exists(log_path):
        abort(404, 'Log file not found')
    if not is_safe_log_path(log_path):
        abort(403, 'Invalid log file type')


def _read_text_file(path):
    with open(path, 'r') as f:
        return f.read()


def _render_error(e, status_code):
    return (render_template(ERROR_TEMPLATE, error=str(e)), status_code)


def _create_sample_logs():
    """Create the sample log files if they do not already exist."""
    for log in SAMPLE_LOGS:
        log_path = os.path.join(app.config['LOG_DIR'], log)
        if not os.path.exists(log_path):
            with open(log_path, 'w') as f:
                f.write(f'Sample log entries for {log}\n'
                        + SAMPLE_LOG_LINE * SAMPLE_LOG_LINE_COUNT)


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/')
def index():
    return render_template(INDEX_TEMPLATE, log_files=_list_log_files())


@app.route('/view')
def view_log():
    log_file = _get_requested_log_file()
    try:
        log_path = _build_log_path(log_file)
        _validate_log_path(log_path)
        file_size = os.path.getsize(log_path)
        if file_size > app.config['MAX_LOG_SIZE']:
            return Response('Log file too large', mimetype='text/plain')
        content = _read_text_file(log_path)
        return render_template(VIEW_TEMPLATE, log_name=log_file, log_content=content)
    except Exception as e:
        abort(500, f'Error reading log: {str(e)}')


@app.route('/download')
def download_log():
    log_file = _get_requested_log_file()
    try:
        log_path = _build_log_path(log_file)
        _validate_log_path(log_path)
        return send_file(log_path, as_attachment=True)
    except Exception as e:
        abort(500, f'Error downloading log: {str(e)}')


# --------------------------------------------------------------------------- #
# Error handlers
# --------------------------------------------------------------------------- #
@app.errorhandler(400)
def bad_request(e):
    return _render_error(e, 400)


@app.errorhandler(403)
def forbidden(e):
    return _render_error(e, 403)


@app.errorhandler(404)
def not_found(e):
    return _render_error(e, 404)


@app.errorhandler(500)
def server_error(e):
    return _render_error(e, 500)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
if __name__ == '__main__':
    os.makedirs(app.config['LOG_DIR'], exist_ok=True)
    _create_sample_logs()
    app.run(host=SERVER_HOST, port=SERVER_PORT)
