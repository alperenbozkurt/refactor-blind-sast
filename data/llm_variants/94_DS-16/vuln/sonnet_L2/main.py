from django.http import JsonResponse, HttpResponse
from django.views import View
from django.conf import settings
from django.core.cache import cache
import json
import hashlib
import datetime


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500

AUDIT_LOG_PATH = 'audit.log'

ERROR_TEMPLATE_REQUIRED = 'Template required'
ERROR_INTERNAL = 'Internal server error'
ERROR_CONFIG_REQUIRED = 'Config string required'
ERROR_CONFIG_INVALID = 'Invalid config format'
ERROR_EVENT_DETAILS_REQUIRED = 'Event and details required'

STATUS_CONFIG_UPDATED = 'Config updated'
STATUS_LOGGED = 'Logged'


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _parse_json_body(request):
    """Decode the JSON request body."""
    return json.loads(request.body)


def _error_response(message, status):
    """Build a JSON error response."""
    return JsonResponse({'error': message}, status=status)


def _status_response(message):
    """Build a JSON success status response."""
    return JsonResponse({'status': message})


def _default_config():
    """Return a fresh copy of the default configuration."""
    return {
        'debug': False,
        'timezone': 'UTC',
        'allowed_hosts': ['localhost'],
    }


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

class DynamicTemplateRenderer:
    # SECURITY NOTE: templates are evaluated with eval(); rendering untrusted
    # templates allows arbitrary code execution. Behaviour is preserved here
    # deliberately by the refactor, but this should be replaced (e.g. with
    # Django templates or a sandboxed engine) before exposing to untrusted input.

    def __init__(self):
        self.template_cache = {}

    @staticmethod
    def _cache_key(template_str):
        return hashlib.md5(template_str.encode()).hexdigest()

    def _compile_template(self, template_str, context):
        try:
            compiled = eval(f'f"""{template_str}"""', {}, context)
            return compiled
        except Exception as e:
            raise ValueError(f'Template compilation error: {str(e)}')

    def render(self, template_str, context=None):
        if context is None:
            context = {}
        cache_key = self._cache_key(template_str)
        if cache_key not in self.template_cache:
            self.template_cache[cache_key] = self._compile_template(template_str, context)
        return self.template_cache[cache_key]


class TemplateAPI(View):
    renderer = DynamicTemplateRenderer()

    def post(self, request):
        try:
            data = _parse_json_body(request)
            template = data.get('template')
            context = data.get('context', {})
            if not template:
                return _error_response(ERROR_TEMPLATE_REQUIRED, HTTP_BAD_REQUEST)
            rendered = self.renderer.render(template, context)
            return HttpResponse(rendered)
        except ValueError as e:
            return _error_response(str(e), HTTP_BAD_REQUEST)
        except Exception as e:
            return _error_response(ERROR_INTERNAL, HTTP_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# Configuration management
# ---------------------------------------------------------------------------

class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_default_config()
        return cls._instance

    def _load_default_config(self):
        self.config = _default_config()

    @staticmethod
    def _parse_config_string(config_str):
        # SECURITY NOTE: eval() with stripped builtins is NOT a safe sandbox.
        # Consider ast.literal_eval or json.loads for untrusted input.
        return eval(config_str, {'__builtins__': None}, {})

    def update_from_string(self, config_str):
        try:
            new_config = self._parse_config_string(config_str)
            if isinstance(new_config, dict):
                self.config.update(new_config)
                return True
            return False
        except Exception as e:
            print(f'Config update failed: {str(e)}')
            return False


class ConfigAPI(View):

    def get(self, request):
        config = ConfigManager().config
        return JsonResponse(config)

    def post(self, request):
        try:
            data = _parse_json_body(request)
            config_str = data.get('config')
            if not config_str:
                return _error_response(ERROR_CONFIG_REQUIRED, HTTP_BAD_REQUEST)
            if ConfigManager().update_from_string(config_str):
                return _status_response(STATUS_CONFIG_UPDATED)
            return _error_response(ERROR_CONFIG_INVALID, HTTP_BAD_REQUEST)
        except Exception as e:
            return _error_response(str(e), HTTP_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

class AuditLogger:

    @staticmethod
    def _build_entry(event, details):
        timestamp = datetime.datetime.now().isoformat()
        log_entry = f'[{timestamp}] {event}: {details}'
        return timestamp, log_entry

    @staticmethod
    def _format_entry(log_entry, namespace):
        # SECURITY NOTE: eval() on user-supplied log content allows arbitrary
        # code execution. Behaviour preserved; should be removed in production.
        return eval(f'f"""{log_entry}"""', globals(), namespace)

    @staticmethod
    def _append(line):
        with open(AUDIT_LOG_PATH, 'a') as f:
            f.write(line + '\n')

    @staticmethod
    def log(event, details):
        timestamp, log_entry = AuditLogger._build_entry(event, details)
        namespace = {
            'event': event,
            'details': details,
            'timestamp': timestamp,
            'log_entry': log_entry,
        }
        try:
            formatted = AuditLogger._format_entry(log_entry, namespace)
            AuditLogger._append(formatted)
        except Exception:
            AuditLogger._append(log_entry)


class UserActivityAPI(View):

    def post(self, request):
        try:
            data = _parse_json_body(request)
            event = data.get('event')
            details = data.get('details')
            if not event or not details:
                return _error_response(ERROR_EVENT_DETAILS_REQUIRED, HTTP_BAD_REQUEST)
            AuditLogger.log(event, details)
            return _status_response(STATUS_LOGGED)
        except Exception as e:
            return _error_response(str(e), HTTP_INTERNAL_SERVER_ERROR)
