import os
from http.server import BaseHTTPRequestHandler, HTTPServer


class FileServerHandler(BaseHTTPRequestHandler):
    BASE_DIR = os.path.join(os.path.dirname(__file__), 'files')

    def do_GET(self):
        if self.path.startswith('/download'):
            file_path = self.path.split('/download/')[-1]
            self.serve_file(file_path)
        else:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(
                b'\n'
                b'                <html>\n'
                b'                <body>\n'
                b'                    <h1>File Server</h1>\n'
                b'                    <form action="/download" method="get">\n'
                b'                        <input type="text" name="file" placeholder="Filename">\n'
                b'                        <button type="submit">Download</button>\n'
                b'                    </form>\n'
                b'                </body>\n'
                b'                </html>\n'
                b'            '
            )

    def serve_file(self, file_path):
        try:
            full_path = os.path.join(self.BASE_DIR, file_path)
            if not os.path.exists(full_path):
                self.send_error(404, 'File not found')
                return
            if not os.path.isfile(full_path):
                self.send_error(400, 'Not a file')
                return

            with open(full_path, 'rb') as file_obj:
                self.send_response(200)
                self.send_header('Content-type', 'application/octet-stream')
                self.send_header(
                    'Content-Disposition',
                    f'attachment; filename="{os.path.basename(file_path)}"',
                )
                self.end_headers()
                self.wfile.write(file_obj.read())
        except Exception as e:
            self.send_error(500, f'Server error: {str(e)}')


def run_server():
    server_address = ('', 8000)
    httpd = HTTPServer(server_address, FileServerHandler)
    print('Server running on port 8000...')
    httpd.serve_forever()


if __name__ == '__main__':
    base_dir = FileServerHandler.BASE_DIR
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
        with open(os.path.join(base_dir, 'test.txt'), 'w') as f:
            f.write('Sample file content')
    run_server()
