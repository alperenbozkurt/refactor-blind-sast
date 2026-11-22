"""Views and helpers for template rendering, runtime configuration and audit logging."""

import ast
import datetime
import hashlib
import json
from string import Template

from django.conf import settings  # noqa: F401 -- kept to preserve the module's public namespace
from django.core.cache import cache  # noqa: F401 -- kept to preserve the module's public namespace
from django.http import HttpResponse, JsonResponse
from django.utils.html import escape
from django.views import View


def _error_response(message, status):
    """Build a JSON error response with the given message and HTTP status code."""
    return JsonResponse({'error': message}, status=status)


class SafeTemplateRenderer:
    """Render ``string.Template`` templates with HTML-escaped context values.

    Rendered output is cached per template string; the cache key is derived
    from the template only, not from the context.
    """

    def __init__(self):
        self.template_cache = {}

    def _compile_template(self, template_str, context):
        try:
            template = Template(template_str)
            return template.safe_substitute(self._escape_context(context))
        except Exception as e:
            raise ValueError(f'Template compilation error: {e}')

    @staticmethod
    def _escape_context(context):
        """Return a copy of *context* with every value HTML-escaped."""
        return {
            key: escape(str(value)) if value is not None else ''
            for key, value in context.items()
        }

    def render(self, template_str, context=None):
        if context is None:
            context = {}
        cache_key = hashlib.md5(template_str.encode()).hexdigest()
        if cache_key not in self.template_cache:
            self.template_cache[cache_key] = self._compile_template(template_str, context)
        return self.template_cache[cache_key]


class TemplateAPI(View):
    renderer = SafeTemplateRenderer()

    def post(self, request):
        try:
            data = json.loads(request.body)
            template = data.get('template')
            context = data.get('context', {})

            validation_error = self._validate(template, context)
            if validation_error is not None:
                return validation_error

            return HttpResponse(self.renderer.render(template, context))
        except ValueError as e:
            return _error_response(str(e), 400)
        except Exception:
            return _error_response('Internal server error', 500)

    @staticmethod
    def _validate(template, context):
        """Return an error response if the payload is invalid, else ``None``."""
        if not template:
            return _error_response('Template required', 400)
        if not isinstance(context, dict):
            return _error_response('Context must be a dictionary', 400)
        return None


class ConfigManager:
    """Process-wide singleton holding the runtime configuration."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_default_config()
        return cls._instance

    def _load_default_config(self):
        self.config = {
            'debug': False,
            'timezone': 'UTC',
            'allowed_hosts': ['localhost'],
        }

    def update_from_string(self, config_str):
        """Merge an ``ast.literal_eval``-compatible dict string into the config.

        Returns ``True`` when the string parses to a dictionary, ``False``
        otherwise. Only recognised keys with values of the expected type are
        applied.
        """
        try:
            new_config = ast.literal_eval(config_str)
        except (ValueError, SyntaxError) as e:
            print(f'Config update failed: {e}')
            return False

        if not isinstance(new_config, dict):
            return False

        self._update_scalar_options(new_config)
        self._update_allowed_hosts(new_config)
        return True

    def _update_scalar_options(self, new_config):
        if isinstance(new_config.get('debug'), bool):
            self.config['debug'] = new_config['debug']
        if isinstance(new_config.get('timezone'), str):
            self.config['timezone'] = new_config['timezone']

    def _update_allowed_hosts(self, new_config):
        allowed_hosts = new_config.get('allowed_hosts')
        if isinstance(allowed_hosts, list):
            self.config['allowed_hosts'] = [
                host for host in allowed_hosts
                if isinstance(host, str)
            ]


class ConfigAPI(View):

    def get(self, request):
        return JsonResponse(ConfigManager().config)

    def post(self, request):
        try:
            data = json.loads(request.body)
            config_str = data.get('config')
            if not config_str or not isinstance(config_str, str):
                return _error_response('Valid config string required', 400)
            if ConfigManager().update_from_string(config_str):
                return JsonResponse({'status': 'Config updated'})
            return _error_response('Invalid config format', 400)
        except json.JSONDecodeError:
            return _error_response('Invalid JSON', 400)
        except Exception:
            return _error_response('Internal server error', 500)


class AuditLogger:
    """Append-only audit log writer; write failures are reported to stdout."""

    LOG_FILE = 'audit.log'

    @staticmethod
    def log(event, details):
        timestamp = datetime.datetime.now().isoformat()
        try:
            if not isinstance(event, str):
                event = str(event)
            if not isinstance(details, str):
                details = str(details)
            log_entry = f'[{timestamp}] {event}: {details}\n'
            with open(AuditLogger.LOG_FILE, 'a') as log_file:
                log_file.write(log_entry)
        except Exception as e:
            print(f'Failed to write audit log: {e}')


class UserActivityAPI(View):

    def post(self, request):
        try:
            data = json.loads(request.body)
            event = data.get('event')
            details = data.get('details')

            validation_error = self._validate(event, details)
            if validation_error is not None:
                return validation_error

            AuditLogger.log(event, details)
            return JsonResponse({'status': 'Logged'})
        except json.JSONDecodeError:
            return _error_response('Invalid JSON', 400)
        except Exception:
            return _error_response('Internal server error', 500)

    @staticmethod
    def _validate(event, details):
        """Return an error response if the payload is invalid, else ``None``."""
        if not event or not details:
            return _error_response('Event and details required', 400)
        if not isinstance(event, str) or not isinstance(details, str):
            return _error_response('Event and details must be strings', 400)
        return None
