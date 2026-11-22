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


def _error_response(message, status):
    """Build a JSON error response with the given message and HTTP status."""
    return JsonResponse({'error': message}, status=status)


class SafeTemplateRenderer:
    """Renders string templates with HTML-escaped context values."""

    def __init__(self):
        self.template_cache = {}

    @staticmethod
    def _escape_context(context):
        """Return a copy of the context with all values converted to escaped strings."""
        return {
            key: escape(str(value)) if value is not None else ''
            for key, value in context.items()
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
            if not template:
                return _error_response('Template required', 400)
            if not isinstance(context, dict):
                return _error_response('Context must be a dictionary', 400)
            rendered = self.renderer.render(template, context)
            return HttpResponse(rendered)
        except ValueError as e:
            return _error_response(str(e), 400)
        except Exception:
            return _error_response('Internal server error', 500)


class ConfigManager:
    """Singleton holding the application configuration."""

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

    def _apply_config_values(self, new_config):
        """Apply only the recognised, correctly typed values from new_config."""
        if 'debug' in new_config and isinstance(new_config['debug'], bool):
            self.config['debug'] = new_config['debug']
        if 'timezone' in new_config and isinstance(new_config['timezone'], str):
            self.config['timezone'] = new_config['timezone']
        if 'allowed_hosts' in new_config and isinstance(new_config['allowed_hosts'], list):
            self.config['allowed_hosts'] = [
                host for host in new_config['allowed_hosts'] if isinstance(host, str)
            ]

    def update_from_string(self, config_str):
        try:
            new_config = ast.literal_eval(config_str)
            if not isinstance(new_config, dict):
                return False
            self._apply_config_values(new_config)
            return True
        except (ValueError, SyntaxError) as e:
            print(f'Config update failed: {str(e)}')
            return False


class ConfigAPI(View):

    def get(self, request):
        config = ConfigManager().config
        return JsonResponse(config)

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
    """Appends audit entries to a log file."""

    @staticmethod
    def log(event, details):
        timestamp = datetime.datetime.now().isoformat()
        try:
            if not isinstance(event, str):
                event = str(event)
            if not isinstance(details, str):
                details = str(details)
            log_entry = f'[{timestamp}] {event}: {details}\n'
            with open('audit.log', 'a') as f:
                f.write(log_entry)
        except Exception as e:
            print(f'Failed to write audit log: {str(e)}')


class UserActivityAPI(View):

    def post(self, request):
        try:
            data = json.loads(request.body)
            event = data.get('event')
            details = data.get('details')
            if not event or not details:
                return _error_response('Event and details required', 400)
            if not isinstance(event, str) or not isinstance(details, str):
                return _error_response('Event and details must be strings', 400)
            AuditLogger.log(event, details)
            return JsonResponse({'status': 'Logged'})
        except json.JSONDecodeError:
            return _error_response('Invalid JSON', 400)
        except Exception:
            return _error_response('Internal server error', 500)
