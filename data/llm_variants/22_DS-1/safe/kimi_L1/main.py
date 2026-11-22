import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote


class FileServerHandler(BaseHTTPRequestHandler):
    """HTTP request handler that serves files from BASE_DIR as downloads."""

    BASE_DIR = './files'

    def do_GET(self):
        try:
            if self.path.startswith('/download'):
                file_path = unquote(self.path.split('/download/')[1])
                self.serve_file(file_path)
            else:
                self._send_plain_response(404, b'Not Found')
        except Exception as e:
            self._send_plain_response(500, str(e).encode())

    def serve_file(self, file_path):
        try:
            full_path = os.path.abspath(os.path.join(self.BASE_DIR, file_path))
            if not full_path.startswith(os.path.abspath(self.BASE_DIR)):
                raise ValueError('Access denied')
            if not os.path.exists(full_path):
                self._send_plain_response(404, b'File not found')
                return
            if os.path.isdir(full_path):
                self._send_plain_response(400, b'Directory listing not allowed')
                return
            with open(full_path, 'rb') as f:
                content = f.read()
            self._send_file_response(content, file_path)
        except ValueError as e:
            self._send_plain_response(403, str(e).encode())
        except Exception as e:
            self._send_plain_response(500, str(e).encode())

    def _send_plain_response(self, status_code, body):
        """Send a response with no extra headers and the given body."""
        self.send_response(status_code)
        self.end_headers()
        self.wfile.write(body)

    def _send_file_response(self, content, file_path):
        """Send a 200 response carrying the file as an attachment."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Disposition', f'attachment; filename={os.path.basename(file_path)}')
        self.end_headers()
        self.wfile.write(content)


def run_server(port=8000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, FileServerHandler)
    print(f'Server running on port {port}')
    httpd.serve_forever()


def main():
    os.makedirs('./files', exist_ok=True)
    with open('./files/test.txt', 'w') as f:
        f.write('Sample file content')
    run_server()


if __name__ == '__main__':
    main()
