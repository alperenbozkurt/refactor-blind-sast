import os
from datetime import datetime

from flask import Flask, request, send_file, abort, render_template_string, escape
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_LOG_DIR = '/var/log/app_logs'
MAX_LOG_SIZE_BYTES = 1024 * 1024
ALLOWED_LOG_EXTENSIONS = {'.log', '.txt'}

LOG_ENTRY_TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'
LOG_ROTATION_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
ROTATED_FILE_SUFFIX = '.bak'

DEFAULT_MAX_LINES = 1000

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000

# Error descriptions shared by the HTTP handlers.
ERR_MISSING_FILENAME_OR_MESSAGE = 'Missing filename or message'
ERR_INVALID_INPUT_TYPE = 'Invalid input type'
ERR_INVALID_LOG_FILENAME = 'Invalid log filename'
ERR_LOG_NOT_FOUND_OR_INACCESSIBLE = 'Log file not found or inaccessible'
ERR_ACCESS_DENIED = 'Access denied'
ERR_LOG_FILE_NOT_FOUND = 'Log file not found'
ERR_NOT_A_FILE = 'Requested path is not a file'
ERR_INTERNAL_SERVER_ERROR = 'Internal server error'


class Config:
    """Default Flask configuration for the log viewer application."""

    LOG_DIR = os.path.abspath(DEFAULT_LOG_DIR)
    MAX_LOG_SIZE = MAX_LOG_SIZE_BYTES
    ALLOWED_LOG_EXTENSIONS = ALLOWED_LOG_EXTENSIONS


def create_app():
    """Build and configure the Flask application instance."""
    app = Flask(__name__)
    app.config.from_object(Config)
    return app


app = create_app()

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

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _current_timestamp(format_string):
    """Return the current time formatted with ``format_string``."""
    return datetime.now().strftime(format_string)


def _log_file_path(filename):
    """Return the path of ``filename`` inside the configured log directory."""
    return os.path.join(app.config['LOG_DIR'], filename)


def _read_first_lines(file_path, max_lines):
    """Read at most ``max_lines`` lines from ``file_path`` and join them."""
    lines = []
    with open(file_path, 'r') as f:
        for (i, line) in enumerate(f):
            if i >= max_lines:
                break
            lines.append(line)
    return ''.join(lines)


def _parse_log_entry_payload():
    """Validate the JSON body of a log-writing request and return it."""
    data = request.get_json()
    if not data or 'filename' not in data or 'message' not in data:
        abort(400, description=ERR_MISSING_FILENAME_OR_MESSAGE)
    if not isinstance(data['filename'], str) or not isinstance(data['message'], str):
        abort(400, description=ERR_INVALID_INPUT_TYPE)
    return data


# ---------------------------------------------------------------------------
# Log management
# ---------------------------------------------------------------------------


class LogManager:

    def __init__(self):
        os.makedirs(app.config['LOG_DIR'], exist_ok=True)

    def is_safe_path(self, path):
        base_path = os.path.abspath(app.config['LOG_DIR'])
        requested_path = os.path.abspath(path)
        return requested_path.startswith(base_path + os.sep)

    def is_valid_log_filename(self, filename):
        if not filename:
            return False
        if not any(filename.endswith(ext) for ext in app.config['ALLOWED_LOG_EXTENSIONS']):
            return False
        if '../' in filename or '~' in filename:
            return False
        return True

    def rotate_logs(self):
        for log_file in os.listdir(app.config['LOG_DIR']):
            file_path = _log_file_path(log_file)
            if self._needs_rotation(file_path):
                self._rotate_file(file_path, log_file)

    def _needs_rotation(self, file_path):
        return (
            os.path.exists(file_path)
            and os.path.getsize(file_path) > app.config['MAX_LOG_SIZE']
        )

    def _rotate_file(self, file_path, log_file):
        timestamp = _current_timestamp(LOG_ROTATION_TIMESTAMP_FORMAT)
        new_name = f'{log_file}.{timestamp}{ROTATED_FILE_SUFFIX}'
        new_path = _log_file_path(new_name)
        if self.is_safe_path(new_path):
            os.rename(file_path, new_path)

    def get_log_file(self, filename, max_lines=DEFAULT_MAX_LINES):
        if not self.is_valid_log_filename(filename):
            return None
        file_path = _log_file_path(filename)
        if not self.is_safe_path(file_path):
            return None
        try:
            if not os.path.exists(file_path):
                return None
            if not os.path.isfile(file_path):
                return None
            return _read_first_lines(file_path, max_lines)
        except Exception:
            return None

    def write_log(self, filename, message):
        if not self.is_valid_log_filename(filename):
            return False
        file_path = _log_file_path(filename)
        if not self.is_safe_path(file_path):
            return False
        try:
            with open(file_path, 'a') as f:
                timestamp = _current_timestamp(LOG_ENTRY_TIMESTAMP_FORMAT)
                f.write(f'[{timestamp}] {message}\n')
            return True
        except Exception:
            return False


log_manager = LogManager()

# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------


@app.route('/log', methods=['POST'])
def write_log_entry():
    data = _parse_log_entry_payload()
    if log_manager.write_log(data['filename'], data['message']):
        return ({'status': 'success'}, 201)
    else:
        return ({'error': 'Failed to write log'}, 500)


@app.route('/log/<path:filename>')
def view_log_file(filename):
    if not log_manager.is_valid_log_filename(filename):
        abort(400, description=ERR_INVALID_LOG_FILENAME)
    log_content = log_manager.get_log_file(filename)
    if log_content is None:
        abort(404, description=ERR_LOG_NOT_FOUND_OR_INACCESSIBLE)
    return render_template_string(
        LOG_VIEW_TEMPLATE,
        filename=escape(filename),
        log_content=escape(log_content),
    )


@app.route('/log/download/<path:filename>')
def download_log_file(filename):
    if not log_manager.is_valid_log_filename(filename):
        abort(400, description=ERR_INVALID_LOG_FILENAME)
    file_path = _log_file_path(filename)
    if not log_manager.is_safe_path(file_path):
        abort(403, description=ERR_ACCESS_DENIED)
    if not os.path.exists(file_path):
        abort(404, description=ERR_LOG_FILE_NOT_FOUND)
    if not os.path.isfile(file_path):
        abort(400, description=ERR_NOT_A_FILE)
    try:
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        app.logger.error(f'Error downloading log file: {e}')
        abort(500, description=ERR_INTERNAL_SERVER_ERROR)


@app.route('/logs')
def list_log_files():
    try:
        logs = [
            f
            for f in os.listdir(app.config['LOG_DIR'])
            if os.path.isfile(_log_file_path(f))
            and log_manager.is_valid_log_filename(f)
        ]
        return {'logs': logs}
    except Exception as e:
        app.logger.error(f'Error listing log files: {e}')
        abort(500, description=ERR_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------------


def main():
    log_manager.rotate_logs()
    app.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
