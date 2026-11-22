import pickle
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

SERVER_PORT = 8080

UPLOAD_CONFIG_PATH = '/upload_config'
RECORD_EVENT_PATH = '/record'

REQUIRED_EVENT_FIELDS = ('user_id', 'event_type', 'timestamp')


def _restricted_pickle_load(pickle_data):
    """Unpickle ``pickle_data`` while allowing only a small set of safe classes.

    Only ``AnalyticsConfig`` (from ``__main__``) and a handful of builtin
    types may be resolved; anything else raises ``pickle.UnpicklingError``.
    """
    safe_classes = {'AnalyticsConfig': AnalyticsConfig}
    safe_builtins = {
        'object': object,
        'dict': dict,
        'list': list,
        'str': str,
    }

    def safe_find_class(module, name):
        if module == '__main__':
            if name in safe_classes:
                return safe_classes[name]
        elif module == 'builtins':
            if name in safe_builtins:
                return safe_builtins[name]
        raise pickle.UnpicklingError(
            f'Attempt to unpickle issue class {module}.{name}')

    unpickler = pickle.Unpickler(pickle_data)
    unpickler.find_class = safe_find_class
    return unpickler.load()


class AnalyticsConfig:
    """Configuration for the analytics service."""

    def __init__(self):
        self.tracking_id = ''
        self.endpoints = []
        self.filters = {}

    def load_from_pickle(self, config_data):
        """Load configuration from pickled data using the restricted loader."""
        try:
            config = _restricted_pickle_load(config_data)
            self.tracking_id = config.tracking_id
            self.endpoints = config.endpoints
            self.filters = config.filters
            return True
        except Exception as e:
            print(f'Error loading config: {e}')
            return False


class AnalyticsService:
    """Core analytics service holding configuration and recorded events."""

    def __init__(self):
        self.config = AnalyticsConfig()
        self.analytics_data = []

    def process_config_upload(self, config_file):
        """Load an uploaded configuration file."""
        if not config_file:
            return False
        if not self.config.load_from_pickle(config_file):
            return False
        print('Config loaded successfully!')
        return True

    def record_event(self, event_data):
        """Validate and store a single analytics event."""
        if not self.validate_event(event_data):
            return False
        self.analytics_data.append(event_data)
        return True

    def validate_event(self, event_data):
        """Return True if the event contains all required fields."""
        return all(field in event_data for field in REQUIRED_EVENT_FIELDS)


class RequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler exposing the analytics upload/record routes."""

    def __init__(self, *args, **kwargs):
        self.analytics = AnalyticsService()
        super().__init__(*args, **kwargs)

    def do_POST(self):
        if self.path == UPLOAD_CONFIG_PATH:
            self._handle_config_upload()
        elif self.path == RECORD_EVENT_PATH:
            self._handle_event_record()
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_config_upload(self):
        post_data = self._read_request_body()
        if self.analytics.process_config_upload(post_data):
            self._send_response_with_body(200, b'Config uploaded successfully')
        else:
            self._send_response_with_body(400, b'Failed to upload config')

    def _handle_event_record(self):
        post_data = self._read_request_body()
        event_data = json.loads(post_data.decode())
        if self.analytics.record_event(event_data):
            self._send_response_with_body(200, b'Event recorded')
        else:
            self._send_response_with_body(400, b'Invalid event data')

    def _read_request_body(self):
        content_length = int(self.headers['Content-Length'])
        return self.rfile.read(content_length)

    def _send_response_with_body(self, status_code, body):
        self.send_response(status_code)
        self.end_headers()
        self.wfile.write(body)


def run_server():
    server_address = ('', SERVER_PORT)
    httpd = HTTPServer(server_address, RequestHandler)
    print(f'Starting analytics server on port {SERVER_PORT}...')
    httpd.serve_forever()


if __name__ == '__main__':
    run_server()
