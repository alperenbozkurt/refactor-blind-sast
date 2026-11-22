import json
import os
import pickle
from http.server import BaseHTTPRequestHandler, HTTPServer

UPLOAD_CONFIG_PATH = '/upload_config'
RECORD_EVENT_PATH = '/record'
SERVER_PORT = 8080


class AnalyticsConfig:
    """Analytics configuration populated from a pickled payload."""

    def __init__(self):
        self.tracking_id = ''
        self.endpoints = []
        self.filters = {}

    def load_from_pickle(self, config_data):
        """Load configuration attributes from pickled data.

        Returns True when the payload was unpacked and applied,
        False otherwise.
        """
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
    """Loads configuration and validates/records analytics events."""

    REQUIRED_EVENT_FIELDS = ('user_id', 'event_type', 'timestamp')

    def __init__(self):
        self.config = AnalyticsConfig()
        self.analytics_data = []

    def process_config_upload(self, config_file):
        """Apply an uploaded config payload, returning True on success."""
        if not config_file:
            return False
        if self.config.load_from_pickle(config_file):
            print('Config loaded successfully!')
            return True
        return False

    def record_event(self, event_data):
        """Validate and store an event, returning True when recorded."""
        if not self.validate_event(event_data):
            return False
        self.analytics_data.append(event_data)
        return True

    def validate_event(self, event_data):
        """Return True when the event contains every required field."""
        return all(field in event_data for field in self.REQUIRED_EVENT_FIELDS)


class RequestHandler(BaseHTTPRequestHandler):
    """HTTP handler exposing the analytics upload and record endpoints."""

    def __init__(self, *args, **kwargs):
        self.analytics = AnalyticsService()
        super().__init__(*args, **kwargs)

    def do_POST(self):
        if self.path == UPLOAD_CONFIG_PATH:
            self._handle_config_upload()
        elif self.path == RECORD_EVENT_PATH:
            self._handle_event_record()
        else:
            self._respond(404)

    def _handle_config_upload(self):
        post_data = self._read_request_body()
        if self.analytics.process_config_upload(post_data):
            self._respond(200, b'Config uploaded successfully')
        else:
            self._respond(400, b'Failed to upload config')

    def _handle_event_record(self):
        post_data = self._read_request_body()
        event_data = json.loads(post_data.decode())
        if self.analytics.record_event(event_data):
            self._respond(200, b'Event recorded')
        else:
            self._respond(400, b'Invalid event data')

    def _read_request_body(self):
        content_length = int(self.headers['Content-Length'])
        return self.rfile.read(content_length)

    def _respond(self, status, body=b''):
        self.send_response(status)
        self.end_headers()
        if body:
            self.wfile.write(body)


def run_server():
    """Start the analytics HTTP server."""
    server_address = ('', SERVER_PORT)
    httpd = HTTPServer(server_address, RequestHandler)
    print(f'Starting analytics server on port {SERVER_PORT}...')
    httpd.serve_forever()


if __name__ == '__main__':
    run_server()
