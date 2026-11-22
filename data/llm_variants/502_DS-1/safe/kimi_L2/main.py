import json
import os
import pickle
from http.server import BaseHTTPRequestHandler, HTTPServer

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DEFAULT_PORT = 8080

ROUTE_UPLOAD_CONFIG = '/upload_config'
ROUTE_RECORD = '/record'

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404

MSG_CONFIG_UPLOADED = b'Config uploaded successfully'
MSG_CONFIG_UPLOAD_FAILED = b'Failed to upload config'
MSG_EVENT_RECORDED = b'Event recorded'
MSG_INVALID_EVENT = b'Invalid event data'

CONFIG_LOAD_SUCCESS_MESSAGE = 'Config loaded successfully!'

REQUIRED_EVENT_FIELDS = ('user_id', 'event_type', 'timestamp')

_MAIN_MODULE_NAME = '__main__'
_BUILTINS_MODULE_NAME = 'builtins'
_ALLOWED_BUILTINS = {
    'object': object,
    'dict': dict,
    'list': list,
    'str': str,
}


class AnalyticsConfig:

    def __init__(self):
        self.tracking_id = ''
        self.endpoints = []
        self.filters = {}

    def load_from_pickle(self, config_data):
        try:
            config = _restricted_unpickle(config_data)
            self.tracking_id = config.tracking_id
            self.endpoints = config.endpoints
            self.filters = config.filters
            return True
        except Exception as e:
            print(f'Error loading config: {e}')
            return False


# ---------------------------------------------------------------------------
# Restricted unpickling helpers
# ---------------------------------------------------------------------------

_ALLOWED_MAIN_CLASSES = {'AnalyticsConfig': AnalyticsConfig}


def _safe_find_class(module, name):
    """Resolve only explicitly allowed classes during unpickling."""
    if module == _MAIN_MODULE_NAME:
        if name in _ALLOWED_MAIN_CLASSES:
            return _ALLOWED_MAIN_CLASSES[name]
    elif module == _BUILTINS_MODULE_NAME:
        if name in _ALLOWED_BUILTINS:
            return _ALLOWED_BUILTINS[name]
    raise pickle.UnpicklingError(f'Attempt to unpickle issue class {module}.{name}')


def _restricted_unpickle(pickle_data):
    """Unpickle data while restricting which classes may be instantiated."""
    unpickler = pickle.Unpickler(pickle_data)
    unpickler.find_class = _safe_find_class
    return unpickler.load()


class AnalyticsService:

    def __init__(self):
        self.config = AnalyticsConfig()
        self.analytics_data = []

    def process_config_upload(self, config_file):
        if not config_file:
            return False
        success = self.config.load_from_pickle(config_file)
        if success:
            print(CONFIG_LOAD_SUCCESS_MESSAGE)
            return True
        return False

    def record_event(self, event_data):
        if not self.validate_event(event_data):
            return False
        self.analytics_data.append(event_data)
        return True

    def validate_event(self, event_data):
        return all(field in event_data for field in REQUIRED_EVENT_FIELDS)


# ---------------------------------------------------------------------------
# HTTP request/response helpers
# ---------------------------------------------------------------------------

def _read_request_body(handler):
    content_length = int(handler.headers['Content-Length'])
    return handler.rfile.read(content_length)


def _write_response(handler, status, body=None):
    handler.send_response(status)
    handler.end_headers()
    if body is not None:
        handler.wfile.write(body)


class RequestHandler(BaseHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        self.analytics = AnalyticsService()
        super().__init__(*args, **kwargs)

    def do_POST(self):
        if self.path == ROUTE_UPLOAD_CONFIG:
            self._handle_config_upload()
        elif self.path == ROUTE_RECORD:
            self._handle_record_event()
        else:
            _write_response(self, HTTP_NOT_FOUND)

    def _handle_config_upload(self):
        post_data = _read_request_body(self)
        if self.analytics.process_config_upload(post_data):
            _write_response(self, HTTP_OK, MSG_CONFIG_UPLOADED)
        else:
            _write_response(self, HTTP_BAD_REQUEST, MSG_CONFIG_UPLOAD_FAILED)

    def _handle_record_event(self):
        post_data = _read_request_body(self)
        event_data = json.loads(post_data.decode())
        if self.analytics.record_event(event_data):
            _write_response(self, HTTP_OK, MSG_EVENT_RECORDED)
        else:
            _write_response(self, HTTP_BAD_REQUEST, MSG_INVALID_EVENT)


def run_server():
    server_address = ('', DEFAULT_PORT)
    httpd = HTTPServer(server_address, RequestHandler)
    print(f'Starting analytics server on port {DEFAULT_PORT}...')
    httpd.serve_forever()


if __name__ == '__main__':
    run_server()
