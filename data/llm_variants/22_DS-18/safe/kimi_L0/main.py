import os

from flask import Flask, request, send_file, abort, render_template, Response
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MEDIA_ROOT'] = os.path.abspath('/var/media')
app.config['ALLOWED_EXTENSIONS'] = {'mp4', 'avi', 'mov', 'mkv'}
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

_MIME_TYPES = {
    'mp4': 'video/mp4',
    'avi': 'video/x-msvideo',
    'mov': 'video/quicktime',
    'mkv': 'video/x-matroska',
}
_DEFAULT_MIME_TYPE = 'video/mp4'
_CHUNK_SIZE = 4096
_MEDIA_ROOT_MODE = 0o750
_MEDIA_FILE_MODE = 0o640
_SAMPLE_MEDIA_FILES = ('sample1.mp4', 'sample2.avi', 'sample3.mov')


def allowed_file(filename):
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in app.config['ALLOWED_EXTENSIONS']


def is_safe_path(base_path, requested_path):
    base_path = os.path.abspath(base_path)
    requested_path = os.path.abspath(requested_path)
    return requested_path.startswith(base_path + os.sep)


def _media_path(filename):
    return os.path.join(app.config['MEDIA_ROOT'], filename)


def _is_allowed_media_file(filename):
    return allowed_file(filename) and is_safe_path(
        app.config['MEDIA_ROOT'], _media_path(filename)
    )


def _list_media_files():
    return [
        f
        for f in os.listdir(app.config['MEDIA_ROOT'])
        if _is_allowed_media_file(f)
    ]


def _mime_type_for(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    return _MIME_TYPES.get(ext, _DEFAULT_MIME_TYPE)


def _parse_range_header(range_header, file_size):
    from_bytes, to_bytes = 0, None
    range_units = range_header.split('=')
    if len(range_units) == 2 and range_units[0] == 'bytes':
        range_bytes = range_units[1].split('-')
        from_bytes = int(range_bytes[0]) if range_bytes[0] else 0
        to_bytes = int(range_bytes[1]) if range_bytes[1] else file_size - 1
    return from_bytes, to_bytes


def _generate_file_chunks(path, start, length):
    with open(path, 'rb') as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            chunk = f.read(min(_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def _build_range_response(full_path, file_size, mimetype, range_header):
    from_bytes, to_bytes = _parse_range_header(range_header, file_size)
    length = to_bytes - from_bytes + 1
    return Response(
        _generate_file_chunks(full_path, from_bytes, length),
        206,
        mimetype=mimetype,
        direct_passthrough=True,
        headers={
            'Content-Range': f'bytes {from_bytes}-{to_bytes}/{file_size}',
            'Accept-Ranges': 'bytes',
            'Content-Length': str(length),
        },
    )


@app.route('/')
def index():
    media_files = []
    try:
        media_files = _list_media_files()
    except Exception as e:
        app.logger.error(f'Error listing media files: {e}')
    return render_template('browse.html', media_files=media_files)


@app.route('/stream/<path:media_path>')
def stream_media(media_path):
    try:
        if not media_path or not isinstance(media_path, str):
            abort(400, 'Invalid media path')
        safe_path = secure_filename(media_path)
        full_path = _media_path(safe_path)
        if not is_safe_path(app.config['MEDIA_ROOT'], full_path):
            abort(403, 'Access denied')
        if not os.path.exists(full_path):
            abort(404, 'Media file not found')
        if not os.path.isfile(full_path):
            abort(400, 'Requested path is not a file')
        if not allowed_file(full_path):
            abort(403, 'File type not allowed')
        mimetype = _mime_type_for(safe_path)
        range_header = request.headers.get('Range', None)
        file_size = os.path.getsize(full_path)
        if range_header:
            try:
                return _build_range_response(full_path, file_size, mimetype, range_header)
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
        if not is_safe_path(app.config['MEDIA_ROOT'], file_path):
            abort(403, 'Access denied')
        file.save(file_path)
        return 'File uploaded successfully'
    except Exception as e:
        app.logger.error(f'Upload error: {e}')
        abort(500, 'File upload failed')


@app.errorhandler(400)
def bad_request(e):
    return (render_template('error.html', error='Invalid request'), 400)


@app.errorhandler(403)
def forbidden(e):
    return (render_template('error.html', error='Access denied'), 403)


@app.errorhandler(404)
def not_found(e):
    return (render_template('error.html', error='Resource not found'), 404)


@app.errorhandler(500)
def server_error(e):
    return (render_template('error.html', error='Internal server error'), 500)


def _create_sample_media_files():
    for media in _SAMPLE_MEDIA_FILES:
        path = _media_path(media)
        if not os.path.exists(path):
            try:
                with open(path, 'wb') as f:
                    pass
                os.chmod(path, _MEDIA_FILE_MODE)
            except Exception as e:
                app.logger.error(f'Error creating sample media {media}: {e}')


if __name__ == '__main__':
    os.makedirs(app.config['MEDIA_ROOT'], mode=_MEDIA_ROOT_MODE, exist_ok=True)
    _create_sample_media_files()
    app.run(host='0.0.0.0', port=8000)
