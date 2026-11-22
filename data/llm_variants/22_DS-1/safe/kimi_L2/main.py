"""A minimal HTTP file server.

Exposes the files stored under a base directory through
``GET /download/<path>`` requests. Running the module directly starts a
demo server on port 8000 after creating a sample file.
"""

import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

FILES_DIR = './files'
SERVER_HOST = ''
DEFAULT_PORT = 8000

DOWNLOAD_ROUTE_PREFIX = '/download'
DOWNLOAD_ROUTE = '/download/'

CONTENT_TYPE_BINARY = 'application/octet-stream'
CONTENT_DISPOSITION_TEMPLATE = 'attachment; filename={filename}'

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500

MSG_NOT_FOUND = b'Not Found'
MSG_FILE_NOT_FOUND = b'File not found'
MSG_DIR_LISTING_FORBIDDEN = b'Directory listing not allowed'
MSG_ACCESS_DENIED = 'Access denied'

SAMPLE_FILE_NAME = 'test.txt'
SAMPLE_FILE_CONTENT = 'Sample file content'


class FileServerHandler(BaseHTTPRequestHandler):
    """Request handler that serves files stored under ``BASE_DIR``."""

    BASE_DIR = FILES_DIR

    # -- routing -----------------------------------------------------------

    def do_GET(self):
        try:
            if self.path.startswith(DOWNLOAD_ROUTE_PREFIX):
                self.serve_file(self._extract_file_path())
            else:
                self._respond(HTTP_NOT_FOUND, MSG_NOT_FOUND)
        except Exception as e:
            self._respond(HTTP_INTERNAL_SERVER_ERROR, str(e).encode())

    # -- file serving --------------------------------------------------------

    def serve_file(self, file_path):
        try:
            full_path = self._resolve_path(file_path)
            if not os.path.exists(full_path):
                self._respond(HTTP_NOT_FOUND, MSG_FILE_NOT_FOUND)
                return
            if os.path.isdir(full_path):
                self._respond(HTTP_BAD_REQUEST, MSG_DIR_LISTING_FORBIDDEN)
                return
            self._send_file(full_path, file_path)
        except ValueError as e:
            self._respond(HTTP_FORBIDDEN, str(e).encode())
        except Exception as e:
            self._respond(HTTP_INTERNAL_SERVER_ERROR, str(e).encode())

    # -- helpers ---------------------------------------------------------------

    def _extract_file_path(self):
        """Return the URL-decoded file path taken from the request path."""
        return unquote(self.path.split(DOWNLOAD_ROUTE)[1])

    def _resolve_path(self, file_path):
        """Return the absolute path for ``file_path``.

        Raises ``ValueError`` if the resolved path escapes ``BASE_DIR``.
        """
        full_path = os.path.abspath(os.path.join(self.BASE_DIR, file_path))
        if not full_path.startswith(os.path.abspath(self.BASE_DIR)):
            raise ValueError(MSG_ACCESS_DENIED)
        return full_path

    def _send_file(self, full_path, file_path):
        """Stream the file at ``full_path`` back to the client."""
        with open(full_path, 'rb') as f:
            content = f.read()
        self.send_response(HTTP_OK)
        self.send_header('Content-Type', CONTENT_TYPE_BINARY)
        self.send_header(
            'Content-Disposition',
            CONTENT_DISPOSITION_TEMPLATE.format(filename=os.path.basename(file_path)),
        )
        self.end_headers()
        self.wfile.write(content)

    def _respond(self, status, body):
        """Send a plain response with the given status code and body."""
        self.send_response(status)
        self.end_headers()
        self.wfile.write(body)


def run_server(port=DEFAULT_PORT):
    """Start the HTTP file server on ``port`` and serve requests forever."""
    server_address = (SERVER_HOST, port)
    httpd = HTTPServer(server_address, FileServerHandler)
    print(f'Server running on port {port}')
    httpd.serve_forever()


def create_sample_file(base_dir=FILES_DIR):
    """Create the base directory (if needed) and write a sample file."""
    os.makedirs(base_dir, exist_ok=True)
    sample_path = os.path.join(base_dir, SAMPLE_FILE_NAME)
    with open(sample_path, 'w') as f:
        f.write(SAMPLE_FILE_CONTENT)


def main():
    """Entry point used when the module is executed as a script."""
    create_sample_file(FileServerHandler.BASE_DIR)
    run_server()


if __name__ == '__main__':
    main()
