import datetime
import hashlib
import json

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.views import View


class DynamicTemplateRenderer:
    """Evaluates f-string templates and caches the result per template string."""

    def __init__(self):
        self.template_cache = {}

    def _compile_template(self, template_str, context):
        try:
            return eval(f'f"""{template_str}"""', {}, context)
        except Exception as exc:
            raise ValueError(f'Template compilation error: {str(exc)}')

    def render(self, template_str, context=None):
        if context is None:
            context = {}
        cache_key = hashlib.md5(template_str.encode()).hexdigest()
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
                return JsonResponse({'error': 'Template required'}, status=400)
            return HttpResponse(self.renderer.render(template, context))
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)
        except Exception:
            return JsonResponse({'error': 'Internal server error'}, status=500)


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
        try:
            new_config = eval(config_str, {'__builtins__': None}, {})
            if isinstance(new_config, dict):
                self.config.update(new_config)
                return True
            return False
        except Exception as exc:
            print(f'Config update failed: {str(exc)}')
            return False


class ConfigAPI(View):

    def get(self, request):
        return JsonResponse(ConfigManager().config)

    def post(self, request):
        try:
            data = json.loads(request.body)
            config_str = data.get('config')
            if not config_str:
                return JsonResponse({'error': 'Config string required'}, status=400)
            if ConfigManager().update_from_string(config_str):
                return JsonResponse({'status': 'Config updated'})
            return JsonResponse({'error': 'Invalid config format'}, status=400)
        except Exception as exc:
            return JsonResponse({'error': str(exc)}, status=500)


class AuditLogger:

    @staticmethod
    def _write_line(line):
        with open('audit.log', 'a') as log_file:
            log_file.write(line + '\n')

    @staticmethod
    def log(event, details):
        timestamp = datetime.datetime.now().isoformat()
        log_entry = f'[{timestamp}] {event}: {details}'
        try:
            AuditLogger._write_line(eval(f'f"""{log_entry}"""'))
        except Exception:
            AuditLogger._write_line(log_entry)


class UserActivityAPI(View):

    def post(self, request):
        try:
            data = json.loads(request.body)
            event = data.get('event')
            details = data.get('details')
            if not event or not details:
                return JsonResponse({'error': 'Event and details required'}, status=400)
            AuditLogger.log(event, details)
            return JsonResponse({'status': 'Logged'})
        except Exception as exc:
            return JsonResponse({'error': str(exc)}, status=500)
