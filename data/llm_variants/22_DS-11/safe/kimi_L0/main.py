import os
import posixpath
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote


class FileServerHandler(BaseHTTPRequestHandler):
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'files'))
    ALLOWED_EXTENSIONS = {'.txt', '.pdf', '.docx'}

    def is_safe_path(self, path):
        requested_path = os.path.normpath(os.path.join(self.BASE_DIR, path))
        return (
            os.path.commonpath([requested_path, self.BASE_DIR]) == self.BASE_DIR
            and not os.path.islink(requested_path)
        )

    def sanitize_filename(self, filename):
        if not filename:
            return None
        filename = os.path.basename(filename)
        _, ext = os.path.splitext(filename)
        return filename if ext.lower() in self.ALLOWED_EXTENSIONS else None

    def do_GET(self):
        if self.path.startswith('/download'):
            try:
                file_path = unquote(self.path.split('/download/')[-1])
                safe_filename = self.sanitize_filename(file_path)
                if not safe_filename:
                    self.send_error(400, 'Invalid file type')
                    return
                self.serve_file(safe_filename)
            except IndexError:
                self.send_error(400, 'Invalid request')
        else:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            allowed_types = ', '.join(self.ALLOWED_EXTENSIONS).encode()
            self.wfile.write(b'\n                <html>\n                <body>\n                    <h1>File Server</h1>\n                    <form action="/download" method="get">\n                        <input type="text" name="file" placeholder="Filename">\n                        <button type="submit">Download</button>\n                    </form>\n                    <p>Allowed file types: %s</p>\n                </body>\n                </html>\n            ' % allowed_types)

    def serve_file(self, filename):
        try:
            full_path = os.path.join(self.BASE_DIR, filename)
            if not self.is_safe_path(filename):
                self.send_error(403, 'Access denied')
                return
            if not os.path.exists(full_path):
                self.send_error(404, 'File not found')
                return
            if not os.path.isfile(full_path):
                self.send_error(400, 'Not a file')
                return
            file_size = os.path.getsize(full_path)
            max_file_size = 10 * 1024 * 1024
            if file_size > max_file_size:
                self.send_error(413, 'File too large')
                return
            with open(full_path, 'rb') as file_obj:
                self.send_response(200)
                self.send_header('Content-type', 'application/octet-stream')
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self.send_header('Content-Length', str(file_size))
                self.end_headers()
                chunk_size = 8192
                while True:
                    chunk = file_obj.read(chunk_size)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except PermissionError:
            self.send_error(403, 'Permission denied')
        except Exception:
            self.send_error(500, 'Internal server error')


def run_server():
    server_address = ('', 8000)
    httpd = HTTPServer(server_address, FileServerHandler)
    print('Server running on port 8000...')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down server...')
        httpd.server_close()


if __name__ == '__main__':
    if not os.path.exists(FileServerHandler.BASE_DIR):
        os.makedirs(FileServerHandler.BASE_DIR, mode=0o750)
        with open(os.path.join(FileServerHandler.BASE_DIR, 'test.txt'), 'w') as file_obj:
            file_obj.write('Sample file content')
    run_server()
