import os
from itertools import islice

from flask import Flask, request, send_file, abort, render_template_string, escape
from datetime import datetime
from werkzeug.utils import secure_filename


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
DEFAULT_LOG_DIR = '/var/log/app_logs'
DEFAULT_MAX_LOG_SIZE = 1024 * 1024
DEFAULT_ALLOWED_LOG_EXTENSIONS = {'.log', '.txt'}
DEFAULT_MAX_LINES = 1000

ROTATION_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
ENTRY_TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'
BACKUP_SUFFIX = 'bak'

FORBIDDEN_FILENAME_SEQUENCES = ('../', '~')

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000

LOG_VIEW_TEMPLATE = '\n<!DOCTYPE html>\n<html>\n<head>\n    <title>Log Viewer - {{ filename }}</title>\n</head>\n<body>\n    <h1>Log File: {{ filename }}</h1>\n    <pre>{{ log_content }}</pre>\n</body>\n</html>\n'


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
class DefaultConfig:
    """Default application configuration (uppercase attributes are loaded)."""

    LOG_DIR = os.path.abspath(DEFAULT_LOG_DIR)
    MAX_LOG_SIZE = DEFAULT_MAX_LOG_SIZE
    ALLOWED_LOG_EXTENSIONS = DEFAULT_ALLOWED_LOG_EXTENSIONS


app = Flask(__name__)
app.config.from_object(DefaultConfig)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _log_dir():
    return app.config['LOG_DIR']


def _log_path(filename):
    """Join a filename onto the configured log directory."""
    return os.path.join(_log_dir(), filename)


def _now_str(fmt):
    return datetime.now().strftime(fmt)


def _has_allowed_extension(filename):
    return any((filename.endswith(ext) for ext in app.config['ALLOWED_LOG_EXTENSIONS']))


def _contains_forbidden_sequence(filename):
    return any(seq in filename for seq in FORBIDDEN_FILENAME_SEQUENCES)


def _read_lines(file_path, max_lines):
    with open(file_path, 'r') as f:
        return ''.join(islice(f, max_lines)) if max_lines > 0 else ''


def _format_entry(message):
    return f'[{_now_str(ENTRY_TIMESTAMP_FORMAT)}] {message}\n'


# --------------------------------------------------------------------------- #
# Log management
# --------------------------------------------------------------------------- #
class LogManager:

    def __init__(self):
        os.makedirs(_log_dir(), exist_ok=True)

    def is_safe_path(self, path):
        base_path = os.path.abspath(_log_dir())
        requested_path = os.path.abspath(path)
        return requested_path.startswith(base_path + os.sep)

    def is_valid_log_filename(self, filename):
        if not filename:
            return False
        if not _has_allowed_extension(filename):
            return False
        if _contains_forbidden_sequence(filename):
            return False
        return True

    def _needs_rotation(self, file_path):
        return os.path.exists(file_path) and os.path.getsize(file_path) > app.config['MAX_LOG_SIZE']

    def _rotated_name(self, log_file):
        timestamp = _now_str(ROTATION_TIMESTAMP_FORMAT)
        return f'{log_file}.{timestamp}.{BACKUP_SUFFIX}'

    def rotate_logs(self):
        for log_file in os.listdir(_log_dir()):
            file_path = _log_path(log_file)
            if self._needs_rotation(file_path):
                new_path = _log_path(self._rotated_name(log_file))
                if self.is_safe_path(new_path):
                    os.rename(file_path, new_path)

    def get_log_file(self, filename, max_lines=DEFAULT_MAX_LINES):
        if not self.is_valid_log_filename(filename):
            return None
        file_path = _log_path(filename)
        if not self.is_safe_path(file_path):
            return None
        try:
            if not os.path.exists(file_path):
                return None
            if not os.path.isfile(file_path):
                return None
            return _read_lines(file_path, max_lines)
        except Exception:
            return None

    def write_log(self, filename, message):
        if not self.is_valid_log_filename(filename):
            return False
        file_path = _log_path(filename)
        if not self.is_safe_path(file_path):
            return False
        try:
            with open(file_path, 'a') as f:
                f.write(_format_entry(message))
            return True
        except Exception:
            return False


log_manager = LogManager()


# --------------------------------------------------------------------------- #
# Request validation
# --------------------------------------------------------------------------- #
def _require_valid_filename(filename):
    if not log_manager.is_valid_log_filename(filename):
        abort(400, description='Invalid log filename')


def _parse_write_payload():
    data = request.get_json()
    if not data or 'filename' not in data or 'message' not in data:
        abort(400, description='Missing filename or message')
    if not isinstance(data['filename'], str) or not isinstance(data['message'], str):
        abort(400, description='Invalid input type')
    return data['filename'], data['message']


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/log', methods=['POST'])
def write_log_entry():
    filename, message = _parse_write_payload()
    if log_manager.write_log(filename, message):
        return ({'status': 'success'}, 201)
    else:
        return ({'error': 'Failed to write log'}, 500)


@app.route('/log/<path:filename>')
def view_log_file(filename):
    _require_valid_filename(filename)
    log_content = log_manager.get_log_file(filename)
    if log_content is None:
        abort(404, description='Log file not found or inaccessible')
    return render_template_string(LOG_VIEW_TEMPLATE, filename=escape(filename), log_content=escape(log_content))


@app.route('/log/download/<path:filename>')
def download_log_file(filename):
    _require_valid_filename(filename)
    file_path = _log_path(filename)
    if not log_manager.is_safe_path(file_path):
        abort(403, description='Access denied')
    if not os.path.exists(file_path):
        abort(404, description='Log file not found')
    if not os.path.isfile(file_path):
        abort(400, description='Requested path is not a file')
    try:
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        app.logger.error(f'Error downloading log file: {e}')
        abort(500, description='Internal server error')


def _list_valid_log_files():
    return [
        f for f in os.listdir(_log_dir())
        if os.path.isfile(_log_path(f)) and log_manager.is_valid_log_filename(f)
    ]


@app.route('/logs')
def list_log_files():
    try:
        logs = _list_valid_log_files()
        return {'logs': logs}
    except Exception as e:
        app.logger.error(f'Error listing log files: {e}')
        abort(500, description='Internal server error')


if __name__ == '__main__':
    log_manager.rotate_logs()
    app.run(host=SERVER_HOST, port=SERVER_PORT)
