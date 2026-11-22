import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote

DOWNLOAD_PREFIX = '/download'
DOWNLOAD_SEPARATOR = '/download/'


class FileServerHandler(BaseHTTPRequestHandler):
    BASE_DIR = './files'

    def do_GET(self):
        try:
            if self.path.startswith(DOWNLOAD_PREFIX):
                file_path = unquote(self.path.split(DOWNLOAD_SEPARATOR)[1])
                self.serve_file(file_path)
            else:
                self._send_plain(404, b'Not Found')
        except Exception as e:
            self._send_error_message(500, e)

    def serve_file(self, file_path):
        try:
            full_path = self._resolve_path(file_path)

            if not os.path.exists(full_path):
                self._send_plain(404, b'File not found')
                return
            if os.path.isdir(full_path):
                self._send_plain(400, b'Directory listing not allowed')
                return

            with open(full_path, 'rb') as f:
                content = f.read()
            self._send_file(file_path, content)
        except ValueError as e:
            self._send_error_message(403, e)
        except Exception as e:
            self._send_error_message(500, e)

    def _resolve_path(self, file_path):
        """Resolve file_path against BASE_DIR, raising ValueError if it falls outside.

        Note: the original prefix-based containment check is intentionally preserved as is.
        """
        full_path = os.path.abspath(os.path.join(self.BASE_DIR, file_path))
        if not full_path.startswith(os.path.abspath(self.BASE_DIR)):
            raise ValueError('Access denied')
        return full_path

    def _send_plain(self, status, body):
        self.send_response(status)
        self.end_headers()
        self.wfile.write(body)

    def _send_error_message(self, status, error):
        self._send_plain(status, str(error).encode())

    def _send_file(self, file_path, content):
        self.send_response(200)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header(
            'Content-Disposition',
            f'attachment; filename={os.path.basename(file_path)}',
        )
        self.end_headers()
        self.wfile.write(content)


def run_server(port=8000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, FileServerHandler)
    print(f'Server running on port {port}')
    httpd.serve_forever()


if __name__ == '__main__':
    os.makedirs('./files', exist_ok=True)
    with open('./files/test.txt', 'w') as f:
        f.write('Sample file content')
    run_server()
