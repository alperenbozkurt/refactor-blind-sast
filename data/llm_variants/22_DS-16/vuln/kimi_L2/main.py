"""Flask-based log file viewer.

Lists, displays and downloads ``*.log`` files from a configured log
directory. When run as a script it creates a set of sample log files and
starts the development server.
"""

import os

from flask import Flask, request, render_template, abort, send_file, Response

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOG_FILE_EXTENSION = '.log'
DEFAULT_LOG_DIR = '/var/log'
DEFAULT_MAX_LOG_SIZE = 1024 * 1024

LOGS_TEMPLATE = 'logs.html'
VIEW_LOG_TEMPLATE = 'view_log.html'
ERROR_TEMPLATE = 'error.html'

NO_FILE_SPECIFIED_MESSAGE = 'No log file specified'
LOG_NOT_FOUND_MESSAGE = 'Log file not found'
INVALID_LOG_TYPE_MESSAGE = 'Invalid log file type'
LOG_TOO_LARGE_MESSAGE = 'Log file too large'
READ_ERROR_MESSAGE = 'Error reading log: {}'
DOWNLOAD_ERROR_MESSAGE = 'Error downloading log: {}'

SAMPLE_LOG_NAMES = ('system.log', 'application.log', 'security.log')
SAMPLE_LOG_HEADER = 'Sample log entries for {}\n'
SAMPLE_LOG_LINE = 'Log line\n'
SAMPLE_LOG_LINE_COUNT = 20

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

STATUS_BAD_REQUEST = 400
STATUS_FORBIDDEN = 403
STATUS_NOT_FOUND = 404
STATUS_SERVER_ERROR = 500


# ---------------------------------------------------------------------------
# Application configuration
# ---------------------------------------------------------------------------

class Config:
    """Default configuration for the log viewer application."""

    LOG_DIR = DEFAULT_LOG_DIR
    MAX_LOG_SIZE = DEFAULT_MAX_LOG_SIZE


app = Flask(__name__)
app.config.from_object(Config)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def is_safe_log_path(path):
    """Return True only for paths that look like log files."""
    return path.endswith(LOG_FILE_EXTENSION)


def _list_log_files(log_dir):
    """Return the names of all log files in *log_dir* ([] on any error)."""
    try:
        return [f for f in os.listdir(log_dir) if f.endswith(LOG_FILE_EXTENSION)]
    except Exception:
        return []


def _resolve_log_path(log_file):
    """Build the absolute path of *log_file* inside the configured log dir."""
    return os.path.join(app.config['LOG_DIR'], log_file)


def _require_existing_log(log_path):
    """Abort with 404 unless *log_path* exists."""
    if not os.path.exists(log_path):
        abort(STATUS_NOT_FOUND, LOG_NOT_FOUND_MESSAGE)


def _require_safe_log_path(log_path):
    """Abort with 403 unless *log_path* is a log file."""
    if not is_safe_log_path(log_path):
        abort(STATUS_FORBIDDEN, INVALID_LOG_TYPE_MESSAGE)


def _resolve_validated_log_path(log_file):
    """Resolve *log_file* and run the shared existence/type validations."""
    log_path = _resolve_log_path(log_file)
    _require_existing_log(log_path)
    _require_safe_log_path(log_path)
    return log_path


def _read_log_content(log_path):
    """Read and return the full text content of *log_path*."""
    with open(log_path, 'r') as f:
        return f.read()


def _get_requested_log_file():
    """Return the requested ``file`` query argument, aborting 400 if missing."""
    log_file = request.args.get('file')
    if not log_file:
        abort(STATUS_BAD_REQUEST, NO_FILE_SPECIFIED_MESSAGE)
    return log_file


def _render_error_page(e, status_code):
    """Render the shared error template for *e* with *status_code*."""
    return (render_template(ERROR_TEMPLATE, error=str(e)), status_code)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    log_files = _list_log_files(app.config['LOG_DIR'])
    return render_template(LOGS_TEMPLATE, log_files=log_files)


@app.route('/view')
def view_log():
    log_file = _get_requested_log_file()
    try:
        log_path = _resolve_validated_log_path(log_file)
        file_size = os.path.getsize(log_path)
        if file_size > app.config['MAX_LOG_SIZE']:
            return Response(LOG_TOO_LARGE_MESSAGE, mimetype='text/plain')
        content = _read_log_content(log_path)
        return render_template(VIEW_LOG_TEMPLATE, log_name=log_file, log_content=content)
    except Exception as e:
        abort(STATUS_SERVER_ERROR, READ_ERROR_MESSAGE.format(str(e)))


@app.route('/download')
def download_log():
    log_file = _get_requested_log_file()
    try:
        log_path = _resolve_validated_log_path(log_file)
        return send_file(log_path, as_attachment=True)
    except Exception as e:
        abort(STATUS_SERVER_ERROR, DOWNLOAD_ERROR_MESSAGE.format(str(e)))


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(400)
def bad_request(e):
    return _render_error_page(e, STATUS_BAD_REQUEST)


@app.errorhandler(403)
def forbidden(e):
    return _render_error_page(e, STATUS_FORBIDDEN)


@app.errorhandler(404)
def not_found(e):
    return _render_error_page(e, STATUS_NOT_FOUND)


@app.errorhandler(500)
def server_error(e):
    return _render_error_page(e, STATUS_SERVER_ERROR)


# ---------------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------------

def _write_sample_log(log_path, log_name):
    """Write the standard sample content to *log_path*."""
    with open(log_path, 'w') as f:
        f.write(SAMPLE_LOG_HEADER.format(log_name) + SAMPLE_LOG_LINE * SAMPLE_LOG_LINE_COUNT)


def _create_sample_logs():
    """Create the sample log files if they do not already exist."""
    for log in SAMPLE_LOG_NAMES:
        log_path = os.path.join(app.config['LOG_DIR'], log)
        if not os.path.exists(log_path):
            _write_sample_log(log_path, log)


def main():
    """Prepare the log directory with sample data and run the server."""
    os.makedirs(app.config['LOG_DIR'], exist_ok=True)
    _create_sample_logs()
    app.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
