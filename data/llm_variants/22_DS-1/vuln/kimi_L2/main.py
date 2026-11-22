import os
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer


@dataclass(frozen=True)
class FileServerConfig:
    base_dir: str = './files'
    port: int = 8000
    download_route: str = '/download'
    sample_file_name: str = 'test.txt'
    sample_file_content: str = 'Sample file content'


DEFAULT_CONFIG = FileServerConfig()

DOWNLOAD_ROUTE = DEFAULT_CONFIG.download_route
DEFAULT_PORT = DEFAULT_CONFIG.port

STATUS_OK = 200
STATUS_BAD_REQUEST = 400
STATUS_NOT_FOUND = 404
STATUS_INTERNAL_SERVER_ERROR = 500

CONTENT_TYPE_OCTET_STREAM = 'application/octet-stream'

NOT_FOUND_MESSAGE = b'Not Found'
FILE_NOT_FOUND_MESSAGE = b'File not found'
DIRECTORY_LISTING_MESSAGE = b'Directory listing not allowed'


def _extract_download_file_path(path):
    return path.split(f'{DOWNLOAD_ROUTE}/')[1]


def _read_file_content(full_path):
    with open(full_path, 'rb') as f:
        return f.read()


class FileServerHandler(BaseHTTPRequestHandler):
    BASE_DIR = DEFAULT_CONFIG.base_dir

    def do_GET(self):
        try:
            if self.path.startswith(DOWNLOAD_ROUTE):
                file_path = _extract_download_file_path(self.path)
                self.serve_file(file_path)
            else:
                self._send_response(STATUS_NOT_FOUND, NOT_FOUND_MESSAGE)
        except Exception as e:
            self._send_error(e)

    def serve_file(self, file_path):
        full_path = self._full_path(file_path)
        if not os.path.exists(full_path):
            self._send_response(STATUS_NOT_FOUND, FILE_NOT_FOUND_MESSAGE)
            return
        if os.path.isdir(full_path):
            self._send_response(STATUS_BAD_REQUEST, DIRECTORY_LISTING_MESSAGE)
            return
        try:
            content = _read_file_content(full_path)
            self._send_file(file_path, content)
        except Exception as e:
            self._send_error(e)

    def _full_path(self, file_path):
        return os.path.join(self.BASE_DIR, file_path)

    def _send_response(self, status_code, body):
        self.send_response(status_code)
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, error):
        self._send_response(STATUS_INTERNAL_SERVER_ERROR, str(error).encode())

    def _send_file(self, file_path, content):
        self.send_response(STATUS_OK)
        self.send_header('Content-Type', CONTENT_TYPE_OCTET_STREAM)
        self.send_header('Content-Disposition', f'attachment; filename={os.path.basename(file_path)}')
        self.end_headers()
        self.wfile.write(content)


def _prepare_sample_file(config):
    os.makedirs(config.base_dir, exist_ok=True)
    sample_file_path = os.path.join(config.base_dir, config.sample_file_name)
    with open(sample_file_path, 'w') as f:
        f.write(config.sample_file_content)


def run_server(port=8000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, FileServerHandler)
    print(f'Server running on port {port}')
    httpd.serve_forever()


if __name__ == '__main__':
    _prepare_sample_file(DEFAULT_CONFIG)
    run_server()
