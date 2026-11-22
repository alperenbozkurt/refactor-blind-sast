import pickle
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

# ---------------------------------------------------------------------------
# Server configuration constants
# ---------------------------------------------------------------------------

SERVER_HOST = ''
SERVER_PORT = 8080

# Routes exposed by the analytics HTTP API.
ROUTE_UPLOAD_CONFIG = '/upload_config'
ROUTE_RECORD_EVENT = '/record'

# Fields every analytics event must contain to be considered valid.
REQUIRED_EVENT_FIELDS = ['user_id', 'event_type', 'timestamp']

# HTTP status codes returned by the request handler.
HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404

# Response bodies sent back to clients.
RESPONSE_CONFIG_UPLOADED = b'Config uploaded successfully'
RESPONSE_CONFIG_UPLOAD_FAILED = b'Failed to upload config'
RESPONSE_EVENT_RECORDED = b'Event recorded'
RESPONSE_EVENT_INVALID = b'Invalid event data'

# Messages logged to stdout.
LOG_CONFIG_LOAD_ERROR = 'Error loading config: {}'
LOG_CONFIG_LOADED = 'Config loaded successfully!'
LOG_SERVER_START = 'Starting analytics server on port {}...'


# ---------------------------------------------------------------------------
# HTTP helper functions
# ---------------------------------------------------------------------------

def _read_request_body(handler):
    """Read the raw body of an incoming request using its Content-Length."""
    content_length = int(handler.headers['Content-Length'])
    return handler.rfile.read(content_length)


def _send_response(handler, status_code, body):
    """Send a complete HTTP response: status line, headers and body."""
    handler.send_response(status_code)
    handler.end_headers()
    handler.wfile.write(body)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class AnalyticsConfig:
    """Holds the analytics tracking configuration.

    The configuration is populated from an uploaded pickled object that
    exposes ``tracking_id``, ``endpoints`` and ``filters`` attributes.
    """

    def __init__(self):
        self.tracking_id = ''
        self.endpoints = []
        self.filters = {}

    def load_from_pickle(self, config_data):
        try:
            config = pickle.loads(config_data)
            self._apply(config)
            return True
        except Exception as e:
            print(LOG_CONFIG_LOAD_ERROR.format(e))
            return False

    def _apply(self, config):
        """Copy the attributes of an unpickled config object onto this one."""
        self.tracking_id = config.tracking_id
        self.endpoints = config.endpoints
        self.filters = config.filters


# ---------------------------------------------------------------------------
# Core service
# ---------------------------------------------------------------------------

class AnalyticsService:
    """Owns the active configuration and the recorded analytics events."""

    def __init__(self):
        self.config = AnalyticsConfig()
        self.analytics_data = []

    def process_config_upload(self, config_file):
        if not config_file:
            return False
        if not self.config.load_from_pickle(config_file):
            return False
        print(LOG_CONFIG_LOADED)
        return True

    def record_event(self, event_data):
        if not self.validate_event(event_data):
            return False
        self.analytics_data.append(event_data)
        return True

    def validate_event(self, event_data):
        return all((field in event_data for field in REQUIRED_EVENT_FIELDS))


# ---------------------------------------------------------------------------
# HTTP request handler
# ---------------------------------------------------------------------------

class RequestHandler(BaseHTTPRequestHandler):
    """HTTP API used to upload configuration and record analytics events."""

    def __init__(self, *args, **kwargs):
        self.analytics = AnalyticsService()
        super().__init__(*args, **kwargs)

    def do_POST(self):
        if self.path == ROUTE_UPLOAD_CONFIG:
            self._handle_config_upload()
        elif self.path == ROUTE_RECORD_EVENT:
            self._handle_event_record()
        else:
            self._handle_unknown_route()

    def _handle_config_upload(self):
        post_data = _read_request_body(self)
        if self.analytics.process_config_upload(post_data):
            _send_response(self, HTTP_OK, RESPONSE_CONFIG_UPLOADED)
        else:
            _send_response(self, HTTP_BAD_REQUEST, RESPONSE_CONFIG_UPLOAD_FAILED)

    def _handle_event_record(self):
        post_data = _read_request_body(self)
        event_data = json.loads(post_data.decode())
        if self.analytics.record_event(event_data):
            _send_response(self, HTTP_OK, RESPONSE_EVENT_RECORDED)
        else:
            _send_response(self, HTTP_BAD_REQUEST, RESPONSE_EVENT_INVALID)

    def _handle_unknown_route(self):
        self.send_response(HTTP_NOT_FOUND)
        self.end_headers()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_server():
    server_address = (SERVER_HOST, SERVER_PORT)
    httpd = HTTPServer(server_address, RequestHandler)
    print(LOG_SERVER_START.format(SERVER_PORT))
    httpd.serve_forever()


if __name__ == '__main__':
    run_server()
