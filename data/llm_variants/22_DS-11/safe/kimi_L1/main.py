import os
import posixpath
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote


class FileServerHandler(BaseHTTPRequestHandler):
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "files"))
    ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx"}

    def is_safe_path(self, path):
        requested_path = os.path.normpath(os.path.join(self.BASE_DIR, path))
        is_within_base_dir = os.path.commonpath([requested_path, self.BASE_DIR]) == self.BASE_DIR
        return is_within_base_dir and not os.path.islink(requested_path)

    def sanitize_filename(self, filename):
        if not filename:
            return None

        filename = os.path.basename(filename)
        _, extension = os.path.splitext(filename)
        if extension.lower() not in self.ALLOWED_EXTENSIONS:
            return None
        return filename

    def do_GET(self):
        if self.path.startswith("/download"):
            try:
                file_path = unquote(self.path.split("/download/")[-1])
                safe_filename = self.sanitize_filename(file_path)
                if not safe_filename:
                    self.send_error(400, "Invalid file type")
                    return
                self.serve_file(safe_filename)
            except IndexError:
                self.send_error(400, "Invalid request")
        else:
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            allowed_extensions = ", ".join(self.ALLOWED_EXTENSIONS).encode()
            html_page = (
                b'\n'
                b'                <html>\n'
                b'                <body>\n'
                b'                    <h1>File Server</h1>\n'
                b'                    <form action="/download" method="get">\n'
                b'                        <input type="text" name="file" placeholder="Filename">\n'
                b'                        <button type="submit">Download</button>\n'
                b'                    </form>\n'
                b'                    <p>Allowed file types: %s</p>\n'
                b'                </body>\n'
                b'                </html>\n'
                b'            '
            ) % allowed_extensions
            self.wfile.write(html_page)

    def serve_file(self, filename):
        try:
            full_path = os.path.join(self.BASE_DIR, filename)
            if not self.is_safe_path(filename):
                self.send_error(403, "Access denied")
                return
            if not os.path.exists(full_path):
                self.send_error(404, "File not found")
                return
            if not os.path.isfile(full_path):
                self.send_error(400, "Not a file")
                return

            file_size = os.path.getsize(full_path)
            max_file_size = 10 * 1024 * 1024
            if file_size > max_file_size:
                self.send_error(413, "File too large")
                return

            with open(full_path, "rb") as file:
                self.send_response(200)
                self.send_header("Content-type", "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.send_header("Content-Length", str(file_size))
                self.end_headers()

                chunk_size = 8192
                while True:
                    chunk = file.read(chunk_size)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except PermissionError:
            self.send_error(403, "Permission denied")
        except Exception:
            self.send_error(500, "Internal server error")


def run_server():
    server_address = ("", 8000)
    httpd = HTTPServer(server_address, FileServerHandler)
    print("Server running on port 8000...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()


if __name__ == "__main__":
    if not os.path.exists(FileServerHandler.BASE_DIR):
        os.makedirs(FileServerHandler.BASE_DIR, mode=0o750)
        test_file_path = os.path.join(FileServerHandler.BASE_DIR, "test.txt")
        with open(test_file_path, "w") as test_file:
            test_file.write("Sample file content")
    run_server()
