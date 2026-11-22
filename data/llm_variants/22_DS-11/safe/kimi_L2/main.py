import os
import posixpath
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote

_DOWNLOAD_ROUTE = '/download'
_DOWNLOAD_ROUTE_PREFIX = '/download/'

_CONTENT_TYPE_HTML = 'text/html'
_CONTENT_TYPE_BINARY = 'application/octet-stream'

_ERROR_INVALID_REQUEST = 'Invalid request'
_ERROR_INVALID_FILE_TYPE = 'Invalid file type'
_ERROR_ACCESS_DENIED = 'Access denied'
_ERROR_FILE_NOT_FOUND = 'File not found'
_ERROR_NOT_A_FILE = 'Not a file'
_ERROR_FILE_TOO_LARGE = 'File too large'
_ERROR_PERMISSION_DENIED = 'Permission denied'
_ERROR_INTERNAL = 'Internal server error'

_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
_CHUNK_SIZE_BYTES = 8192

_SERVER_HOST = ''
_SERVER_PORT = 8000

_FILES_DIR_MODE = 488
_TEST_FILE_NAME = 'test.txt'
_TEST_FILE_CONTENT = 'Sample file content'


def _home_page(allowed_extensions):
    return (
        b'\n                <html>\n                <body>\n                    <h1>File Server</h1>\n                    <form action="/download" method="get">\n                        <input type="text" name="file" placeholder="Filename">\n                        <button type="submit">Download</button>\n                    </form>\n                    <p>Allowed file types: %s</p>\n                </body>\n                </html>\n            '
        % (', '.join(allowed_extensions).encode())
    )


def _download_file_path(path):
    return unquote(path.split(_DOWNLOAD_ROUTE_PREFIX)[-1])


def _stream_file(source, destination):
    while True:
        chunk = source.read(_CHUNK_SIZE_BYTES)
        if not chunk:
            break
        destination.write(chunk)


def _ensure_base_dir():
    if not os.path.exists(FileServerHandler.BASE_DIR):
        os.makedirs(FileServerHandler.BASE_DIR, mode=_FILES_DIR_MODE)
        with open(os.path.join(FileServerHandler.BASE_DIR, _TEST_FILE_NAME), 'w') as f:
            f.write(_TEST_FILE_CONTENT)


class FileServerHandler(BaseHTTPRequestHandler):
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'files'))
    ALLOWED_EXTENSIONS = {'.txt', '.pdf', '.docx'}

    def is_safe_path(self, path):
        requested_path = os.path.normpath(os.path.join(self.BASE_DIR, path))
        return os.path.commonpath([requested_path, self.BASE_DIR]) == self.BASE_DIR and (
            not os.path.islink(requested_path)
        )

    def sanitize_filename(self, filename):
        if not filename:
            return None
        filename = os.path.basename(filename)
        (_, ext) = os.path.splitext(filename)
        return filename if ext.lower() in self.ALLOWED_EXTENSIONS else None

    def do_GET(self):
        if self.path.startswith(_DOWNLOAD_ROUTE):
            try:
                file_path = _download_file_path(self.path)
                safe_filename = self.sanitize_filename(file_path)
                if not safe_filename:
                    self.send_error(400, _ERROR_INVALID_FILE_TYPE)
                    return
                self.serve_file(safe_filename)
            except IndexError:
                self.send_error(400, _ERROR_INVALID_REQUEST)
        else:
            self.send_response(200)
            self.send_header('Content-type', _CONTENT_TYPE_HTML)
            self.end_headers()
            self.wfile.write(_home_page(self.ALLOWED_EXTENSIONS))

    def serve_file(self, filename):
        try:
            full_path = os.path.join(self.BASE_DIR, filename)
            if not self.is_safe_path(filename):
                self.send_error(403, _ERROR_ACCESS_DENIED)
                return
            if not os.path.exists(full_path):
                self.send_error(404, _ERROR_FILE_NOT_FOUND)
                return
            if not os.path.isfile(full_path):
                self.send_error(400, _ERROR_NOT_A_FILE)
                return
            file_size = os.path.getsize(full_path)
            if file_size > _MAX_FILE_SIZE_BYTES:
                self.send_error(413, _ERROR_FILE_TOO_LARGE)
                return
            with open(full_path, 'rb') as f:
                self.send_response(200)
                self.send_header('Content-type', _CONTENT_TYPE_BINARY)
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self.send_header('Content-Length', str(file_size))
                self.end_headers()
                _stream_file(f, self.wfile)
        except PermissionError:
            self.send_error(403, _ERROR_PERMISSION_DENIED)
        except Exception:
            self.send_error(500, _ERROR_INTERNAL)


def run_server():
    server_address = (_SERVER_HOST, _SERVER_PORT)
    httpd = HTTPServer(server_address, FileServerHandler)
    print(f'Server running on port {_SERVER_PORT}...')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down server...')
        httpd.server_close()


if __name__ == '__main__':
    _ensure_base_dir()
    run_server()
