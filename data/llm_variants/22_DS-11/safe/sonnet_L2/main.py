import os
import posixpath
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote

# --- Configuration constants -------------------------------------------------

SERVER_HOST = ''
SERVER_PORT = 8000
SERVER_ADDRESS = (SERVER_HOST, SERVER_PORT)

FILES_DIR_NAME = 'files'
DEFAULT_BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), FILES_DIR_NAME)
)
DEFAULT_ALLOWED_EXTENSIONS = {'.txt', '.pdf', '.docx'}

BASE_DIR_MODE = 0o750  # 488 decimal
SAMPLE_FILE_NAME = 'test.txt'
SAMPLE_FILE_CONTENT = 'Sample file content'

DOWNLOAD_ROUTE = '/download'
DOWNLOAD_PREFIX = '/download/'

MAX_FILE_SIZE = 10 * 1024 * 1024
CHUNK_SIZE = 8192

CONTENT_TYPE_HTML = 'text/html'
CONTENT_TYPE_BINARY = 'application/octet-stream'

INDEX_PAGE_TEMPLATE = (
    b'\n                <html>\n                <body>\n                    '
    b'<h1>File Server</h1>\n                    '
    b'<form action="/download" method="get">\n                        '
    b'<input type="text" name="file" placeholder="Filename">\n                        '
    b'<button type="submit">Download</button>\n                    '
    b'</form>\n                    '
    b'<p>Allowed file types: %s</p>\n                '
    b'</body>\n                </html>\n            '
)


# --- Request handler ---------------------------------------------------------

class FileServerHandler(BaseHTTPRequestHandler):
    BASE_DIR = DEFAULT_BASE_DIR
    ALLOWED_EXTENSIONS = DEFAULT_ALLOWED_EXTENSIONS

    # -- Validation helpers --

    def is_safe_path(self, path):
        requested_path = os.path.normpath(os.path.join(self.BASE_DIR, path))
        return (
            os.path.commonpath([requested_path, self.BASE_DIR]) == self.BASE_DIR
            and (not os.path.islink(requested_path))
        )

    def sanitize_filename(self, filename):
        if not filename:
            return None
        filename = os.path.basename(filename)
        (_, ext) = os.path.splitext(filename)
        return filename if ext.lower() in self.ALLOWED_EXTENSIONS else None

    # -- Routing --

    def do_GET(self):
        if self.path.startswith(DOWNLOAD_ROUTE):
            self._handle_download_request()
        else:
            self._send_index_page()

    def _handle_download_request(self):
        try:
            file_path = unquote(self.path.split(DOWNLOAD_PREFIX)[-1])
            safe_filename = self.sanitize_filename(file_path)
            if not safe_filename:
                self.send_error(400, 'Invalid file type')
                return
            self.serve_file(safe_filename)
        except IndexError:
            self.send_error(400, 'Invalid request')

    # -- Responses --

    def _render_index_page(self):
        extensions = ', '.join(self.ALLOWED_EXTENSIONS).encode()
        return INDEX_PAGE_TEMPLATE % extensions

    def _send_index_page(self):
        self.send_response(200)
        self.send_header('Content-type', CONTENT_TYPE_HTML)
        self.end_headers()
        self.wfile.write(self._render_index_page())

    def serve_file(self, filename):
        try:
            full_path = os.path.join(self.BASE_DIR, filename)
            if not self.is_safe_path(filename):
                self.send_error(403, 'Access denied')
                return
            if not os.path.exists(full_path):
                self.send_error(404, 'File not found')
                return
            if not os.path.isfile(full_path):
                self.send_error(400, 'Not a file')
                return
            file_size = os.path.getsize(full_path)
            if file_size > MAX_FILE_SIZE:
                self.send_error(413, 'File too large')
                return
            with open(full_path, 'rb') as f:
                self._send_file_headers(filename, file_size)
                self._stream_file(f)
        except PermissionError:
            self.send_error(403, 'Permission denied')
        except Exception:
            self.send_error(500, 'Internal server error')

    def _send_file_headers(self, filename, file_size):
        self.send_response(200)
        self.send_header('Content-type', CONTENT_TYPE_BINARY)
        self.send_header(
            'Content-Disposition', f'attachment; filename="{filename}"'
        )
        self.send_header('Content-Length', str(file_size))
        self.end_headers()

    def _stream_file(self, file_obj, chunk_size=CHUNK_SIZE):
        while True:
            chunk = file_obj.read(chunk_size)
            if not chunk:
                break
            self.wfile.write(chunk)


# --- Server bootstrap --------------------------------------------------------

def run_server():
    server_address = SERVER_ADDRESS
    httpd = HTTPServer(server_address, FileServerHandler)
    print(f'Server running on port {SERVER_PORT}...')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down server...')
        httpd.server_close()


def ensure_base_dir():
    base_dir = FileServerHandler.BASE_DIR
    if not os.path.exists(base_dir):
        os.makedirs(base_dir, mode=BASE_DIR_MODE)
        with open(os.path.join(base_dir, SAMPLE_FILE_NAME), 'w') as f:
            f.write(SAMPLE_FILE_CONTENT)


if __name__ == '__main__':
    ensure_base_dir()
    run_server()
