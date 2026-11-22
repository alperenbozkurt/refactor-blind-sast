from django.http import JsonResponse, HttpResponse
from django.views import View
from django.conf import settings
from django.core.cache import cache
import json
import hashlib
import datetime


AUDIT_LOG_PATH = 'audit.log'


def _error_response(message, status):
    return JsonResponse({'error': message}, status=status)


class DynamicTemplateRenderer:
    """Renders f-string style templates, caching results by template text.

    WARNING: templates are evaluated with ``eval``; this executes arbitrary
    expressions supplied by the caller. Behaviour is preserved as-is.
    """

    def __init__(self):
        self.template_cache = {}

    def _compile_template(self, template_str, context):
        try:
            return eval(f'f"""{template_str}"""', {}, context)
        except Exception as e:
            raise ValueError(f'Template compilation error: {str(e)}')

    @staticmethod
    def _cache_key(template_str):
        return hashlib.md5(template_str.encode()).hexdigest()

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
            data = json.loads(request.body)
            template = data.get('template')
            context = data.get('context', {})
            if not template:
                return _error_response('Template required', 400)
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

    def update_from_string(self, config_str):
        try:
            new_config = eval(config_str, {'__builtins__': None}, {})
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
            data = json.loads(request.body)
            config_str = data.get('config')
            if not config_str:
                return _error_response('Config string required', 400)
            if ConfigManager().update_from_string(config_str):
                return JsonResponse({'status': 'Config updated'})
            return _error_response('Invalid config format', 400)
        except Exception as e:
            return _error_response(str(e), 500)


class AuditLogger:

    @staticmethod
    def _append_line(line):
        with open(AUDIT_LOG_PATH, 'a') as f:
            f.write(line + '\n')

    @staticmethod
    def log(event, details):
        # The local names below (event, details, timestamp, log_entry) are
        # visible to the ``eval`` call; they are kept unchanged on purpose.
        timestamp = datetime.datetime.now().isoformat()
        log_entry = f'[{timestamp}] {event}: {details}'
        try:
            formatted = eval(f'f"""{log_entry}"""')
            AuditLogger._append_line(formatted)
        except Exception:
            AuditLogger._append_line(log_entry)


class UserActivityAPI(View):

    def post(self, request):
        try:
            data = json.loads(request.body)
            event = data.get('event')
            details = data.get('details')
            if not event or not details:
                return _error_response('Event and details required', 400)
            AuditLogger.log(event, details)
            return JsonResponse({'status': 'Logged'})
        except Exception as e:
            return _error_response(str(e), 500)
