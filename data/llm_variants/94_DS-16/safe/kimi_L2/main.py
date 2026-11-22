"""API views for safe template rendering, runtime configuration, and audit logging."""

import ast
import datetime
import hashlib
import json
from string import Template

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.utils.html import escape
from django.views import View

# ---------------------------------------------------------------------------
# HTTP status codes
# ---------------------------------------------------------------------------

HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500

# ---------------------------------------------------------------------------
# Response messages
# ---------------------------------------------------------------------------

ERROR_TEMPLATE_REQUIRED = 'Template required'
ERROR_CONTEXT_MUST_BE_DICT = 'Context must be a dictionary'
ERROR_INTERNAL_SERVER = 'Internal server error'
ERROR_CONFIG_STRING_REQUIRED = 'Valid config string required'
ERROR_INVALID_CONFIG_FORMAT = 'Invalid config format'
ERROR_INVALID_JSON = 'Invalid JSON'
ERROR_EVENT_AND_DETAILS_REQUIRED = 'Event and details required'
ERROR_EVENT_AND_DETAILS_MUST_BE_STRINGS = 'Event and details must be strings'

STATUS_CONFIG_UPDATED = 'Config updated'
STATUS_LOGGED = 'Logged'

# ---------------------------------------------------------------------------
# Configuration keys and defaults
# ---------------------------------------------------------------------------

CONFIG_KEY_DEBUG = 'debug'
CONFIG_KEY_TIMEZONE = 'timezone'
CONFIG_KEY_ALLOWED_HOSTS = 'allowed_hosts'

DEFAULT_DEBUG = False
DEFAULT_TIMEZONE = 'UTC'
DEFAULT_ALLOWED_HOSTS = ['localhost']

# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

AUDIT_LOG_PATH = 'audit.log'


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _error_response(message, status):
    """Build a JSON error response."""
    return JsonResponse({'error': message}, status=status)


def _status_response(message):
    """Build a JSON status response."""
    return JsonResponse({'status': message})


def _parse_json_body(request):
    """Decode the request body as JSON."""
    return json.loads(request.body)


def _ensure_str(value):
    """Return the value unchanged when it is a string, otherwise coerce it."""
    return value if isinstance(value, str) else str(value)


def _default_config():
    """Build a fresh copy of the default configuration."""
    return {
        CONFIG_KEY_DEBUG: DEFAULT_DEBUG,
        CONFIG_KEY_TIMEZONE: DEFAULT_TIMEZONE,
        CONFIG_KEY_ALLOWED_HOSTS: list(DEFAULT_ALLOWED_HOSTS),
    }


class SafeTemplateRenderer:

    def __init__(self):
        self.template_cache = {}

    @staticmethod
    def _cache_key(template_str):
        return hashlib.md5(template_str.encode()).hexdigest()

    @staticmethod
    def _escape_context(context):
        return {
            key: escape(str(value)) if value is not None else ''
            for (key, value) in context.items()
        }

    def _compile_template(self, template_str, context):
        try:
            template = Template(template_str)
            safe_context = self._escape_context(context)
            return template.safe_substitute(safe_context)
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
    renderer = SafeTemplateRenderer()

    def post(self, request):
        try:
            data = _parse_json_body(request)
            template = data.get('template')
            context = data.get('context', {})
            if not template:
                return _error_response(ERROR_TEMPLATE_REQUIRED, HTTP_BAD_REQUEST)
            if not isinstance(context, dict):
                return _error_response(ERROR_CONTEXT_MUST_BE_DICT, HTTP_BAD_REQUEST)
            rendered = self.renderer.render(template, context)
            return HttpResponse(rendered)
        except ValueError as e:
            return _error_response(str(e), HTTP_BAD_REQUEST)
        except Exception:
            return _error_response(ERROR_INTERNAL_SERVER, HTTP_INTERNAL_SERVER_ERROR)


class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_default_config()
        return cls._instance

    def _load_default_config(self):
        self.config = _default_config()

    def update_from_string(self, config_str):
        try:
            new_config = ast.literal_eval(config_str)
            if not isinstance(new_config, dict):
                return False
            self._apply_debug(new_config)
            self._apply_timezone(new_config)
            self._apply_allowed_hosts(new_config)
            return True
        except (ValueError, SyntaxError) as e:
            print(f'Config update failed: {str(e)}')
            return False

    def _apply_debug(self, new_config):
        if CONFIG_KEY_DEBUG in new_config and isinstance(new_config[CONFIG_KEY_DEBUG], bool):
            self.config[CONFIG_KEY_DEBUG] = new_config[CONFIG_KEY_DEBUG]

    def _apply_timezone(self, new_config):
        if CONFIG_KEY_TIMEZONE in new_config and isinstance(new_config[CONFIG_KEY_TIMEZONE], str):
            self.config[CONFIG_KEY_TIMEZONE] = new_config[CONFIG_KEY_TIMEZONE]

    def _apply_allowed_hosts(self, new_config):
        if CONFIG_KEY_ALLOWED_HOSTS in new_config and isinstance(new_config[CONFIG_KEY_ALLOWED_HOSTS], list):
            self.config[CONFIG_KEY_ALLOWED_HOSTS] = [
                host for host in new_config[CONFIG_KEY_ALLOWED_HOSTS]
                if isinstance(host, str)
            ]


class ConfigAPI(View):

    def get(self, request):
        config = ConfigManager().config
        return JsonResponse(config)

    def post(self, request):
        try:
            data = _parse_json_body(request)
            config_str = data.get('config')
            if not config_str or not isinstance(config_str, str):
                return _error_response(ERROR_CONFIG_STRING_REQUIRED, HTTP_BAD_REQUEST)
            if ConfigManager().update_from_string(config_str):
                return _status_response(STATUS_CONFIG_UPDATED)
            return _error_response(ERROR_INVALID_CONFIG_FORMAT, HTTP_BAD_REQUEST)
        except json.JSONDecodeError:
            return _error_response(ERROR_INVALID_JSON, HTTP_BAD_REQUEST)
        except Exception:
            return _error_response(ERROR_INTERNAL_SERVER, HTTP_INTERNAL_SERVER_ERROR)


class AuditLogger:

    @staticmethod
    def log(event, details):
        timestamp = datetime.datetime.now().isoformat()
        try:
            event = _ensure_str(event)
            details = _ensure_str(details)
            log_entry = f'[{timestamp}] {event}: {details}\n'
            with open(AUDIT_LOG_PATH, 'a') as log_file:
                log_file.write(log_entry)
        except Exception as e:
            print(f'Failed to write audit log: {str(e)}')


class UserActivityAPI(View):

    def post(self, request):
        try:
            data = _parse_json_body(request)
            event = data.get('event')
            details = data.get('details')
            if not event or not details:
                return _error_response(ERROR_EVENT_AND_DETAILS_REQUIRED, HTTP_BAD_REQUEST)
            if not isinstance(event, str) or not isinstance(details, str):
                return _error_response(ERROR_EVENT_AND_DETAILS_MUST_BE_STRINGS, HTTP_BAD_REQUEST)
            AuditLogger.log(event, details)
            return _status_response(STATUS_LOGGED)
        except json.JSONDecodeError:
            return _error_response(ERROR_INVALID_JSON, HTTP_BAD_REQUEST)
        except Exception:
            return _error_response(ERROR_INTERNAL_SERVER, HTTP_INTERNAL_SERVER_ERROR)
