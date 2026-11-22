"""A minimal HTTP file server with basic path traversal protection."""

import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote


class FileServerHandler(BaseHTTPRequestHandler):
    """Request handler that serves files located under ``BASE_DIR``."""

    BASE_DIR = './files'

    DOWNLOAD_ROUTE = '/download'
    DOWNLOAD_PREFIX = '/download/'

    def do_GET(self):
        """Route GET requests to the file download handler."""
        try:
            if self.path.startswith(self.DOWNLOAD_ROUTE):
                file_path = unquote(self.path.split(self.DOWNLOAD_PREFIX)[1])
                self.serve_file(file_path)
            else:
                self._respond(404, b'Not Found')
        except Exception as e:
            self._respond(500, str(e).encode())

    def serve_file(self, file_path):
        """Send the requested file to the client, guarding against traversal."""
        try:
            full_path = self._resolve_path(file_path)
            if not os.path.exists(full_path):
                self._respond(404, b'File not found')
                return
            if os.path.isdir(full_path):
                self._respond(400, b'Directory listing not allowed')
                return
            with open(full_path, 'rb') as f:
                content = f.read()
            headers = (
                ('Content-Type', 'application/octet-stream'),
                ('Content-Disposition', f'attachment; filename={os.path.basename(file_path)}'),
            )
            self._respond(200, content, headers)
        except ValueError as e:
            self._respond(403, str(e).encode())
        except Exception as e:
            self._respond(500, str(e).encode())

    def _resolve_path(self, file_path):
        """Return the absolute path for ``file_path`` or raise ``ValueError``."""
        full_path = os.path.abspath(os.path.join(self.BASE_DIR, file_path))
        if not full_path.startswith(os.path.abspath(self.BASE_DIR)):
            raise ValueError('Access denied')
        return full_path

    def _respond(self, status, body, headers=()):
        """Write a complete HTTP response with an optional set of headers."""
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)


def run_server(port=8000):
    """Start the HTTP server on the given port."""
    server_address = ('', port)
    httpd = HTTPServer(server_address, FileServerHandler)
    print(f'Server running on port {port}')
    httpd.serve_forever()


def _create_sample_files():
    """Create the base directory and a sample file for demonstration."""
    os.makedirs(FileServerHandler.BASE_DIR, exist_ok=True)
    sample_path = os.path.join(FileServerHandler.BASE_DIR, 'test.txt')
    with open(sample_path, 'w') as f:
        f.write('Sample file content')


if __name__ == '__main__':
    _create_sample_files()
    run_server()
