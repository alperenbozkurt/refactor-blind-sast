import io
import json
import os
import pickle
from http.server import BaseHTTPRequestHandler, HTTPServer


class _RestrictedUnpickler(pickle.Unpickler):
    """Unpickler that only permits reconstructing AnalyticsConfig objects.

    Unpickling arbitrary data with pickle.loads can execute arbitrary code,
    so every global lookup other than AnalyticsConfig is rejected.
    """

    _ALLOWED_MODULES = {'__main__', __name__}

    def find_class(self, module, name):
        if name == 'AnalyticsConfig' and module in self._ALLOWED_MODULES:
            return AnalyticsConfig
        raise pickle.UnpicklingError(f'Forbidden global: {module}.{name}')


def _safe_loads(data):
    return _RestrictedUnpickler(io.BytesIO(data)).load()


class AnalyticsConfig:

    def __init__(self):
        self.tracking_id = ''
        self.endpoints = []
        self.filters = {}

    def load_from_pickle(self, config_data):
        try:
            config = _safe_loads(config_data)
            self.tracking_id = config.tracking_id
            self.endpoints = config.endpoints
            self.filters = config.filters
            return True
        except Exception as e:
            print(f'Error loading config: {e}')
            return False


class AnalyticsService:
    REQUIRED_FIELDS = ('user_id', 'event_type', 'timestamp')

    def __init__(self):
        self.config = AnalyticsConfig()
        self.analytics_data = []

    def process_config_upload(self, config_file):
        if not config_file:
            return False
        if self.config.load_from_pickle(config_file):
            print('Config loaded successfully!')
            return True
        return False

    def record_event(self, event_data):
        if not self.validate_event(event_data):
            return False
        self.analytics_data.append(event_data)
        return True

    def validate_event(self, event_data):
        return all(field in event_data for field in self.REQUIRED_FIELDS)


class RequestHandler(BaseHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        self.analytics = AnalyticsService()
        super().__init__(*args, **kwargs)

    def _read_body(self):
        content_length = int(self.headers['Content-Length'])
        return self.rfile.read(content_length)

    def _respond(self, status, message=None):
        self.send_response(status)
        self.end_headers()
        if message is not None:
            self.wfile.write(message)

    def _handle_upload_config(self):
        post_data = self._read_body()
        if self.analytics.process_config_upload(post_data):
            self._respond(200, b'Config uploaded successfully')
        else:
            self._respond(400, b'Failed to upload config')

    def _handle_record(self):
        post_data = self._read_body()
        event_data = json.loads(post_data.decode())
        if self.analytics.record_event(event_data):
            self._respond(200, b'Event recorded')
        else:
            self._respond(400, b'Invalid event data')

    def do_POST(self):
        if self.path == '/upload_config':
            self._handle_upload_config()
        elif self.path == '/record':
            self._handle_record()
        else:
            self._respond(404)


def run_server():
    port = 8080
    server_address = ('', port)
    httpd = HTTPServer(server_address, RequestHandler)
    print(f'Starting analytics server on port {port}...')
    httpd.serve_forever()


if __name__ == '__main__':
    run_server()
