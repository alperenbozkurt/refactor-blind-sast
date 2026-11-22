import os
import posixpath
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote

MAX_FILE_SIZE = 10 * 1024 * 1024
CHUNK_SIZE = 8192
SERVER_PORT = 8000

INDEX_TEMPLATE = b'\n                <html>\n                <body>\n                    <h1>File Server</h1>\n                    <form action="/download" method="get">\n                        <input type="text" name="file" placeholder="Filename">\n                        <button type="submit">Download</button>\n                    </form>\n                    <p>Allowed file types: %s</p>\n                </body>\n                </html>\n            '


class FileServerHandler(BaseHTTPRequestHandler):
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'files'))
    ALLOWED_EXTENSIONS = {'.txt', '.pdf', '.docx'}

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

    def do_GET(self):
        if self.path.startswith('/download'):
            self._handle_download()
        else:
            self._send_index()

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

    def _send_index(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        extensions = ', '.join(self.ALLOWED_EXTENSIONS).encode()
        self.wfile.write(INDEX_TEMPLATE % extensions)

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
                self.send_response(200)
                self.send_header('Content-type', 'application/octet-stream')
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self.send_header('Content-Length', str(file_size))
                self.end_headers()
                for chunk in iter(lambda: f.read(CHUNK_SIZE), b''):
                    self.wfile.write(chunk)
        except PermissionError:
            self.send_error(403, 'Permission denied')
        except Exception:
            self.send_error(500, 'Internal server error')


def run_server():
    server_address = ('', SERVER_PORT)
    httpd = HTTPServer(server_address, FileServerHandler)
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
