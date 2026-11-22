import os
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- Configuration constants -------------------------------------------------

DEFAULT_PORT = 8000
DEFAULT_HOST = ''
DEFAULT_BASE_DIR = './files'

DOWNLOAD_ROUTE_PREFIX = '/download'
DOWNLOAD_PATH_SEPARATOR = '/download/'

CONTENT_TYPE_OCTET_STREAM = 'application/octet-stream'

SAMPLE_FILE_NAME = 'test.txt'
SAMPLE_FILE_CONTENT = 'Sample file content'

# HTTP status codes
HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500

# Response bodies
MSG_NOT_FOUND = b'Not Found'
MSG_FILE_NOT_FOUND = b'File not found'
MSG_DIRECTORY_LISTING_NOT_ALLOWED = b'Directory listing not allowed'


# --- Helper functions --------------------------------------------------------

def extract_download_path(request_path):
    """Return the file path portion of a /download/<file_path> request path.

    Raises IndexError if the separator is not present (handled by the caller
    and reported as a 500 response, as before).
    """
    return request_path.split(DOWNLOAD_PATH_SEPARATOR)[1]


def is_download_request(request_path):
    """Return True if the request path targets the download route."""
    return request_path.startswith(DOWNLOAD_ROUTE_PREFIX)


def build_content_disposition(file_path):
    """Build the Content-Disposition header value for a downloaded file."""
    return f'attachment; filename={os.path.basename(file_path)}'


def read_binary_file(full_path):
    """Read and return the full contents of a file in binary mode."""
    with open(full_path, 'rb') as f:
        return f.read()


# --- HTTP handler ------------------------------------------------------------

class FileServerHandler(BaseHTTPRequestHandler):
    BASE_DIR = DEFAULT_BASE_DIR

    # -- Routing --

    def do_GET(self):
        try:
            if is_download_request(self.path):
                file_path = extract_download_path(self.path)
                self.serve_file(file_path)
            else:
                self._send_plain_response(HTTP_NOT_FOUND, MSG_NOT_FOUND)
        except Exception as e:
            self._send_error_response(e)

    # -- File serving --

    def serve_file(self, file_path):
        # NOTE: file_path is joined to BASE_DIR without sanitisation; this
        # behaviour is intentionally preserved by the refactoring.
        full_path = os.path.join(self.BASE_DIR, file_path)
        if not os.path.exists(full_path):
            self._send_plain_response(HTTP_NOT_FOUND, MSG_FILE_NOT_FOUND)
            return
        if os.path.isdir(full_path):
            self._send_plain_response(HTTP_BAD_REQUEST, MSG_DIRECTORY_LISTING_NOT_ALLOWED)
            return
        try:
            content = read_binary_file(full_path)
            self._send_file_response(file_path, content)
        except Exception as e:
            self._send_error_response(e)

    # -- Response helpers --

    def _send_plain_response(self, status, body):
        self.send_response(status)
        self.end_headers()
        self.wfile.write(body)

    def _send_error_response(self, error):
        self._send_plain_response(HTTP_INTERNAL_SERVER_ERROR, str(error).encode())

    def _send_file_response(self, file_path, content):
        self.send_response(HTTP_OK)
        self.send_header('Content-Type', CONTENT_TYPE_OCTET_STREAM)
        self.send_header('Content-Disposition', build_content_disposition(file_path))
        self.end_headers()
        self.wfile.write(content)


# --- Server bootstrap --------------------------------------------------------

def run_server(port=DEFAULT_PORT):
    server_address = (DEFAULT_HOST, port)
    httpd = HTTPServer(server_address, FileServerHandler)
    print(f'Server running on port {port}')
    httpd.serve_forever()


def create_sample_file(base_dir=DEFAULT_BASE_DIR):
    """Ensure the base directory exists and contains the sample file."""
    os.makedirs(base_dir, exist_ok=True)
    sample_path = f'{base_dir}/{SAMPLE_FILE_NAME}'
    with open(sample_path, 'w') as f:
        f.write(SAMPLE_FILE_CONTENT)


def main():
    create_sample_file()
    run_server()


if __name__ == '__main__':
    main()
