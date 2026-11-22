import os
from flask import Flask, request, send_file, abort, render_template, Response
from werkzeug.utils import secure_filename

DEFAULT_MEDIA_ROOT = '/var/media'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}
MAX_CONTENT_LENGTH_BYTES = 100 * 1024 * 1024

MIME_TYPES = {
    'mp4': 'video/mp4',
    'avi': 'video/x-msvideo',
    'mov': 'video/quicktime',
    'mkv': 'video/x-matroska',
}
DEFAULT_MIMETYPE = 'video/mp4'
RANGE_UNIT_BYTES = 'bytes'
CHUNK_SIZE_BYTES = 4096

BROWSE_TEMPLATE = 'browse.html'
ERROR_TEMPLATE = 'error.html'

MEDIA_ROOT_MODE = 0o750
MEDIA_FILE_MODE = 0o640
SAMPLE_MEDIA_FILES = ('sample1.mp4', 'sample2.avi', 'sample3.mov')
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

app = Flask(__name__)
app.config['MEDIA_ROOT'] = os.path.abspath(DEFAULT_MEDIA_ROOT)
app.config['ALLOWED_EXTENSIONS'] = ALLOWED_EXTENSIONS
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH_BYTES


def _extension(filename):
    return filename.rsplit('.', 1)[1].lower()


def _mimetype_for(filename):
    return MIME_TYPES.get(_extension(filename), DEFAULT_MIMETYPE)


def _is_media_file(root, filename):
    return allowed_file(filename) and is_safe_path(root, os.path.join(root, filename))


def _list_media_files(root):
    return [f for f in os.listdir(root) if _is_media_file(root, f)]


def _parse_range_header(range_header, file_size):
    from_bytes, to_bytes = 0, None
    range_units = range_header.split('=')
    if len(range_units) == 2 and range_units[0] == RANGE_UNIT_BYTES:
        range_bytes = range_units[1].split('-')
        from_bytes = int(range_bytes[0]) if range_bytes[0] else 0
        to_bytes = int(range_bytes[1]) if range_bytes[1] else file_size - 1
    length = to_bytes - from_bytes + 1
    return from_bytes, to_bytes, length


def _range_response(full_path, from_bytes, to_bytes, length, file_size, mimetype):
    def generate():
        with open(full_path, 'rb') as f:
            f.seek(from_bytes)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(CHUNK_SIZE_BYTES, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return Response(
        generate(),
        206,
        mimetype=mimetype,
        direct_passthrough=True,
        headers={
            'Content-Range': f'bytes {from_bytes}-{to_bytes}/{file_size}',
            'Accept-Ranges': 'bytes',
            'Content-Length': str(length),
        },
    )


def _prepare_media_root(root):
    os.makedirs(root, mode=MEDIA_ROOT_MODE, exist_ok=True)
    for media in SAMPLE_MEDIA_FILES:
        path = os.path.join(root, media)
        if not os.path.exists(path):
            try:
                with open(path, 'wb') as f:
                    pass
                os.chmod(path, MEDIA_FILE_MODE)
            except Exception as e:
                app.logger.error(f'Error creating sample media {media}: {e}')


def allowed_file(filename):
    if not filename or '.' not in filename:
        return False
    return _extension(filename) in app.config['ALLOWED_EXTENSIONS']


def is_safe_path(base_path, requested_path):
    base_path = os.path.abspath(base_path)
    requested_path = os.path.abspath(requested_path)
    return requested_path.startswith(base_path + os.sep)


@app.route('/')
def index():
    media_files = []
    try:
        media_files = _list_media_files(app.config['MEDIA_ROOT'])
    except Exception as e:
        app.logger.error(f'Error listing media files: {e}')
    return render_template(BROWSE_TEMPLATE, media_files=media_files)


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
        mimetype = _mimetype_for(safe_path)
        range_header = request.headers.get('Range', None)
        file_size = os.path.getsize(full_path)
        if range_header:
            try:
                from_bytes, to_bytes, length = _parse_range_header(range_header, file_size)
                return _range_response(full_path, from_bytes, to_bytes, length, file_size, mimetype)
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
        file_path = os.path.join(app.config['MEDIA_ROOT'], filename)
        if not is_safe_path(app.config['MEDIA_ROOT'], file_path):
            abort(403, 'Access denied')
        file.save(file_path)
        return 'File uploaded successfully'
    except Exception as e:
        app.logger.error(f'Upload error: {e}')
        abort(500, 'File upload failed')


@app.errorhandler(400)
def bad_request(e):
    return (render_template(ERROR_TEMPLATE, error='Invalid request'), 400)


@app.errorhandler(403)
def forbidden(e):
    return (render_template(ERROR_TEMPLATE, error='Access denied'), 403)


@app.errorhandler(404)
def not_found(e):
    return (render_template(ERROR_TEMPLATE, error='Resource not found'), 404)


@app.errorhandler(500)
def server_error(e):
    return (render_template(ERROR_TEMPLATE, error='Internal server error'), 500)


if __name__ == '__main__':
    _prepare_media_root(app.config['MEDIA_ROOT'])
    app.run(host=SERVER_HOST, port=SERVER_PORT)
