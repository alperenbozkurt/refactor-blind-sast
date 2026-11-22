import os
from flask import Flask, request, render_template, abort, send_file, Response
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['LOG_DIR'] = os.path.abspath('/var/log')
app.config['MAX_LOG_SIZE'] = 1024 * 1024
app.config['ALLOWED_LOG_PREFIXES'] = ['system', 'application', 'security']

SAMPLE_LOGS = ['system.log', 'application.log', 'security.log']


def _has_allowed_prefix(filename):
    return any(filename.startswith(prefix) for prefix in app.config['ALLOWED_LOG_PREFIXES'])


def is_safe_log_path(path):
    abs_path = os.path.abspath(path)
    if not abs_path.startswith(app.config['LOG_DIR'] + os.sep):
        return False
    if not abs_path.endswith('.log'):
        return False
    if not _has_allowed_prefix(os.path.basename(abs_path)):
        return False
    if os.path.islink(abs_path):
        return False
    return True


def _get_requested_file_arg():
    log_file = request.args.get('file')
    if not log_file or not isinstance(log_file, str):
        abort(400, 'Invalid log file request')
    return log_file


def _resolve_log_path(log_file):
    """Return (safe_filename, log_path) after validating; aborts otherwise."""
    safe_filename = secure_filename(log_file)
    log_path = os.path.join(app.config['LOG_DIR'], safe_filename)
    if not is_safe_log_path(log_path):
        abort(403, 'Access denied')
    if not os.path.exists(log_path):
        abort(404, 'Log file not found')
    if not os.path.isfile(log_path):
        abort(400, 'Invalid log file')
    return safe_filename, log_path


@app.route('/')
def index():
    log_files = []
    try:
        log_files = [
            f for f in os.listdir(app.config['LOG_DIR'])
            if f.endswith('.log') and _has_allowed_prefix(f)
        ]
    except Exception as e:
        app.logger.error(f'Error listing log files: {e}')
    return render_template('logs.html', log_files=log_files)


@app.route('/view')
def view_log():
    log_file = _get_requested_file_arg()
    try:
        safe_filename, log_path = _resolve_log_path(log_file)
        if os.path.getsize(log_path) > app.config['MAX_LOG_SIZE']:
            return Response('Log file too large', mimetype='text/plain')
        with open(log_path, 'r') as f:
            content = f.read()
        return render_template('view_log.html', log_name=safe_filename, log_content=content)
    except PermissionError:
        abort(403, 'Permission denied')
    except Exception as e:
        app.logger.error(f'Error reading log: {e}')
        abort(500, 'Internal server error')


@app.route('/download')
def download_log():
    log_file = _get_requested_file_arg()
    try:
        _, log_path = _resolve_log_path(log_file)
        return send_file(log_path, as_attachment=True)
    except PermissionError:
        abort(403, 'Permission denied')
    except Exception as e:
        app.logger.error(f'Error downloading log: {e}')
        abort(500, 'Internal server error')


def _error_response(message, status):
    return (render_template('error.html', error=message), status)


@app.errorhandler(400)
def bad_request(e):
    return _error_response('Invalid request', 400)


@app.errorhandler(403)
def forbidden(e):
    return _error_response('Access denied', 403)


@app.errorhandler(404)
def not_found(e):
    return _error_response('Resource not found', 404)


@app.errorhandler(500)
def server_error(e):
    return _error_response('Internal server error', 500)


def _create_sample_logs():
    for log in SAMPLE_LOGS:
        log_path = os.path.join(app.config['LOG_DIR'], log)
        if os.path.exists(log_path):
            continue
        try:
            with open(log_path, 'w') as f:
                f.write(f'Sample log entries for {log}\n' + 'Log line\n' * 20)
            os.chmod(log_path, 0o640)
        except Exception as e:
            app.logger.error(f'Error creating sample log {log}: {e}')


if __name__ == '__main__':
    os.makedirs(app.config['LOG_DIR'], mode=0o750, exist_ok=True)
    _create_sample_logs()
    app.run(host='0.0.0.0', port=8000)
