import os
from http.server import BaseHTTPRequestHandler, HTTPServer


class FileServerHandler(BaseHTTPRequestHandler):
    BASE_DIR = './files'

    def do_GET(self):
        try:
            if not self.path.startswith('/download'):
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'Not Found')
                return

            file_path = self.path.split('/download/')[1]
            self.serve_file(file_path)
        except Exception as error:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(error).encode())

    def serve_file(self, file_path):
        full_path = os.path.join(self.BASE_DIR, file_path)

        if not os.path.exists(full_path):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'File not found')
            return

        if os.path.isdir(full_path):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Directory listing not allowed')
            return

        try:
            with open(full_path, 'rb') as file:
                content = file.read()

            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header(
                'Content-Disposition',
                f'attachment; filename={os.path.basename(file_path)}',
            )
            self.end_headers()
            self.wfile.write(content)
        except Exception as error:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(error).encode())


def run_server(port=8000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, FileServerHandler)
    print(f'Server running on port {port}')
    httpd.serve_forever()


if __name__ == '__main__':
    os.makedirs('./files', exist_ok=True)
    with open('./files/test.txt', 'w') as file:
        file.write('Sample file content')
    run_server()
