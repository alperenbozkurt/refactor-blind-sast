import os
from datetime import datetime

from flask import Flask, abort, render_template_string, request, send_file

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

DEFAULT_LOG_DIR = '/var/log/app_logs'
DEFAULT_MAX_LOG_SIZE = 1024 * 1024
DEFAULT_MAX_LINES = 1000

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000

BACKUP_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
LOG_ENTRY_TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'
BACKUP_SUFFIX = '.bak'

HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_ERROR = 500

STATUS_SUCCESS = 'success'
ERROR_MISSING_FIELDS = 'Missing filename or message'
ERROR_WRITE_FAILED = 'Failed to write log'
ERROR_LOG_NOT_FOUND = 'Log file not found or inaccessible'
ERROR_FILE_NOT_FOUND = 'Log file not found'
ERROR_NOT_A_FILE = 'Requested path is not a file'

LOG_VIEW_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Log Viewer - {{ filename }}</title>
</head>
<body>
    <h1>Log File: {{ filename }}</h1>
    <pre>{{ log_content }}</pre>
</body>
</html>
"""

app = Flask(__name__)


def configure_app(application):
    """Apply the default log viewer configuration to the Flask app."""
    application.config['LOG_DIR'] = DEFAULT_LOG_DIR
    application.config['MAX_LOG_SIZE'] = DEFAULT_MAX_LOG_SIZE


configure_app(app)


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------

def _log_dir():
    return app.config['LOG_DIR']


def _log_path(filename):
    return os.path.join(_log_dir(), filename)


def _read_first_lines(file_path, max_lines):
    lines = []
    with open(file_path, 'r') as f:
        for (i, line) in enumerate(f):
            if i >= max_lines:
                break
            lines.append(line)
    return ''.join(lines)


def _list_log_filenames():
    return [
        entry
        for entry in os.listdir(_log_dir())
        if os.path.isfile(_log_path(entry))
    ]


def _current_timestamp(format_string):
    return datetime.now().strftime(format_string)


# ---------------------------------------------------------------------------
# Log management
# ---------------------------------------------------------------------------

class LogManager:

    def __init__(self):
        os.makedirs(_log_dir(), exist_ok=True)

    # -- internal helpers ---------------------------------------------------

    @staticmethod
    def _backup_name(log_file):
        timestamp = _current_timestamp(BACKUP_TIMESTAMP_FORMAT)
        return f'{log_file}.{timestamp}{BACKUP_SUFFIX}'

    @staticmethod
    def _format_entry(message):
        timestamp = _current_timestamp(LOG_ENTRY_TIMESTAMP_FORMAT)
        return f'[{timestamp}] {message}\n'

    def _is_oversized(self, file_path):
        return os.path.getsize(file_path) > app.config['MAX_LOG_SIZE']

    # -- public API ----------------------------------------------------------

    def rotate_logs(self):
        for log_file in os.listdir(_log_dir()):
            file_path = _log_path(log_file)
            if self._is_oversized(file_path):
                backup_path = _log_path(self._backup_name(log_file))
                os.rename(file_path, backup_path)

    def get_log_file(self, filename, max_lines=DEFAULT_MAX_LINES):
        file_path = _log_path(filename)
        try:
            if not os.path.exists(file_path):
                return None
            if not os.path.isfile(file_path):
                return None
            return _read_first_lines(file_path, max_lines)
        except Exception:
            return None

    def write_log(self, filename, message):
        file_path = _log_path(filename)
        try:
            with open(file_path, 'a') as f:
                f.write(self._format_entry(message))
            return True
        except Exception:
            return False


log_manager = LogManager()


# ---------------------------------------------------------------------------
# Request helpers
# ---------------------------------------------------------------------------

def _parse_log_entry(data):
    """Extract (filename, message) from request JSON, or None if invalid."""
    if not data or 'filename' not in data or 'message' not in data:
        return None
    return data['filename'], data['message']


def _resolve_download_path(filename):
    """Validate that filename maps to an existing file and return its path."""
    file_path = _log_path(filename)
    if not os.path.exists(file_path):
        abort(HTTP_NOT_FOUND, description=ERROR_FILE_NOT_FOUND)
    if not os.path.isfile(file_path):
        abort(HTTP_BAD_REQUEST, description=ERROR_NOT_A_FILE)
    return file_path


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/log', methods=['POST'])
def write_log_entry():
    entry = _parse_log_entry(request.get_json())
    if entry is None:
        abort(HTTP_BAD_REQUEST, description=ERROR_MISSING_FIELDS)
    filename, message = entry
    if log_manager.write_log(filename, message):
        return ({'status': STATUS_SUCCESS}, HTTP_CREATED)
    return ({'error': ERROR_WRITE_FAILED}, HTTP_INTERNAL_ERROR)


@app.route('/log/<path:filename>')
def view_log_file(filename):
    log_content = log_manager.get_log_file(filename)
    if log_content is None:
        abort(HTTP_NOT_FOUND, description=ERROR_LOG_NOT_FOUND)
    return render_template_string(LOG_VIEW_TEMPLATE, filename=filename, log_content=log_content)


@app.route('/log/download/<path:filename>')
def download_log_file(filename):
    file_path = _resolve_download_path(filename)
    try:
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        abort(HTTP_INTERNAL_ERROR, description=str(e))


@app.route('/logs')
def list_log_files():
    try:
        return {'logs': _list_log_filenames()}
    except Exception as e:
        abort(HTTP_INTERNAL_ERROR, description=str(e))


# ---------------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------------

def main():
    log_manager.rotate_logs()
    app.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
