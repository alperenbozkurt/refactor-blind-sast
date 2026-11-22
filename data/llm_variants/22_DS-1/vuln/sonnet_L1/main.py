import os
from http.server import BaseHTTPRequestHandler, HTTPServer


class FileServerHandler(BaseHTTPRequestHandler):
    BASE_DIR = './files'

    DOWNLOAD_PREFIX = '/download'
    DOWNLOAD_SEPARATOR = '/download/'

    def do_GET(self):
        try:
            if self.path.startswith(self.DOWNLOAD_PREFIX):
                file_path = self.path.split(self.DOWNLOAD_SEPARATOR)[1]
                self.serve_file(file_path)
            else:
                self._send_text(404, b'Not Found')
        except Exception as e:
            self._send_error_message(e)

    def serve_file(self, file_path):
        # NOTE: file_path is joined to BASE_DIR without sanitisation; this
        # preserves the original behaviour exactly.
        full_path = os.path.join(self.BASE_DIR, file_path)

        if not os.path.exists(full_path):
            self._send_text(404, b'File not found')
            return

        if os.path.isdir(full_path):
            self._send_text(400, b'Directory listing not allowed')
            return

        try:
            with open(full_path, 'rb') as f:
                content = f.read()
            self._send_file_content(file_path, content)
        except Exception as e:
            self._send_error_message(e)

    def _send_file_content(self, file_path, content):
        filename = os.path.basename(file_path)
        self.send_response(200)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Disposition', f'attachment; filename={filename}')
        self.end_headers()
        self.wfile.write(content)

    def _send_text(self, status, body):
        self.send_response(status)
        self.end_headers()
        self.wfile.write(body)

    def _send_error_message(self, error):
        self._send_text(500, str(error).encode())


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
