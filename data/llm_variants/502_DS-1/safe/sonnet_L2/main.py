import pickle
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- Constants -------------------------------------------------------------

DEFAULT_PORT = 8080
DEFAULT_HOST = ''

PATH_UPLOAD_CONFIG = '/upload_config'
PATH_RECORD = '/record'

REQUIRED_EVENT_FIELDS = ('user_id', 'event_type', 'timestamp')

SAFE_MAIN_CLASS_NAMES = ('AnalyticsConfig',)
SAFE_BUILTINS = {'object': object, 'dict': dict, 'list': list, 'str': str}

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404

MSG_CONFIG_UPLOADED = b'Config uploaded successfully'
MSG_CONFIG_FAILED = b'Failed to upload config'
MSG_EVENT_RECORDED = b'Event recorded'
MSG_EVENT_INVALID = b'Invalid event data'


# --- Restricted unpickling helpers ----------------------------------------

def _build_safe_find_class():
    """Return a find_class function restricted to an allow-list of types."""
    safe_classes = {'AnalyticsConfig': AnalyticsConfig}

    def safe_find_class(module, name):
        if module == '__main__':
            if name in safe_classes:
                return safe_classes[name]
        elif module == 'builtins':
            if name in SAFE_BUILTINS:
                return SAFE_BUILTINS[name]
        raise pickle.UnpicklingError(
            f'Attempt to unpickle issue class {module}.{name}'
        )

    return safe_find_class


def _restricted_load(pickle_data):
    """Load pickle data using the restricted class lookup."""
    unpickler = pickle.Unpickler(pickle_data)
    unpickler.find_class = _build_safe_find_class()
    return unpickler.load()


# --- Domain classes --------------------------------------------------------

class AnalyticsConfig:

    def __init__(self):
        self.tracking_id = ''
        self.endpoints = []
        self.filters = {}

    def _apply(self, config):
        self.tracking_id = config.tracking_id
        self.endpoints = config.endpoints
        self.filters = config.filters

    def load_from_pickle(self, config_data):
        try:
            config = _restricted_load(config_data)
            self._apply(config)
            return True
        except Exception as e:
            print(f'Error loading config: {e}')
            return False


class AnalyticsService:

    def __init__(self):
        self.config = AnalyticsConfig()
        self.analytics_data = []

    def process_config_upload(self, config_file):
        if not config_file:
            return False
        success = self.config.load_from_pickle(config_file)
        if success:
            print('Config loaded successfully!')
            return True
        return False

    def record_event(self, event_data):
        if not self.validate_event(event_data):
            return False
        self.analytics_data.append(event_data)
        return True

    def validate_event(self, event_data):
        return all((field in event_data for field in REQUIRED_EVENT_FIELDS))


# --- HTTP layer ------------------------------------------------------------

class RequestHandler(BaseHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        self.analytics = AnalyticsService()
        super().__init__(*args, **kwargs)

    def _read_body(self):
        content_length = int(self.headers['Content-Length'])
        return self.rfile.read(content_length)

    def _respond(self, status, body=None):
        self.send_response(status)
        self.end_headers()
        if body is not None:
            self.wfile.write(body)

    def _handle_upload_config(self):
        post_data = self._read_body()
        if self.analytics.process_config_upload(post_data):
            self._respond(HTTP_OK, MSG_CONFIG_UPLOADED)
        else:
            self._respond(HTTP_BAD_REQUEST, MSG_CONFIG_FAILED)

    def _handle_record(self):
        post_data = self._read_body()
        event_data = json.loads(post_data.decode())
        if self.analytics.record_event(event_data):
            self._respond(HTTP_OK, MSG_EVENT_RECORDED)
        else:
            self._respond(HTTP_BAD_REQUEST, MSG_EVENT_INVALID)

    def do_POST(self):
        if self.path == PATH_UPLOAD_CONFIG:
            self._handle_upload_config()
        elif self.path == PATH_RECORD:
            self._handle_record()
        else:
            self._respond(HTTP_NOT_FOUND)


def run_server():
    port = DEFAULT_PORT
    server_address = (DEFAULT_HOST, port)
    httpd = HTTPServer(server_address, RequestHandler)
    print(f'Starting analytics server on port {port}...')
    httpd.serve_forever()


if __name__ == '__main__':
    run_server()
