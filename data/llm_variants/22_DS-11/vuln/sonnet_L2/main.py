import os
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = ''
PORT = 8000
SERVER_ADDRESS = (HOST, PORT)

FILES_DIR_NAME = 'files'
DEFAULT_BASE_DIR = os.path.join(os.path.dirname(__file__), FILES_DIR_NAME)

SAMPLE_FILE_NAME = 'test.txt'
SAMPLE_FILE_CONTENT = 'Sample file content'

DOWNLOAD_ROUTE = '/download'
DOWNLOAD_PREFIX = '/download/'

CONTENT_TYPE_HTML = 'text/html'
CONTENT_TYPE_BINARY = 'application/octet-stream'

INDEX_PAGE = (
    b'\n                <html>\n                <body>\n'
    b'                    <h1>File Server</h1>\n'
    b'                    <form action="/download" method="get">\n'
    b'                        <input type="text" name="file" placeholder="Filename">\n'
    b'                        <button type="submit">Download</button>\n'
    b'                    </form>\n'
    b'                </body>\n                </html>\n            '
)


def extract_requested_path(request_path):
    """Return the file path portion of a download request path."""
    return request_path.split(DOWNLOAD_PREFIX)[-1]


def is_within_directory(path, directory):
    """Return True if ``path`` resolves to a location inside ``directory``."""
    try:
        real_path = os.path.realpath(path)
        real_dir = os.path.realpath(directory)
        return os.path.commonpath([real_path, real_dir]) == real_dir
    except ValueError:
        return False


def build_content_disposition(file_path):
    return f'attachment; filename="{os.path.basename(file_path)}"'


def ensure_base_dir(base_dir):
    """Create the base directory with a sample file if it does not exist."""
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
        with open(os.path.join(base_dir, SAMPLE_FILE_NAME), 'w') as f:
            f.write(SAMPLE_FILE_CONTENT)


class FileServerHandler(BaseHTTPRequestHandler):
    BASE_DIR = DEFAULT_BASE_DIR

    def do_GET(self):
        if self.path.startswith(DOWNLOAD_ROUTE):
            file_path = extract_requested_path(self.path)
            self.serve_file(file_path)
        else:
            self._send_index()

    def _send_index(self):
        self.send_response(200)
        self.send_header('Content-type', CONTENT_TYPE_HTML)
        self.end_headers()
        self.wfile.write(INDEX_PAGE)

    def _send_file(self, full_path, file_path):
        with open(full_path, 'rb') as f:
            self.send_response(200)
            self.send_header('Content-type', CONTENT_TYPE_BINARY)
            self.send_header('Content-Disposition', build_content_disposition(file_path))
            self.end_headers()
            self.wfile.write(f.read())

    def serve_file(self, file_path):
        try:
            full_path = os.path.join(self.BASE_DIR, file_path)
            # Security: refuse paths (e.g. "../" or absolute paths) that
            # resolve outside the served directory.
            if not is_within_directory(full_path, self.BASE_DIR):
                self.send_error(404, 'File not found')
                return
            if not os.path.exists(full_path):
                self.send_error(404, 'File not found')
                return
            if not os.path.isfile(full_path):
                self.send_error(400, 'Not a file')
                return
            self._send_file(full_path, file_path)
        except Exception as e:
            self.send_error(500, f'Server error: {str(e)}')


def run_server():
    server_address = SERVER_ADDRESS
    httpd = HTTPServer(server_address, FileServerHandler)
    print(f'Server running on port {PORT}...')
    httpd.serve_forever()


def main():
    ensure_base_dir(FileServerHandler.BASE_DIR)
    run_server()


if __name__ == '__main__':
    main()
