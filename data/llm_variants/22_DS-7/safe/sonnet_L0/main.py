import os
from flask import Flask, request, send_file, abort, render_template_string, escape
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['LOG_DIR'] = os.path.abspath('/var/log/app_logs')
app.config['MAX_LOG_SIZE'] = 1024 * 1024
app.config['ALLOWED_LOG_EXTENSIONS'] = {'.log', '.txt'}

LOG_VIEW_TEMPLATE = '\n<!DOCTYPE html>\n<html>\n<head>\n    <title>Log Viewer - {{ filename }}</title>\n</head>\n<body>\n    <h1>Log File: {{ filename }}</h1>\n    <pre>{{ log_content }}</pre>\n</body>\n</html>\n'


def _log_dir():
    return app.config['LOG_DIR']


class LogManager:

    def __init__(self):
        os.makedirs(_log_dir(), exist_ok=True)

    def _build_path(self, filename):
        return os.path.join(_log_dir(), filename)

    def _resolve_safe_path(self, filename):
        """Return the full path for a valid, safe filename, otherwise None."""
        if not self.is_valid_log_filename(filename):
            return None
        file_path = self._build_path(filename)
        if not self.is_safe_path(file_path):
            return None
        return file_path

    def is_safe_path(self, path):
        base_path = os.path.abspath(_log_dir())
        requested_path = os.path.abspath(path)
        return requested_path.startswith(base_path + os.sep)

    def is_valid_log_filename(self, filename):
        if not filename:
            return False
        allowed = app.config['ALLOWED_LOG_EXTENSIONS']
        if not any(filename.endswith(ext) for ext in allowed):
            return False
        if '../' in filename or '~' in filename:
            return False
        return True

    def rotate_logs(self):
        for log_file in os.listdir(_log_dir()):
            file_path = self._build_path(log_file)
            if not (os.path.exists(file_path)
                    and os.path.getsize(file_path) > app.config['MAX_LOG_SIZE']):
                continue
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_path = self._build_path(f'{log_file}.{timestamp}.bak')
            if self.is_safe_path(new_path):
                os.rename(file_path, new_path)

    def get_log_file(self, filename, max_lines=1000):
        file_path = self._resolve_safe_path(filename)
        if file_path is None:
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
        file_path = self._resolve_safe_path(filename)
        if file_path is None:
            return False
        try:
            with open(file_path, 'a') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
        return ({'status': 'success'}, 201)
    return ({'error': 'Failed to write log'}, 500)


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
    file_path = os.path.join(_log_dir(), filename)
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
        log_dir = _log_dir()
        logs = [
            f for f in os.listdir(log_dir)
            if os.path.isfile(os.path.join(log_dir, f))
            and log_manager.is_valid_log_filename(f)
        ]
        return {'logs': logs}
    except Exception as e:
        app.logger.error(f'Error listing log files: {e}')
        abort(500, description='Internal server error')


if __name__ == '__main__':
    log_manager.rotate_logs()
    app.run(host='0.0.0.0', port=5000)
