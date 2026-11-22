import pickle
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

SERVER_PORT = 8080


class AnalyticsConfig:
    """Holds analytics configuration loaded from serialized data."""

    def __init__(self):
        self.tracking_id = ''
        self.endpoints = []
        self.filters = {}

    def load_from_pickle(self, config_data):
        # NOTE: pickle deserialization is preserved as-is to keep behaviour
        # unchanged; it should only ever be used with trusted data.
        try:
            config = pickle.loads(config_data)
            self.tracking_id = config.tracking_id
            self.endpoints = config.endpoints
            self.filters = config.filters
            return True
        except Exception as e:
            print(f'Error loading config: {e}')
            return False


class AnalyticsService:
    """Manages configuration and recorded analytics events."""

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
    """HTTP handler exposing config upload and event recording endpoints."""

    def __init__(self, *args, **kwargs):
        self.analytics = AnalyticsService()
        super().__init__(*args, **kwargs)

    def do_POST(self):
        if self.path == '/upload_config':
            self._handle_upload_config()
        elif self.path == '/record':
            self._handle_record()
        else:
            self._respond(404)

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

    def _read_body(self):
        content_length = int(self.headers['Content-Length'])
        return self.rfile.read(content_length)

    def _respond(self, status, body=None):
        self.send_response(status)
        self.end_headers()
        if body is not None:
            self.wfile.write(body)


def run_server():
    port = SERVER_PORT
    server_address = ('', port)
    httpd = HTTPServer(server_address, RequestHandler)
    print(f'Starting analytics server on port {port}...')
    httpd.serve_forever()


if __name__ == '__main__':
    run_server()
