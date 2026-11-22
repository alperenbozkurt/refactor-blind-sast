import os
import posixpath  # noqa: F401  (kept to preserve the module's namespace)
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote

SERVER_ADDRESS = ('', 8000)


class FileServerHandler(BaseHTTPRequestHandler):
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'files'))
    ALLOWED_EXTENSIONS = {'.txt', '.pdf', '.docx'}

    MAX_FILE_SIZE = 10 * 1024 * 1024
    CHUNK_SIZE = 8192
    DOWNLOAD_PREFIX = '/download'

    INDEX_TEMPLATE = (
        b'\n                <html>\n                <body>\n'
        b'                    <h1>File Server</h1>\n'
        b'                    <form action="/download" method="get">\n'
        b'                        <input type="text" name="file" placeholder="Filename">\n'
        b'                        <button type="submit">Download</button>\n'
        b'                    </form>\n'
        b'                    <p>Allowed file types: %s</p>\n'
        b'                </body>\n                </html>\n            '
    )

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    def is_safe_path(self, path):
        requested_path = os.path.normpath(os.path.join(self.BASE_DIR, path))
        is_inside_base = os.path.commonpath([requested_path, self.BASE_DIR]) == self.BASE_DIR
        return is_inside_base and not os.path.islink(requested_path)

    def sanitize_filename(self, filename):
        if not filename:
            return None
        filename = os.path.basename(filename)
        _, ext = os.path.splitext(filename)
        return filename if ext.lower() in self.ALLOWED_EXTENSIONS else None

    # ------------------------------------------------------------------
    # Request handling
    # ------------------------------------------------------------------
    def do_GET(self):
        if self.path.startswith(self.DOWNLOAD_PREFIX):
            self._handle_download()
        else:
            self._send_index_page()

    def _handle_download(self):
        try:
            file_path = unquote(self.path.split('/download/')[-1])
            safe_filename = self.sanitize_filename(file_path)
            if not safe_filename:
                self.send_error(400, 'Invalid file type')
                return
            self.serve_file(safe_filename)
        except IndexError:
            self.send_error(400, 'Invalid request')

    def _send_index_page(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        extensions = ', '.join(self.ALLOWED_EXTENSIONS).encode()
        self.wfile.write(self.INDEX_TEMPLATE % extensions)

    def _find_file_error(self, filename, full_path):
        """Return an (status, message) tuple if the file can't be served."""
        if not self.is_safe_path(filename):
            return 403, 'Access denied'
        if not os.path.exists(full_path):
            return 404, 'File not found'
        if not os.path.isfile(full_path):
            return 400, 'Not a file'
        return None

    def serve_file(self, filename):
        try:
            full_path = os.path.join(self.BASE_DIR, filename)

            error = self._find_file_error(filename, full_path)
            if error:
                self.send_error(*error)
                return

            file_size = os.path.getsize(full_path)
            if file_size > self.MAX_FILE_SIZE:
                self.send_error(413, 'File too large')
                return

            self._stream_file(full_path, filename, file_size)
        except PermissionError:
            self.send_error(403, 'Permission denied')
        except Exception:
            self.send_error(500, 'Internal server error')

    def _stream_file(self, full_path, filename, file_size):
        with open(full_path, 'rb') as f:
            self.send_response(200)
            self.send_header('Content-type', 'application/octet-stream')
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.send_header('Content-Length', str(file_size))
            self.end_headers()
            while True:
                chunk = f.read(self.CHUNK_SIZE)
                if not chunk:
                    break
                self.wfile.write(chunk)


def run_server():
    httpd = HTTPServer(SERVER_ADDRESS, FileServerHandler)
    print('Server running on port 8000...')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down server...')
        httpd.server_close()


def _ensure_base_dir():
    base_dir = FileServerHandler.BASE_DIR
    if not os.path.exists(base_dir):
        os.makedirs(base_dir, mode=0o750)
        with open(os.path.join(base_dir, 'test.txt'), 'w') as f:
            f.write('Sample file content')


if __name__ == '__main__':
    _ensure_base_dir()
    run_server()
