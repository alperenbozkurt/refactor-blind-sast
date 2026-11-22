import os
from http.server import BaseHTTPRequestHandler, HTTPServer

SERVER_ADDRESS = ('', 8000)

DOWNLOAD_PREFIX = '/download'
DOWNLOAD_SPLIT_TOKEN = '/download/'

SAMPLE_FILE_NAME = 'test.txt'
SAMPLE_FILE_CONTENT = 'Sample file content'

INDEX_PAGE = (
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
    BASE_DIR = os.path.join(os.path.dirname(__file__), 'files')

    def do_GET(self):
        if self.path.startswith(DOWNLOAD_PREFIX):
            file_path = self.path.split(DOWNLOAD_SPLIT_TOKEN)[-1]
            self.serve_file(file_path)
        else:
            self._send_index_page()

    def _send_index_page(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(INDEX_PAGE)

    def serve_file(self, file_path):
        try:
            # NOTE: the requested path is joined to BASE_DIR without any
            # normalisation or containment check (behaviour intentionally
            # preserved from the original implementation).
            full_path = os.path.join(self.BASE_DIR, file_path)

            if not os.path.exists(full_path):
                self.send_error(404, 'File not found')
                return
            if not os.path.isfile(full_path):
                self.send_error(400, 'Not a file')
                return

            with open(full_path, 'rb') as f:
                self._send_file_headers(file_path)
                self.wfile.write(f.read())
        except Exception as e:
            self.send_error(500, f'Server error: {str(e)}')

    def _send_file_headers(self, file_path):
        self.send_response(200)
        self.send_header('Content-type', 'application/octet-stream')
        self.send_header(
            'Content-Disposition',
            f'attachment; filename="{os.path.basename(file_path)}"',
        )
        self.end_headers()


def run_server():
    httpd = HTTPServer(SERVER_ADDRESS, FileServerHandler)
    print('Server running on port 8000...')
    httpd.serve_forever()


def _ensure_base_dir():
    base_dir = FileServerHandler.BASE_DIR
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
        with open(os.path.join(base_dir, SAMPLE_FILE_NAME), 'w') as f:
            f.write(SAMPLE_FILE_CONTENT)


if __name__ == '__main__':
    _ensure_base_dir()
    run_server()
