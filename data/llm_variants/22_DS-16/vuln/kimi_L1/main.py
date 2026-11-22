"""Minimal log viewer web application.

Exposes routes to list the ``.log`` files stored in a log directory,
view their contents in the browser, and download them as attachments.
"""

import os

from flask import Flask, Response, abort, render_template, request, send_file

app = Flask(__name__)
app.config['LOG_DIR'] = '/var/log'
app.config['MAX_LOG_SIZE'] = 1024 * 1024


def is_safe_log_path(path):
    """Return ``True`` when *path* refers to a ``.log`` file."""
    return path.endswith('.log')


@app.route('/')
def index():
    """Show the list of available log files."""
    try:
        log_files = [
            name
            for name in os.listdir(app.config['LOG_DIR'])
            if name.endswith('.log')
        ]
    except Exception:
        log_files = []
    return render_template('logs.html', log_files=log_files)


@app.route('/view')
def view_log():
    """Render the contents of the requested log file."""
    log_file = request.args.get('file')
    if not log_file:
        abort(400, 'No log file specified')

    try:
        log_path = os.path.join(app.config['LOG_DIR'], log_file)
        if not os.path.exists(log_path):
            abort(404, 'Log file not found')
        if not is_safe_log_path(log_path):
            abort(403, 'Invalid log file type')

        file_size = os.path.getsize(log_path)
        if file_size > app.config['MAX_LOG_SIZE']:
            return Response('Log file too large', mimetype='text/plain')

        with open(log_path, 'r') as f:
            content = f.read()
        return render_template('view_log.html', log_name=log_file, log_content=content)
    except Exception as e:
        abort(500, f'Error reading log: {str(e)}')


@app.route('/download')
def download_log():
    """Send the requested log file to the client as an attachment."""
    log_file = request.args.get('file')
    if not log_file:
        abort(400, 'No log file specified')

    try:
        log_path = os.path.join(app.config['LOG_DIR'], log_file)
        if not os.path.exists(log_path):
            abort(404, 'Log file not found')
        if not is_safe_log_path(log_path):
            abort(403, 'Invalid log file type')

        return send_file(log_path, as_attachment=True)
    except Exception as e:
        abort(500, f'Error downloading log: {str(e)}')


@app.errorhandler(400)
def bad_request(e):
    """Render the error page for bad requests."""
    return (render_template('error.html', error=str(e)), 400)


@app.errorhandler(403)
def forbidden(e):
    """Render the error page for forbidden requests."""
    return (render_template('error.html', error=str(e)), 403)


@app.errorhandler(404)
def not_found(e):
    """Render the error page for missing resources."""
    return (render_template('error.html', error=str(e)), 404)


@app.errorhandler(500)
def server_error(e):
    """Render the error page for internal server errors."""
    return (render_template('error.html', error=str(e)), 500)


if __name__ == '__main__':
    # Ensure the log directory exists and seed it with sample logs so
    # the application has something to display on a first run.
    os.makedirs(app.config['LOG_DIR'], exist_ok=True)
    sample_logs = ['system.log', 'application.log', 'security.log']
    for log in sample_logs:
        log_path = os.path.join(app.config['LOG_DIR'], log)
        if not os.path.exists(log_path):
            with open(log_path, 'w') as f:
                f.write(f'Sample log entries for {log}\n' + 'Log line\n' * 20)
    app.run(host='0.0.0.0', port=8000)
