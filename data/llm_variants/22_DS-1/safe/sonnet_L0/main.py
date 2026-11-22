import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote


class FileServerHandler(BaseHTTPRequestHandler):
    BASE_DIR = './files'

    def _send_text(self, status, message):
        if isinstance(message, str):
            message = message.encode()
        self.send_response(status)
        self.end_headers()
        self.wfile.write(message)

    def do_GET(self):
        try:
            if self.path.startswith('/download'):
                file_path = unquote(self.path.split('/download/')[1])
                self.serve_file(file_path)
            else:
                self._send_text(404, b'Not Found')
        except Exception as e:
            self._send_text(500, str(e))

    def serve_file(self, file_path):
        try:
            base_path = os.path.abspath(self.BASE_DIR)
            full_path = os.path.abspath(os.path.join(self.BASE_DIR, file_path))

            if not full_path.startswith(base_path):
                raise ValueError('Access denied')
            if not os.path.exists(full_path):
                self._send_text(404, b'File not found')
                return
            if os.path.isdir(full_path):
                self._send_text(400, b'Directory listing not allowed')
                return

            with open(full_path, 'rb') as f:
                content = f.read()

            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header(
                'Content-Disposition',
                f'attachment; filename={os.path.basename(file_path)}',
            )
            self.end_headers()
            self.wfile.write(content)
        except ValueError as e:
            self._send_text(403, str(e))
        except Exception as e:
            self._send_text(500, str(e))


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
