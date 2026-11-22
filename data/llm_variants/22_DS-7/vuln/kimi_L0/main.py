import os
from datetime import datetime

from flask import Flask, abort, render_template_string, request, send_file

app = Flask(__name__)
app.config['LOG_DIR'] = '/var/log/app_logs'
app.config['MAX_LOG_SIZE'] = 1024 * 1024

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


def _log_path(filename):
    """Return the full path of *filename* inside the configured log directory."""
    return os.path.join(app.config['LOG_DIR'], filename)


class LogManager:
    """Create, read, write and rotate log files in the configured directory."""

    WRITE_TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'
    ROTATE_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

    def __init__(self):
        os.makedirs(app.config['LOG_DIR'], exist_ok=True)

    def rotate_logs(self):
        for log_file in os.listdir(app.config['LOG_DIR']):
            file_path = _log_path(log_file)
            if os.path.getsize(file_path) > app.config['MAX_LOG_SIZE']:
                timestamp = datetime.now().strftime(self.ROTATE_TIMESTAMP_FORMAT)
                backup_path = _log_path(f'{log_file}.{timestamp}.bak')
                os.rename(file_path, backup_path)

    def get_log_file(self, filename, max_lines=1000):
        file_path = _log_path(filename)
        try:
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
        try:
            with open(_log_path(filename), 'a') as f:
                timestamp = datetime.now().strftime(self.WRITE_TIMESTAMP_FORMAT)
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
    if log_manager.write_log(data['filename'], data['message']):
        return {'status': 'success'}, 201
    return {'error': 'Failed to write log'}, 500


@app.route('/log/<path:filename>')
def view_log_file(filename):
    log_content = log_manager.get_log_file(filename)
    if log_content is None:
        abort(404, description='Log file not found or inaccessible')
    return render_template_string(
        LOG_VIEW_TEMPLATE, filename=filename, log_content=log_content
    )


@app.route('/log/download/<path:filename>')
def download_log_file(filename):
    file_path = _log_path(filename)
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
        logs = [
            f for f in os.listdir(app.config['LOG_DIR'])
            if os.path.isfile(_log_path(f))
        ]
        return {'logs': logs}
    except Exception as e:
        abort(500, description=str(e))


if __name__ == '__main__':
    log_manager.rotate_logs()
    app.run(host='0.0.0.0', port=5000)
