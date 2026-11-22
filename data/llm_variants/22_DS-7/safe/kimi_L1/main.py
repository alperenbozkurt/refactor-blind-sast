"""Flask application for viewing, writing, downloading, and listing log files."""

import os
from datetime import datetime

from flask import Flask, abort, escape, render_template_string, request, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['LOG_DIR'] = os.path.abspath('/var/log/app_logs')
app.config['MAX_LOG_SIZE'] = 1024 * 1024
app.config['ALLOWED_LOG_EXTENSIONS'] = {'.log', '.txt'}

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


class LogManager:
    """Handle validation, rotation, reading, and writing of log files."""

    def __init__(self):
        os.makedirs(app.config['LOG_DIR'], exist_ok=True)

    def is_safe_path(self, path):
        """Return True if `path` resolves inside the configured log directory."""
        base_path = os.path.abspath(app.config['LOG_DIR'])
        requested_path = os.path.abspath(path)
        return requested_path.startswith(base_path + os.sep)

    def is_valid_log_filename(self, filename):
        """Return True if `filename` is a non-empty, allowed log file name."""
        if not filename:
            return False
        if not any(filename.endswith(ext) for ext in app.config['ALLOWED_LOG_EXTENSIONS']):
            return False
        if '../' in filename or '~' in filename:
            return False
        return True

    def rotate_logs(self):
        """Rename any log file exceeding the configured maximum size."""
        for log_file in os.listdir(app.config['LOG_DIR']):
            file_path = os.path.join(app.config['LOG_DIR'], log_file)
            if not os.path.exists(file_path):
                continue
            if os.path.getsize(file_path) <= app.config['MAX_LOG_SIZE']:
                continue
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_name = f'{log_file}.{timestamp}.bak'
            new_path = os.path.join(app.config['LOG_DIR'], new_name)
            if self.is_safe_path(new_path):
                os.rename(file_path, new_path)

    def get_log_file(self, filename, max_lines=1000):
        """Return up to `max_lines` lines from `filename`, or None on failure."""
        if not self.is_valid_log_filename(filename):
            return None

        file_path = os.path.join(app.config['LOG_DIR'], filename)
        if not self.is_safe_path(file_path):
            return None

        try:
            if not os.path.exists(file_path):
                return None
            if not os.path.isfile(file_path):
                return None
            with open(file_path, 'r') as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line)
            return ''.join(lines)
        except Exception:
            return None

    def write_log(self, filename, message):
        """Append a timestamped `message` to `filename`. Return success flag."""
        if not self.is_valid_log_filename(filename):
            return False

        file_path = os.path.join(app.config['LOG_DIR'], filename)
        if not self.is_safe_path(file_path):
            return False

        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(file_path, 'a') as f:
                f.write(f'[{timestamp}] {message}\n')
            return True
        except Exception:
            return False


log_manager = LogManager()


@app.route('/log', methods=['POST'])
def write_log_entry():
    data = request.get_json()
    if not data or 'filename' not in data or 'message' not in data:
        abort(400, description='Missing filename or message')
    if not isinstance(data['filename'], str) or not isinstance(data['message'], str):
        abort(400, description='Invalid input type')
    if log_manager.write_log(data['filename'], data['message']):
        return {'status': 'success'}, 201
    return {'error': 'Failed to write log'}, 500


@app.route('/log/<path:filename>')
def view_log_file(filename):
    if not log_manager.is_valid_log_filename(filename):
        abort(400, description='Invalid log filename')
    log_content = log_manager.get_log_file(filename)
    if log_content is None:
        abort(404, description='Log file not found or inaccessible')
    return render_template_string(
        LOG_VIEW_TEMPLATE,
        filename=escape(filename),
        log_content=escape(log_content),
    )


@app.route('/log/download/<path:filename>')
def download_log_file(filename):
    if not log_manager.is_valid_log_filename(filename):
        abort(400, description='Invalid log filename')

    file_path = os.path.join(app.config['LOG_DIR'], filename)
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


@app.route('/logs')
def list_log_files():
    try:
        logs = [
            f
            for f in os.listdir(app.config['LOG_DIR'])
            if os.path.isfile(os.path.join(app.config['LOG_DIR'], f))
            and log_manager.is_valid_log_filename(f)
        ]
        return {'logs': logs}
    except Exception as e:
        app.logger.error(f'Error listing log files: {e}')
        abort(500, description='Internal server error')


if __name__ == '__main__':
    log_manager.rotate_logs()
    app.run(host='0.0.0.0', port=5000)
