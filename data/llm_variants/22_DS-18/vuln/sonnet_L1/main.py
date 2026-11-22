import os

from flask import Flask, request, send_file, abort, render_template
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MEDIA_ROOT'] = '/var/media'
app.config['ALLOWED_EXTENSIONS'] = {'mp4', 'avi', 'mov', 'mkv'}

CHUNK_SIZE = 4096
VIDEO_MIMETYPE = 'video/mp4'
SAMPLE_MEDIA = ['sample1.mp4', 'sample2.avi', 'sample3.mov']


def allowed_file(filename):
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']
    )


def _parse_range_header(range_header, file_size):
    """Return (from_bytes, to_bytes) for a Range header.

    If the header is not of the form "bytes=...", to_bytes is None.
    """
    from_bytes, to_bytes = 0, None
    range_units = range_header.split('=')
    if len(range_units) == 2 and range_units[0] == 'bytes':
        range_bytes = range_units[1].split('-')
        from_bytes = int(range_bytes[0]) if range_bytes[0] else 0
        to_bytes = int(range_bytes[1]) if range_bytes[1] else file_size - 1
    return from_bytes, to_bytes


def _read_range(path, start, length):
    """Yield the file content from `start` for `length` bytes in chunks."""
    with open(path, 'rb') as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            chunk = f.read(min(CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def _check_media_file(full_path):
    if not os.path.exists(full_path):
        abort(404, 'Media file not found')
    if not os.path.isfile(full_path):
        abort(400, 'Requested path is not a file')
    if not allowed_file(full_path):
        abort(403, 'File type not allowed')


def _partial_response(full_path, range_header, file_size):
    from_bytes, to_bytes = _parse_range_header(range_header, file_size)
    length = to_bytes - from_bytes + 1
    headers = {
        'Content-Range': f'bytes {from_bytes}-{to_bytes}/{file_size}',
        'Accept-Ranges': 'bytes',
        'Content-Length': str(length),
    }
    return app.response_class(
        _read_range(full_path, from_bytes, length),
        206,
        mimetype=VIDEO_MIMETYPE,
        direct_passthrough=True,
        headers=headers,
    )


@app.route('/')
def index():
    media_files = []
    try:
        media_files = [
            f for f in os.listdir(app.config['MEDIA_ROOT']) if allowed_file(f)
        ]
    except Exception:
        pass
    return render_template('browse.html', media_files=media_files)


@app.route('/stream/<path:media_path>')
def stream_media(media_path):
    try:
        full_path = os.path.join(app.config['MEDIA_ROOT'], media_path)
        _check_media_file(full_path)

        range_header = request.headers.get('Range', None)
        file_size = os.path.getsize(full_path)
        if range_header:
            return _partial_response(full_path, range_header, file_size)
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


def _error_response(e, status_code):
    return render_template('error.html', error=str(e)), status_code


@app.errorhandler(400)
def bad_request(e):
    return _error_response(e, 400)


@app.errorhandler(403)
def forbidden(e):
    return _error_response(e, 403)


@app.errorhandler(404)
def not_found(e):
    return _error_response(e, 404)


@app.errorhandler(500)
def server_error(e):
    return _error_response(e, 500)


def _create_sample_media():
    for media in SAMPLE_MEDIA:
        path = os.path.join(app.config['MEDIA_ROOT'], media)
        if not os.path.exists(path):
            open(path, 'wb').close()


if __name__ == '__main__':
    os.makedirs(app.config['MEDIA_ROOT'], exist_ok=True)
    _create_sample_media()
    app.run(host='0.0.0.0', port=8000, threaded=True)
