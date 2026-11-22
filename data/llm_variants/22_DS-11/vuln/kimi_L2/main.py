"""Simple HTTP file server.

Serves a small HTML form on any non-download route and streams files from
the ``files`` directory (located next to this module) via ``/download/...``.
"""

import os
from http.server import BaseHTTPRequestHandler, HTTPServer

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SERVER_HOST = ''
SERVER_PORT = 8000

DOWNLOAD_ROUTE = '/download'
DOWNLOAD_PREFIX = '/download/'

CONTENT_TYPE_HTML = 'text/html'
CONTENT_TYPE_BINARY = 'application/octet-stream'

SAMPLE_FILENAME = 'test.txt'
SAMPLE_FILE_CONTENT = 'Sample file content'

INDEX_PAGE_HTML = (
    b'\n'
    b'                <html>\n'
    b'                <body>\n'
    b'                    <h1>File Server</h1>\n'
    b'                    <form action="/download" method="get">\n'
    b'                        <input type="text" name="file" placeholder="Filename">\n'
    b'                        <button type="submit">Download</button>\n'
    b'                    </form>\n'
    b'                </body>\n'
    b'                </html>\n'
    b'            '
)


class FileServerHandler(BaseHTTPRequestHandler):
    """HTTP request handler serving an index page and file downloads."""

    BASE_DIR = os.path.join(os.path.dirname(__file__), 'files')

    def do_GET(self):
        if self.path.startswith(DOWNLOAD_ROUTE):
            file_path = self.path.split(DOWNLOAD_PREFIX)[-1]
            self.serve_file(file_path)
        else:
            self._serve_index_page()

    def serve_file(self, file_path):
        try:
            full_path = os.path.join(self.BASE_DIR, file_path)
            if not os.path.exists(full_path):
                self.send_error(404, 'File not found')
                return
            if not os.path.isfile(full_path):
                self.send_error(400, 'Not a file')
                return
            self._stream_file(full_path, file_path)
        except Exception as e:
            self.send_error(500, f'Server error: {str(e)}')

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _serve_index_page(self):
        self.send_response(200)
        self.send_header('Content-type', CONTENT_TYPE_HTML)
        self.end_headers()
        self.wfile.write(INDEX_PAGE_HTML)

    def _stream_file(self, full_path, file_path):
        with open(full_path, 'rb') as f:
            self.send_response(200)
            self.send_header('Content-type', CONTENT_TYPE_BINARY)
            self.send_header(
                'Content-Disposition',
                f'attachment; filename="{os.path.basename(file_path)}"',
            )
            self.end_headers()
            self.wfile.write(f.read())


def run_server():
    server_address = (SERVER_HOST, SERVER_PORT)
    httpd = HTTPServer(server_address, FileServerHandler)
    print(f'Server running on port {SERVER_PORT}...')
    httpd.serve_forever()


def _ensure_base_dir():
    if not os.path.exists(FileServerHandler.BASE_DIR):
        os.makedirs(FileServerHandler.BASE_DIR)
        _write_sample_file()


def _write_sample_file():
    sample_path = os.path.join(FileServerHandler.BASE_DIR, SAMPLE_FILENAME)
    with open(sample_path, 'w') as f:
        f.write(SAMPLE_FILE_CONTENT)


if __name__ == '__main__':
    _ensure_base_dir()
    run_server()
