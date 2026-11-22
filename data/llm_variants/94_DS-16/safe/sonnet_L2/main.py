from django.http import JsonResponse, HttpResponse
from django.views import View
from django.conf import settings
from django.core.cache import cache
from django.utils.html import escape
import json
import hashlib
import datetime
from string import Template
import ast


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500

AUDIT_LOG_PATH = 'audit.log'

CONFIG_KEY_DEBUG = 'debug'
CONFIG_KEY_TIMEZONE = 'timezone'
CONFIG_KEY_ALLOWED_HOSTS = 'allowed_hosts'

DEFAULT_DEBUG = False
DEFAULT_TIMEZONE = 'UTC'
DEFAULT_ALLOWED_HOSTS = ('localhost',)

ERROR_INTERNAL = 'Internal server error'
ERROR_INVALID_JSON = 'Invalid JSON'
ERROR_TEMPLATE_REQUIRED = 'Template required'
ERROR_CONTEXT_NOT_DICT = 'Context must be a dictionary'
ERROR_CONFIG_REQUIRED = 'Valid config string required'
ERROR_CONFIG_FORMAT = 'Invalid config format'
ERROR_EVENT_DETAILS_REQUIRED = 'Event and details required'
ERROR_EVENT_DETAILS_TYPE = 'Event and details must be strings'

STATUS_CONFIG_UPDATED = 'Config updated'
STATUS_LOGGED = 'Logged'


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _error_response(message, status=HTTP_BAD_REQUEST):
    """Build a JSON error response."""
    return JsonResponse({'error': message}, status=status)


def _status_response(message):
    """Build a JSON success status response."""
    return JsonResponse({'status': message})


def _parse_json_body(request):
    """Parse the request body as JSON (may raise ValueError subclasses)."""
    return json.loads(request.body)


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

def _escape_context_value(value):
    """Escape a context value for safe HTML substitution."""
    return escape(str(value)) if value is not None else ''


def _build_safe_context(context):
    """Return a copy of the context with all values escaped."""
    return {key: _escape_context_value(value) for (key, value) in context.items()}


def _template_cache_key(template_str):
    """Compute the cache key for a template string."""
    return hashlib.md5(template_str.encode()).hexdigest()


class SafeTemplateRenderer:

    def __init__(self):
        self.template_cache = {}

    def _compile_template(self, template_str, context):
        try:
            template = Template(template_str)
            safe_context = _build_safe_context(context)
            return template.safe_substitute(safe_context)
        except Exception as e:
            raise ValueError(f'Template compilation error: {str(e)}')

    def render(self, template_str, context=None):
        if context is None:
            context = {}
        cache_key = _template_cache_key(template_str)
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
                return _error_response(ERROR_TEMPLATE_REQUIRED)
            if not isinstance(context, dict):
                return _error_response(ERROR_CONTEXT_NOT_DICT)
            rendered = self.renderer.render(template, context)
            return HttpResponse(rendered)
        except ValueError as e:
            return _error_response(str(e))
        except Exception as e:
            return _error_response(ERROR_INTERNAL, HTTP_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# Configuration management
# ---------------------------------------------------------------------------

def _default_config():
    """Return a fresh default configuration dictionary."""
    return {
        CONFIG_KEY_DEBUG: DEFAULT_DEBUG,
        CONFIG_KEY_TIMEZONE: DEFAULT_TIMEZONE,
        CONFIG_KEY_ALLOWED_HOSTS: list(DEFAULT_ALLOWED_HOSTS),
    }


class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_default_config()
        return cls._instance

    def _load_default_config(self):
        self.config = _default_config()

    def _apply_debug(self, new_config):
        value = new_config.get(CONFIG_KEY_DEBUG)
        if CONFIG_KEY_DEBUG in new_config and isinstance(value, bool):
            self.config[CONFIG_KEY_DEBUG] = value

    def _apply_timezone(self, new_config):
        value = new_config.get(CONFIG_KEY_TIMEZONE)
        if CONFIG_KEY_TIMEZONE in new_config and isinstance(value, str):
            self.config[CONFIG_KEY_TIMEZONE] = value

    def _apply_allowed_hosts(self, new_config):
        value = new_config.get(CONFIG_KEY_ALLOWED_HOSTS)
        if CONFIG_KEY_ALLOWED_HOSTS in new_config and isinstance(value, list):
            self.config[CONFIG_KEY_ALLOWED_HOSTS] = [
                host for host in value if isinstance(host, str)
            ]

    def update_from_string(self, config_str):
        try:
            new_config = ast.literal_eval(config_str)
            if isinstance(new_config, dict):
                self._apply_debug(new_config)
                self._apply_timezone(new_config)
                self._apply_allowed_hosts(new_config)
                return True
            return False
        except (ValueError, SyntaxError) as e:
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
            if not config_str or not isinstance(config_str, str):
                return _error_response(ERROR_CONFIG_REQUIRED)
            if ConfigManager().update_from_string(config_str):
                return _status_response(STATUS_CONFIG_UPDATED)
            return _error_response(ERROR_CONFIG_FORMAT)
        except json.JSONDecodeError:
            return _error_response(ERROR_INVALID_JSON)
        except Exception as e:
            return _error_response(ERROR_INTERNAL, HTTP_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

def _format_log_entry(timestamp, event, details):
    """Format a single audit log line."""
    return f'[{timestamp}] {event}: {details}\n'


def _append_to_audit_log(entry):
    """Append an entry to the audit log file."""
    with open(AUDIT_LOG_PATH, 'a') as f:
        f.write(entry)


class AuditLogger:

    @staticmethod
    def log(event, details):
        timestamp = datetime.datetime.now().isoformat()
        try:
            if not isinstance(event, str):
                event = str(event)
            if not isinstance(details, str):
                details = str(details)
            log_entry = _format_log_entry(timestamp, event, details)
            _append_to_audit_log(log_entry)
        except Exception as e:
            print(f'Failed to write audit log: {str(e)}')


class UserActivityAPI(View):

    def post(self, request):
        try:
            data = _parse_json_body(request)
            event = data.get('event')
            details = data.get('details')
            if not event or not details:
                return _error_response(ERROR_EVENT_DETAILS_REQUIRED)
            if not isinstance(event, str) or not isinstance(details, str):
                return _error_response(ERROR_EVENT_DETAILS_TYPE)
            AuditLogger.log(event, details)
            return _status_response(STATUS_LOGGED)
        except json.JSONDecodeError:
            return _error_response(ERROR_INVALID_JSON)
        except Exception as e:
            return _error_response(ERROR_INTERNAL, HTTP_INTERNAL_SERVER_ERROR)
