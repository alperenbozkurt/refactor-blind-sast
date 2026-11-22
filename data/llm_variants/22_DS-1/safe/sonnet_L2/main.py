import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote

# --- Constants ---------------------------------------------------------------

DEFAULT_BASE_DIR = './files'
DEFAULT_PORT = 8000
DEFAULT_HOST = ''

DOWNLOAD_PREFIX = '/download'
DOWNLOAD_SEPARATOR = '/download/'

SAMPLE_FILE_PATH = './files/test.txt'
SAMPLE_FILE_CONTENT = 'Sample file content'

CONTENT_TYPE_BINARY = 'application/octet-stream'

MSG_NOT_FOUND = b'Not Found'
MSG_FILE_NOT_FOUND = b'File not found'
MSG_DIRECTORY_NOT_ALLOWED = b'Directory listing not allowed'
MSG_ACCESS_DENIED = 'Access denied'


# --- Helpers -----------------------------------------------------------------

def extract_download_target(request_path):
    """Return the decoded file path requested after the download separator.

    Raises IndexError if the separator is missing (same as original behaviour).
    """
    return unquote(request_path.split(DOWNLOAD_SEPARATOR)[1])


def build_content_disposition(file_path):
    return f'attachment; filename={os.path.basename(file_path)}'


def is_within_base(full_path, base_dir):
    return full_path.startswith(os.path.abspath(base_dir))


def read_file_bytes(full_path):
    with open(full_path, 'rb') as f:
        return f.read()


# --- Request handler ---------------------------------------------------------

class FileServerHandler(BaseHTTPRequestHandler):
    BASE_DIR = DEFAULT_BASE_DIR

    # -- response helpers --

    def _send_body(self, status, body, headers=None):
        self.send_response(status)
        for name, value in (headers or []):
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_error_message(self, status, exc):
        self._send_body(status, str(exc).encode())

    # -- path helpers --

    def _resolve_full_path(self, file_path):
        full_path = os.path.abspath(os.path.join(self.BASE_DIR, file_path))
        if not is_within_base(full_path, self.BASE_DIR):
            raise ValueError(MSG_ACCESS_DENIED)
        return full_path

    # -- routes --

    def do_GET(self):
        try:
            if self.path.startswith(DOWNLOAD_PREFIX):
                file_path = extract_download_target(self.path)
                self.serve_file(file_path)
            else:
                self._send_body(404, MSG_NOT_FOUND)
        except Exception as e:
            self._send_error_message(500, e)

    def serve_file(self, file_path):
        try:
            full_path = self._resolve_full_path(file_path)
            if not os.path.exists(full_path):
                self._send_body(404, MSG_FILE_NOT_FOUND)
                return
            if os.path.isdir(full_path):
                self._send_body(400, MSG_DIRECTORY_NOT_ALLOWED)
                return
            content = read_file_bytes(full_path)
            self._send_body(
                200,
                content,
                [
                    ('Content-Type', CONTENT_TYPE_BINARY),
                    ('Content-Disposition', build_content_disposition(file_path)),
                ],
            )
        except ValueError as e:
            self._send_error_message(403, e)
        except Exception as e:
            self._send_error_message(500, e)


# --- Server bootstrap --------------------------------------------------------

def run_server(port=DEFAULT_PORT):
    server_address = (DEFAULT_HOST, port)
    httpd = HTTPServer(server_address, FileServerHandler)
    print(f'Server running on port {port}')
    httpd.serve_forever()


def prepare_sample_file():
    os.makedirs(DEFAULT_BASE_DIR, exist_ok=True)
    with open(SAMPLE_FILE_PATH, 'w') as f:
        f.write(SAMPLE_FILE_CONTENT)


def main():
    prepare_sample_file()
    run_server()


if __name__ == '__main__':
    main()
