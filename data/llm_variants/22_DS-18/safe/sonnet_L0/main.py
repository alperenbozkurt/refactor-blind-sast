import os
from flask import Flask, request, send_file, abort, render_template, Response
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MEDIA_ROOT'] = os.path.abspath('/var/media')
app.config['ALLOWED_EXTENSIONS'] = {'mp4', 'avi', 'mov', 'mkv'}
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

MIME_TYPES = {
    'mp4': 'video/mp4',
    'avi': 'video/x-msvideo',
    'mov': 'video/quicktime',
    'mkv': 'video/x-matroska',
}
DEFAULT_MIME_TYPE = 'video/mp4'
CHUNK_SIZE = 4096
SAMPLE_MEDIA = ['sample1.mp4', 'sample2.avi', 'sample3.mov']


def allowed_file(filename):
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in app.config['ALLOWED_EXTENSIONS']


def is_safe_path(base_path, requested_path):
    base_path = os.path.abspath(base_path)
    requested_path = os.path.abspath(requested_path)
    return requested_path.startswith(base_path + os.sep)


def _parse_range(range_header, file_size):
    """Return (from_bytes, to_bytes); to_bytes may be None for malformed units."""
    from_bytes, to_bytes = 0, None
    range_units = range_header.split('=')
    if len(range_units) == 2 and range_units[0] == 'bytes':
        range_bytes = range_units[1].split('-')
        from_bytes = int(range_bytes[0]) if range_bytes[0] else 0
        to_bytes = int(range_bytes[1]) if range_bytes[1] else file_size - 1
    return from_bytes, to_bytes


def _iter_file(path, start, length):
    with open(path, 'rb') as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            chunk = f.read(min(CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def _range_response(full_path, range_header, file_size, mimetype):
    try:
        from_bytes, to_bytes = _parse_range(range_header, file_size)
        length = to_bytes - from_bytes + 1
        return Response(
            _iter_file(full_path, from_bytes, length),
            206,
            mimetype=mimetype,
            direct_passthrough=True,
            headers={
                'Content-Range': f'bytes {from_bytes}-{to_bytes}/{file_size}',
                'Accept-Ranges': 'bytes',
                'Content-Length': str(length),
            },
        )
    except Exception as e:
        app.logger.error(f'Range request error: {e}')
        abort(400, 'Invalid range request')


@app.route('/')
def index():
    media_files = []
    try:
        media_root = app.config['MEDIA_ROOT']
        media_files = [
            f for f in os.listdir(media_root)
            if allowed_file(f) and is_safe_path(media_root, os.path.join(media_root, f))
        ]
    except Exception as e:
        app.logger.error(f'Error listing media files: {e}')
    return render_template('browse.html', media_files=media_files)


@app.route('/stream/<path:media_path>')
def stream_media(media_path):
    try:
        if not media_path or not isinstance(media_path, str):
            abort(400, 'Invalid media path')
        safe_path = secure_filename(media_path)
        full_path = os.path.join(app.config['MEDIA_ROOT'], safe_path)
        if not is_safe_path(app.config['MEDIA_ROOT'], full_path):
            abort(403, 'Access denied')
        if not os.path.exists(full_path):
            abort(404, 'Media file not found')
        if not os.path.isfile(full_path):
            abort(400, 'Requested path is not a file')
        if not allowed_file(full_path):
            abort(403, 'File type not allowed')
        extension = safe_path.rsplit('.', 1)[1].lower()
        mimetype = MIME_TYPES.get(extension, DEFAULT_MIME_TYPE)
        range_header = request.headers.get('Range', None)
        file_size = os.path.getsize(full_path)
        if range_header:
            return _range_response(full_path, range_header, file_size, mimetype)
        return send_file(full_path, mimetype=mimetype)
    except Exception as e:
        app.logger.error(f'Streaming error: {e}')
        abort(500, 'Internal server error')


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        abort(400, 'Invalid request')
    file = request.files['file']
    if file.filename == '':
        abort(400, 'No file selected')
    if not allowed_file(file.filename):
        abort(400, 'File type not allowed')
    try:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['MEDIA_ROOT'], filename)
        if not is_safe_path(app.config['MEDIA_ROOT'], file_path):
            abort(403, 'Access denied')
        file.save(file_path)
        return 'File uploaded successfully'
    except Exception as e:
        app.logger.error(f'Upload error: {e}')
        abort(500, 'File upload failed')


def _error_page(message, status):
    return (render_template('error.html', error=message), status)


@app.errorhandler(400)
def bad_request(e):
    return _error_page('Invalid request', 400)


@app.errorhandler(403)
def forbidden(e):
    return _error_page('Access denied', 403)


@app.errorhandler(404)
def not_found(e):
    return _error_page('Resource not found', 404)


@app.errorhandler(500)
def server_error(e):
    return _error_page('Internal server error', 500)


def _create_sample_media():
    for media in SAMPLE_MEDIA:
        path = os.path.join(app.config['MEDIA_ROOT'], media)
        if not os.path.exists(path):
            try:
                with open(path, 'wb'):
                    pass
                os.chmod(path, 0o640)
            except Exception as e:
                app.logger.error(f'Error creating sample media {media}: {e}')


if __name__ == '__main__':
    os.makedirs(app.config['MEDIA_ROOT'], mode=0o750, exist_ok=True)
    _create_sample_media()
    app.run(host='0.0.0.0', port=8000)
