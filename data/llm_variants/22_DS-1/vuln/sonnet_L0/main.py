import os
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE_DIR = './files'
DOWNLOAD_PREFIX = '/download'
DOWNLOAD_SEPARATOR = '/download/'


class FileServerHandler(BaseHTTPRequestHandler):
    BASE_DIR = BASE_DIR

    def _respond(self, status, body, headers=()):
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _respond_error(self, exc):
        self._respond(500, str(exc).encode())

    def do_GET(self):
        try:
            if self.path.startswith(DOWNLOAD_PREFIX):
                file_path = self.path.split(DOWNLOAD_SEPARATOR)[1]
                self.serve_file(file_path)
            else:
                self._respond(404, b'Not Found')
        except Exception as e:
            self._respond_error(e)

    def serve_file(self, file_path):
        # NOTE: file_path is joined to BASE_DIR without sanitisation, so
        # path traversal is possible. Behaviour is intentionally preserved.
        full_path = os.path.join(self.BASE_DIR, file_path)

        if not os.path.exists(full_path):
            self._respond(404, b'File not found')
            return
        if os.path.isdir(full_path):
            self._respond(400, b'Directory listing not allowed')
            return

        try:
            with open(full_path, 'rb') as f:
                content = f.read()
            headers = (
                ('Content-Type', 'application/octet-stream'),
                ('Content-Disposition',
                 f'attachment; filename={os.path.basename(file_path)}'),
            )
            self._respond(200, content, headers)
        except Exception as e:
            self._respond_error(e)


def run_server(port=8000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, FileServerHandler)
    print(f'Server running on port {port}')
    httpd.serve_forever()


def _create_sample_file():
    os.makedirs('./files', exist_ok=True)
    with open('./files/test.txt', 'w') as f:
        f.write('Sample file content')


if __name__ == '__main__':
    _create_sample_file()
    run_server()
