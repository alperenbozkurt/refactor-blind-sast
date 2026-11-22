import pickle
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

SAFE_MAIN_CLASSES_NAMES = ('AnalyticsConfig',)
SAFE_BUILTINS = {'object': object, 'dict': dict, 'list': list, 'str': str}


class AnalyticsConfig:

    def __init__(self):
        self.tracking_id = ''
        self.endpoints = []
        self.filters = {}

    @staticmethod
    def _restricted_load(pickle_data):
        """Unpickle data, allowing only a small whitelist of classes."""
        safe_classes = {'AnalyticsConfig': AnalyticsConfig}

        def safe_find_class(module, name):
            if module == '__main__' and name in safe_classes:
                return safe_classes[name]
            if module == 'builtins' and name in SAFE_BUILTINS:
                return SAFE_BUILTINS[name]
            raise pickle.UnpicklingError(
                f'Attempt to unpickle issue class {module}.{name}'
            )

        unpickler = pickle.Unpickler(pickle_data)
        unpickler.find_class = safe_find_class
        return unpickler.load()

    def load_from_pickle(self, config_data):
        try:
            config = self._restricted_load(config_data)
            self.tracking_id = config.tracking_id
            self.endpoints = config.endpoints
            self.filters = config.filters
            return True
        except Exception as e:
            print(f'Error loading config: {e}')
            return False


class AnalyticsService:
    REQUIRED_EVENT_FIELDS = ['user_id', 'event_type', 'timestamp']

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
        return all(field in event_data for field in self.REQUIRED_EVENT_FIELDS)


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
