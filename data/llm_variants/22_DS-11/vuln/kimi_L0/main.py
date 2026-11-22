import os
from http.server import BaseHTTPRequestHandler, HTTPServer

_INDEX_HTML = b'''
                <html>
                <body>
                    <h1>File Server</h1>
                    <form action="/download" method="get">
                        <input type="text" name="file" placeholder="Filename">
                        <button type="submit">Download</button>
                    </form>
                </body>
                </html>
            '''


class FileServerHandler(BaseHTTPRequestHandler):
    BASE_DIR = os.path.join(os.path.dirname(__file__), 'files')

    def do_GET(self):
        if self.path.startswith('/download'):
            file_path = self.path.split('/download/')[-1]
            self.serve_file(file_path)
        else:
            self._serve_index_page()

    def _serve_index_page(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(_INDEX_HTML)

    def serve_file(self, file_path):
        try:
            full_path = os.path.join(self.BASE_DIR, file_path)
            if not os.path.exists(full_path):
                self.send_error(404, 'File not found')
                return
            if not os.path.isfile(full_path):
                self.send_error(400, 'Not a file')
                return
            with open(full_path, 'rb') as f:
                self._send_download_response(file_path, f)
        except Exception as e:
            self.send_error(500, f'Server error: {str(e)}')

    def _send_download_response(self, file_path, file_obj):
        self.send_response(200)
        self.send_header('Content-type', 'application/octet-stream')
        self.send_header(
            'Content-Disposition',
            f'attachment; filename="{os.path.basename(file_path)}"',
        )
        self.end_headers()
        self.wfile.write(file_obj.read())


def run_server():
    server_address = ('', 8000)
    httpd = HTTPServer(server_address, FileServerHandler)
    print('Server running on port 8000...')
    httpd.serve_forever()


if __name__ == '__main__':
    if not os.path.exists(FileServerHandler.BASE_DIR):
        os.makedirs(FileServerHandler.BASE_DIR)
        with open(os.path.join(FileServerHandler.BASE_DIR, 'test.txt'), 'w') as f:
            f.write('Sample file content')
    run_server()
