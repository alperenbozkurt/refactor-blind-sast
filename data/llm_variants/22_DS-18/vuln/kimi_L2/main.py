"""Media browsing and streaming server.

A small Flask application that lists media files stored under a media
root, streams them (with HTTP Range support) and accepts uploads.
"""

import os

from flask import Flask, abort, render_template, request, send_file
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_MEDIA_ROOT = '/var/media'
DEFAULT_ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}

STREAM_CHUNK_SIZE = 4096
STREAM_MIMETYPE = 'video/mp4'

SAMPLE_MEDIA_FILES = ('sample1.mp4', 'sample2.avi', 'sample3.mov')

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

UPLOAD_SUCCESS_MESSAGE = 'File uploaded successfully'


class MediaServerConfig:
    """Flask configuration for the media server."""

    MEDIA_ROOT = DEFAULT_MEDIA_ROOT
    ALLOWED_EXTENSIONS = DEFAULT_ALLOWED_EXTENSIONS


app = Flask(__name__)
app.config.from_object(MediaServerConfig)


# ---------------------------------------------------------------------------
# Media helpers
# ---------------------------------------------------------------------------

def _extension(filename):
    """Return the lowercased extension of a filename containing a dot."""
    return filename.rsplit('.', 1)[1].lower()


def allowed_file(filename):
    return '.' in filename and _extension(filename) in app.config['ALLOWED_EXTENSIONS']


def _list_media_files():
    """Return the allowed media files in the media root, or [] on any error."""
    try:
        return [f for f in os.listdir(app.config['MEDIA_ROOT']) if allowed_file(f)]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Streaming helpers
# ---------------------------------------------------------------------------

def _validate_stream_target(full_path):
    """Abort with the appropriate error if *full_path* cannot be streamed."""
    if not os.path.exists(full_path):
        abort(404, 'Media file not found')
    if not os.path.isfile(full_path):
        abort(400, 'Requested path is not a file')
    if not allowed_file(full_path):
        abort(403, 'File type not allowed')


def _parse_range_header(range_header, file_size):
    """Parse an HTTP Range header into a ``(from_bytes, to_bytes)`` tuple."""
    from_bytes, to_bytes = 0, None
    range_units = range_header.split('=')
    if len(range_units) == 2 and range_units[0] == 'bytes':
        range_bytes = range_units[1].split('-')
        from_bytes = int(range_bytes[0]) if range_bytes[0] else 0
        to_bytes = int(range_bytes[1]) if range_bytes[1] else file_size - 1
    return from_bytes, to_bytes


def _iter_file_range(full_path, from_bytes, length):
    """Yield *length* bytes of *full_path* starting at *from_bytes*."""
    with open(full_path, 'rb') as f:
        f.seek(from_bytes)
        remaining = length
        while remaining > 0:
            chunk = f.read(min(STREAM_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def _build_range_response(full_path, from_bytes, to_bytes, file_size):
    """Build the ``206 Partial Content`` response for the requested range."""
    length = to_bytes - from_bytes + 1
    headers = {
        'Content-Range': f'bytes {from_bytes}-{to_bytes}/{file_size}',
        'Accept-Ranges': 'bytes',
        'Content-Length': str(length),
    }
    return app.response_class(
        _iter_file_range(full_path, from_bytes, length),
        206,
        mimetype=STREAM_MIMETYPE,
        direct_passthrough=True,
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    media_files = _list_media_files()
    return render_template('browse.html', media_files=media_files)


@app.route('/stream/<path:media_path>')
def stream_media(media_path):
    try:
        full_path = os.path.join(app.config['MEDIA_ROOT'], media_path)
        _validate_stream_target(full_path)
        range_header = request.headers.get('Range', None)
        file_size = os.path.getsize(full_path)
        if range_header:
            from_bytes, to_bytes = _parse_range_header(range_header, file_size)
            return _build_range_response(full_path, from_bytes, to_bytes, file_size)
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
        file.save(os.path.join(app.config['MEDIA_ROOT'], filename))
        return UPLOAD_SUCCESS_MESSAGE
    abort(400, 'File type not allowed')


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

def _render_error_page(e, status_code):
    """Render the shared error template for *status_code*."""
    return render_template('error.html', error=str(e)), status_code


@app.errorhandler(400)
def bad_request(e):
    return _render_error_page(e, 400)


@app.errorhandler(403)
def forbidden(e):
    return _render_error_page(e, 403)


@app.errorhandler(404)
def not_found(e):
    return _render_error_page(e, 404)


@app.errorhandler(500)
def server_error(e):
    return _render_error_page(e, 500)


# ---------------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------------

def _ensure_media_root():
    """Create the media root directory if it does not exist yet."""
    os.makedirs(app.config['MEDIA_ROOT'], exist_ok=True)


def _create_sample_media_files():
    """Create empty sample media files so the server has demo content."""
    for media in SAMPLE_MEDIA_FILES:
        path = os.path.join(app.config['MEDIA_ROOT'], media)
        if not os.path.exists(path):
            open(path, 'wb').close()


def main():
    """Prepare the media root with sample files and run the server."""
    _ensure_media_root()
    _create_sample_media_files()
    app.run(host=SERVER_HOST, port=SERVER_PORT, threaded=True)


if __name__ == '__main__':
    main()
