import os

from flask import Flask, request, render_template, abort, send_file, Response

app = Flask(__name__)
app.config['LOG_DIR'] = '/var/log'
app.config['MAX_LOG_SIZE'] = 1024 * 1024

LOG_EXTENSION = '.log'
SAMPLE_LOGS = ['system.log', 'application.log', 'security.log']


def is_safe_log_path(path):
    return path.endswith(LOG_EXTENSION)


def _list_log_files():
    """Return the log files in the log directory, or an empty list on any error."""
    try:
        return [
            name for name in os.listdir(app.config['LOG_DIR'])
            if name.endswith(LOG_EXTENSION)
        ]
    except Exception:
        return []


def _get_requested_log_file():
    """Return the 'file' query parameter, aborting with 400 if it is missing."""
    log_file = request.args.get('file')
    if not log_file:
        abort(400, 'No log file specified')
    return log_file


def _resolve_log_path(log_file):
    """Build the log path and validate its existence and type (aborts on failure)."""
    log_path = os.path.join(app.config['LOG_DIR'], log_file)
    if not os.path.exists(log_path):
        abort(404, 'Log file not found')
    if not is_safe_log_path(log_path):
        abort(403, 'Invalid log file type')
    return log_path


def _render_error(e, status_code):
    return (render_template('error.html', error=str(e)), status_code)


@app.route('/')
def index():
    return render_template('logs.html', log_files=_list_log_files())


@app.route('/view')
def view_log():
    log_file = _get_requested_log_file()
    try:
        log_path = _resolve_log_path(log_file)
        if os.path.getsize(log_path) > app.config['MAX_LOG_SIZE']:
            return Response('Log file too large', mimetype='text/plain')
        with open(log_path, 'r') as f:
            content = f.read()
        return render_template('view_log.html', log_name=log_file, log_content=content)
    except Exception as e:
        abort(500, f'Error reading log: {str(e)}')


@app.route('/download')
def download_log():
    log_file = _get_requested_log_file()
    try:
        log_path = _resolve_log_path(log_file)
        return send_file(log_path, as_attachment=True)
    except Exception as e:
        abort(500, f'Error downloading log: {str(e)}')


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


def _create_sample_logs():
    """Create the log directory and any missing sample log files."""
    os.makedirs(app.config['LOG_DIR'], exist_ok=True)
    for log in SAMPLE_LOGS:
        log_path = os.path.join(app.config['LOG_DIR'], log)
        if not os.path.exists(log_path):
            with open(log_path, 'w') as f:
                f.write(f'Sample log entries for {log}\n' + 'Log line\n' * 20)


if __name__ == '__main__':
    _create_sample_logs()
    app.run(host='0.0.0.0', port=8000)
