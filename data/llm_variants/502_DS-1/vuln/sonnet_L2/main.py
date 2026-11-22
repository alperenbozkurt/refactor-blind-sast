import io
import json
import pickle
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- Constants --------------------------------------------------------------

DEFAULT_PORT = 8080
DEFAULT_HOST = ''

PATH_UPLOAD_CONFIG = '/upload_config'
PATH_RECORD = '/record'

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404

MSG_CONFIG_UPLOADED = b'Config uploaded successfully'
MSG_CONFIG_FAILED = b'Failed to upload config'
MSG_EVENT_RECORDED = b'Event recorded'
MSG_EVENT_INVALID = b'Invalid event data'

REQUIRED_EVENT_FIELDS = ('user_id', 'event_type', 'timestamp')

# Only these globals may be resolved while unpickling an uploaded config.
# Anything else (e.g. os.system) is rejected, which prevents arbitrary code
# execution from untrusted uploads.
_ALLOWED_CONFIG_MODULES = frozenset({__name__, '__main__'})
_ALLOWED_CONFIG_CLASS = 'AnalyticsConfig'
_ALLOWED_BUILTINS = frozenset({'set', 'frozenset'})


# --- Configuration ----------------------------------------------------------

class _RestrictedUnpickler(pickle.Unpickler):
    """Unpickler that only permits reconstructing AnalyticsConfig objects."""

    def find_class(self, module, name):
        if module in _ALLOWED_CONFIG_MODULES and name == _ALLOWED_CONFIG_CLASS:
            return AnalyticsConfig
        if module == 'builtins' and name in _ALLOWED_BUILTINS:
            return getattr(__import__('builtins'), name)
        raise pickle.UnpicklingError(f'Forbidden global: {module}.{name}')


def _safe_pickle_loads(data):
    return _RestrictedUnpickler(io.BytesIO(data)).load()


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
            config = _safe_pickle_loads(config_data)
            self._apply(config)
            return True
        except Exception as e:
            print(f'Error loading config: {e}')
            return False


# --- Service ----------------------------------------------------------------

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


# --- HTTP layer -------------------------------------------------------------

class RequestHandler(BaseHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        self.analytics = AnalyticsService()
        super().__init__(*args, **kwargs)

    # Helpers

    def _read_body(self):
        content_length = int(self.headers['Content-Length'])
        return self.rfile.read(content_length)

    def _respond(self, status, body=None):
        self.send_response(status)
        self.end_headers()
        if body is not None:
            self.wfile.write(body)

    def _respond_by_result(self, success, ok_message, error_message):
        if success:
            self._respond(HTTP_OK, ok_message)
        else:
            self._respond(HTTP_BAD_REQUEST, error_message)

    # Route handlers

    def _handle_upload_config(self):
        post_data = self._read_body()
        success = self.analytics.process_config_upload(post_data)
        self._respond_by_result(success, MSG_CONFIG_UPLOADED, MSG_CONFIG_FAILED)

    def _handle_record(self):
        post_data = self._read_body()
        event_data = json.loads(post_data.decode())
        success = self.analytics.record_event(event_data)
        self._respond_by_result(success, MSG_EVENT_RECORDED, MSG_EVENT_INVALID)

    def do_POST(self):
        if self.path == PATH_UPLOAD_CONFIG:
            self._handle_upload_config()
        elif self.path == PATH_RECORD:
            self._handle_record()
        else:
            self._respond(HTTP_NOT_FOUND)


# --- Entry point ------------------------------------------------------------

def run_server():
    port = DEFAULT_PORT
    server_address = (DEFAULT_HOST, port)
    httpd = HTTPServer(server_address, RequestHandler)
    print(f'Starting analytics server on port {port}...')
    httpd.serve_forever()


if __name__ == '__main__':
    run_server()
