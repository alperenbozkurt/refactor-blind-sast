import os
from flask import Flask, request, send_file, abort, render_template, Response
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_MEDIA_ROOT = '/var/media'
DEFAULT_ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}
DEFAULT_MAX_CONTENT_LENGTH = 100 * 1024 * 1024

MIME_TYPES = {
    'mp4': 'video/mp4',
    'avi': 'video/x-msvideo',
    'mov': 'video/quicktime',
    'mkv': 'video/x-matroska',
}
DEFAULT_MIME_TYPE = 'video/mp4'

STREAM_CHUNK_SIZE = 4096

MEDIA_ROOT_DIR_MODE = 0o750   # 488
SAMPLE_FILE_MODE = 0o640      # 416
SAMPLE_MEDIA_FILES = ['sample1.mp4', 'sample2.avi', 'sample3.mov']

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

ERROR_TEMPLATE = 'error.html'
BROWSE_TEMPLATE = 'browse.html'

# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config['MEDIA_ROOT'] = os.path.abspath(DEFAULT_MEDIA_ROOT)
app.config['ALLOWED_EXTENSIONS'] = set(DEFAULT_ALLOWED_EXTENSIONS)
app.config['MAX_CONTENT_LENGTH'] = DEFAULT_MAX_CONTENT_LENGTH


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def allowed_file(filename):
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in app.config['ALLOWED_EXTENSIONS']


def is_safe_path(base_path, requested_path):
    base_path = os.path.abspath(base_path)
    requested_path = os.path.abspath(requested_path)
    return requested_path.startswith(base_path + os.sep)


def _media_root():
    return app.config['MEDIA_ROOT']


def _media_path(filename):
    return os.path.join(_media_root(), filename)


def _list_media_files():
    root = _media_root()
    return [
        f for f in os.listdir(root)
        if allowed_file(f) and is_safe_path(root, os.path.join(root, f))
    ]


def _mimetype_for(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    return MIME_TYPES.get(ext, DEFAULT_MIME_TYPE)


def _parse_range_header(range_header, file_size):
    """Return (from_bytes, to_bytes, length) for a Range header value."""
    from_bytes, to_bytes = 0, None
    range_units = range_header.split('=')
    if len(range_units) == 2 and range_units[0] == 'bytes':
        range_bytes = range_units[1].split('-')
        from_bytes = int(range_bytes[0]) if range_bytes[0] else 0
        to_bytes = int(range_bytes[1]) if range_bytes[1] else file_size - 1
    length = to_bytes - from_bytes + 1
    return from_bytes, to_bytes, length


def _iter_file_range(path, start, length, chunk_size=STREAM_CHUNK_SIZE):
    with open(path, 'rb') as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            chunk = f.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def _build_range_response(full_path, range_header, file_size, mimetype):
    from_bytes, to_bytes, length = _parse_range_header(range_header, file_size)
    return Response(
        _iter_file_range(full_path, from_bytes, length),
        206,
        mimetype=mimetype,
        direct_passthrough=True,
        headers={
            'Content-Range': f'bytes {from_bytes}-{to_bytes}/{file_size}',
            'Accept-Ranges': 'bytes',
            'Content-Length': str(length),
        },
    )


def _validate_stream_path(media_path):
    """Validate the requested media path; return (safe_name, full_path)."""
    if not media_path or not isinstance(media_path, str):
        abort(400, 'Invalid media path')
    safe_path = secure_filename(media_path)
    full_path = _media_path(safe_path)
    if not is_safe_path(_media_root(), full_path):
        abort(403, 'Access denied')
    if not os.path.exists(full_path):
        abort(404, 'Media file not found')
    if not os.path.isfile(full_path):
        abort(400, 'Requested path is not a file')
    if not allowed_file(full_path):
        abort(403, 'File type not allowed')
    return safe_path, full_path


def _render_error(message, status):
    return (render_template(ERROR_TEMPLATE, error=message), status)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    media_files = []
    try:
        media_files = _list_media_files()
    except Exception as e:
        app.logger.error(f'Error listing media files: {e}')
    return render_template(BROWSE_TEMPLATE, media_files=media_files)


@app.route('/stream/<path:media_path>')
def stream_media(media_path):
    try:
        safe_path, full_path = _validate_stream_path(media_path)
        mimetype = _mimetype_for(safe_path)
        range_header = request.headers.get('Range', None)
        file_size = os.path.getsize(full_path)
        if range_header:
            try:
                return _build_range_response(full_path, range_header, file_size, mimetype)
            except Exception as e:
                app.logger.error(f'Range request error: {e}')
                abort(400, 'Invalid range request')
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
        file_path = _media_path(filename)
        if not is_safe_path(_media_root(), file_path):
            abort(403, 'Access denied')
        file.save(file_path)
        return 'File uploaded successfully'
    except Exception as e:
        app.logger.error(f'Upload error: {e}')
        abort(500, 'File upload failed')


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@app.errorhandler(400)
def bad_request(e):
    return _render_error('Invalid request', 400)


@app.errorhandler(403)
def forbidden(e):
    return _render_error('Access denied', 403)


@app.errorhandler(404)
def not_found(e):
    return _render_error('Resource not found', 404)


@app.errorhandler(500)
def server_error(e):
    return _render_error('Internal server error', 500)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
def _create_sample_media():
    for media in SAMPLE_MEDIA_FILES:
        path = _media_path(media)
        if not os.path.exists(path):
            try:
                with open(path, 'wb'):
                    pass
                os.chmod(path, SAMPLE_FILE_MODE)
            except Exception as e:
                app.logger.error(f'Error creating sample media {media}: {e}')


def _prepare_media_root():
    os.makedirs(_media_root(), mode=MEDIA_ROOT_DIR_MODE, exist_ok=True)
    _create_sample_media()


def main():
    _prepare_media_root()
    app.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
