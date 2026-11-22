import os
from flask import Flask, request, send_file, abort, render_template
from werkzeug.utils import secure_filename

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
DEFAULT_MEDIA_ROOT = '/var/media'
DEFAULT_ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}

STREAM_CHUNK_SIZE = 4096
STREAM_MIMETYPE = 'video/mp4'
HTTP_PARTIAL_CONTENT = 206
RANGE_UNIT_BYTES = 'bytes'

BROWSE_TEMPLATE = 'browse.html'
ERROR_TEMPLATE = 'error.html'

SAMPLE_MEDIA_FILES = ['sample1.mp4', 'sample2.avi', 'sample3.mov']

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #
app = Flask(__name__)
app.config['MEDIA_ROOT'] = DEFAULT_MEDIA_ROOT
app.config['ALLOWED_EXTENSIONS'] = set(DEFAULT_ALLOWED_EXTENSIONS)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def _media_root():
    return app.config['MEDIA_ROOT']


def _list_media_files():
    """Return allowed media files in the media root (empty list on any error)."""
    try:
        return [f for f in os.listdir(_media_root()) if allowed_file(f)]
    except Exception:
        return []


def _validate_media_path(full_path):
    """Abort with the appropriate HTTP error if the path cannot be streamed."""
    if not os.path.exists(full_path):
        abort(404, 'Media file not found')
    if not os.path.isfile(full_path):
        abort(400, 'Requested path is not a file')
    if not allowed_file(full_path):
        abort(403, 'File type not allowed')


def _parse_range_header(range_header, file_size):
    """Parse a Range header into (from_bytes, to_bytes).

    to_bytes may be None if the header's units are not 'bytes'.
    """
    from_bytes, to_bytes = 0, None
    range_units = range_header.split('=')
    if len(range_units) == 2 and range_units[0] == RANGE_UNIT_BYTES:
        range_bytes = range_units[1].split('-')
        from_bytes = int(range_bytes[0]) if range_bytes[0] else 0
        to_bytes = int(range_bytes[1]) if range_bytes[1] else file_size - 1
    return from_bytes, to_bytes


def _generate_file_range(path, start, length):
    """Yield chunks of a file starting at `start` for up to `length` bytes."""
    with open(path, 'rb') as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            chunk = f.read(min(STREAM_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def _build_partial_response(full_path, range_header, file_size):
    from_bytes, to_bytes = _parse_range_header(range_header, file_size)
    length = to_bytes - from_bytes + 1
    headers = {
        'Content-Range': f'bytes {from_bytes}-{to_bytes}/{file_size}',
        'Accept-Ranges': RANGE_UNIT_BYTES,
        'Content-Length': str(length),
    }
    return app.response_class(
        _generate_file_range(full_path, from_bytes, length),
        HTTP_PARTIAL_CONTENT,
        mimetype=STREAM_MIMETYPE,
        direct_passthrough=True,
        headers=headers,
    )


def _render_error(e, status_code):
    return (render_template(ERROR_TEMPLATE, error=str(e)), status_code)


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/')
def index():
    media_files = _list_media_files()
    return render_template(BROWSE_TEMPLATE, media_files=media_files)


@app.route('/stream/<path:media_path>')
def stream_media(media_path):
    try:
        full_path = os.path.join(_media_root(), media_path)
        _validate_media_path(full_path)
        range_header = request.headers.get('Range', None)
        file_size = os.path.getsize(full_path)
        if range_header:
            return _build_partial_response(full_path, range_header, file_size)
        return send_file(full_path, mimetype=STREAM_MIMETYPE)
    except Exception as e:
        abort(500, f'Streaming error: {str(e)}')


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        abort(400, 'No file part')
    file = request.files['file']
    if file.filename == '':
        abort(400, 'No selected file')
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(_media_root(), filename))
        return 'File uploaded successfully'
    abort(400, 'File type not allowed')


# --------------------------------------------------------------------------- #
# Error handlers
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# CLI entry point
# --------------------------------------------------------------------------- #
def _ensure_sample_media():
    """Create the media root and empty placeholder sample files if missing."""
    os.makedirs(_media_root(), exist_ok=True)
    for media in SAMPLE_MEDIA_FILES:
        path = os.path.join(_media_root(), media)
        if not os.path.exists(path):
            open(path, 'wb').close()


if __name__ == '__main__':
    _ensure_sample_media()
    app.run(host=SERVER_HOST, port=SERVER_PORT, threaded=True)
