import os

from flask import Flask, abort, render_template, request, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MEDIA_ROOT'] = '/var/media'
app.config['ALLOWED_EXTENSIONS'] = {'mp4', 'avi', 'mov', 'mkv'}

CHUNK_SIZE = 4096
VIDEO_MIMETYPE = 'video/mp4'


def allowed_file(filename):
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']
    )


@app.route('/')
def index():
    try:
        media_files = [
            filename
            for filename in os.listdir(app.config['MEDIA_ROOT'])
            if allowed_file(filename)
        ]
    except Exception:
        media_files = []
    return render_template('browse.html', media_files=media_files)


def _parse_byte_range(range_header, file_size):
    """Parse a Range header value into a (from_bytes, to_bytes) pair."""
    from_bytes, to_bytes = 0, None
    range_units = range_header.split('=')
    if len(range_units) == 2 and range_units[0] == 'bytes':
        range_bytes = range_units[1].split('-')
        from_bytes = int(range_bytes[0]) if range_bytes[0] else 0
        to_bytes = int(range_bytes[1]) if range_bytes[1] else file_size - 1
    return from_bytes, to_bytes


def _iter_file_chunks(full_path, from_bytes, length):
    """Yield up to ``length`` bytes of ``full_path`` starting at ``from_bytes``."""
    with open(full_path, 'rb') as f:
        f.seek(from_bytes)
        remaining = length
        while remaining > 0:
            chunk = f.read(min(CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def _build_range_response(full_path, range_header, file_size):
    """Build the 206 partial-content response for a Range request."""
    from_bytes, to_bytes = _parse_byte_range(range_header, file_size)
    length = to_bytes - from_bytes + 1
    return app.response_class(
        _iter_file_chunks(full_path, from_bytes, length),
        206,
        mimetype=VIDEO_MIMETYPE,
        direct_passthrough=True,
        headers={
            'Content-Range': f'bytes {from_bytes}-{to_bytes}/{file_size}',
            'Accept-Ranges': 'bytes',
            'Content-Length': str(length),
        },
    )


@app.route('/stream/<path:media_path>')
def stream_media(media_path):
    try:
        full_path = os.path.join(app.config['MEDIA_ROOT'], media_path)
        if not os.path.exists(full_path):
            abort(404, 'Media file not found')
        if not os.path.isfile(full_path):
            abort(400, 'Requested path is not a file')
        if not allowed_file(full_path):
            abort(403, 'File type not allowed')

        range_header = request.headers.get('Range', None)
        file_size = os.path.getsize(full_path)
        if range_header:
            return _build_range_response(full_path, range_header, file_size)
        return send_file(full_path, mimetype=VIDEO_MIMETYPE)
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
        return 'File uploaded successfully'
    abort(400, 'File type not allowed')


def _render_error(error, status_code):
    return render_template('error.html', error=str(error)), status_code


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


def _ensure_sample_media():
    os.makedirs(app.config['MEDIA_ROOT'], exist_ok=True)
    sample_media = ['sample1.mp4', 'sample2.avi', 'sample3.mov']
    for media in sample_media:
        path = os.path.join(app.config['MEDIA_ROOT'], media)
        if not os.path.exists(path):
            open(path, 'wb').close()


if __name__ == '__main__':
    _ensure_sample_media()
    app.run(host='0.0.0.0', port=8000, threaded=True)
