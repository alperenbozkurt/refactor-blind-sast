import os
from flask import Flask, request, send_file, abort, render_template_string
from datetime import datetime

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_LOG_DIR = '/var/log/app_logs'
DEFAULT_MAX_LOG_SIZE = 1024 * 1024
DEFAULT_MAX_LINES = 1000

BACKUP_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
ENTRY_TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000

LOG_VIEW_TEMPLATE = '\n<!DOCTYPE html>\n<html>\n<head>\n    <title>Log Viewer - {{ filename }}</title>\n</head>\n<body>\n    <h1>Log File: {{ filename }}</h1>\n    <pre>{{ log_content }}</pre>\n</body>\n</html>\n'

# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config['LOG_DIR'] = DEFAULT_LOG_DIR
app.config['MAX_LOG_SIZE'] = DEFAULT_MAX_LOG_SIZE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _log_dir():
    """Return the currently configured log directory."""
    return app.config['LOG_DIR']


def _max_log_size():
    """Return the currently configured maximum log size in bytes."""
    return app.config['MAX_LOG_SIZE']


def _timestamp(fmt):
    """Return the current time formatted with ``fmt``."""
    return datetime.now().strftime(fmt)


# NOTE: path resolution intentionally preserves the original behaviour
# (plain join with the log directory). Callers that need stricter
# confinement to LOG_DIR should add validation here.
def _resolve_log_path(filename):
    """Return the full path for ``filename`` inside the log directory."""
    return os.path.join(_log_dir(), filename)


def _read_lines(file_path, max_lines):
    """Read at most ``max_lines`` lines from ``file_path`` and join them."""
    with open(file_path, 'r') as f:
        lines = []
        for (i, line) in enumerate(f):
            if i >= max_lines:
                break
            lines.append(line)
        return ''.join(lines)


def _format_entry(message):
    """Format a log entry with a leading timestamp and trailing newline."""
    return f'[{_timestamp(ENTRY_TIMESTAMP_FORMAT)}] {message}\n'


def _backup_name(log_file):
    """Build the rotated backup file name for ``log_file``."""
    return f'{log_file}.{_timestamp(BACKUP_TIMESTAMP_FORMAT)}.bak'


def _is_valid_log_payload(data):
    """Check that a request payload contains the required fields."""
    return bool(data) and 'filename' in data and 'message' in data


# ---------------------------------------------------------------------------
# Log management
# ---------------------------------------------------------------------------
class LogManager:

    def __init__(self):
        os.makedirs(_log_dir(), exist_ok=True)

    def rotate_logs(self):
        for log_file in os.listdir(_log_dir()):
            file_path = _resolve_log_path(log_file)
            if os.path.getsize(file_path) > _max_log_size():
                new_name = _backup_name(log_file)
                os.rename(file_path, _resolve_log_path(new_name))

    def get_log_file(self, filename, max_lines=DEFAULT_MAX_LINES):
        file_path = _resolve_log_path(filename)
        try:
            if not os.path.exists(file_path):
                return None
            if not os.path.isfile(file_path):
                return None
            return _read_lines(file_path, max_lines)
        except Exception:
            return None

    def write_log(self, filename, message):
        file_path = _resolve_log_path(filename)
        try:
            with open(file_path, 'a') as f:
                f.write(_format_entry(message))
            return True
        except Exception:
            return False


log_manager = LogManager()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/log', methods=['POST'])
def write_log_entry():
    data = request.get_json()
    if not _is_valid_log_payload(data):
        abort(400, description='Missing filename or message')
    if log_manager.write_log(data['filename'], data['message']):
        return ({'status': 'success'}, 201)
    else:
        return ({'error': 'Failed to write log'}, 500)


@app.route('/log/<path:filename>')
def view_log_file(filename):
    log_content = log_manager.get_log_file(filename)
    if log_content is None:
        abort(404, description='Log file not found or inaccessible')
    return render_template_string(LOG_VIEW_TEMPLATE, filename=filename, log_content=log_content)


@app.route('/log/download/<path:filename>')
def download_log_file(filename):
    file_path = _resolve_log_path(filename)
    if not os.path.exists(file_path):
        abort(404, description='Log file not found')
    if not os.path.isfile(file_path):
        abort(400, description='Requested path is not a file')
    try:
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        abort(500, description=str(e))


@app.route('/logs')
def list_log_files():
    try:
        logs = [f for f in os.listdir(_log_dir()) if os.path.isfile(_resolve_log_path(f))]
        return {'logs': logs}
    except Exception as e:
        abort(500, description=str(e))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    log_manager.rotate_logs()
    app.run(host=SERVER_HOST, port=SERVER_PORT)
