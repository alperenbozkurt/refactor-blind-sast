import ast
import datetime
import hashlib
import json
import re

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.views import View

AUDIT_LOG_PATH = 'audit.log'

_PLACEHOLDER_RE = re.compile(r'\{\{|\}\}|\{([A-Za-z_][A-Za-z0-9_]*)\}|[{}]')


class DynamicTemplateRenderer:
    """Renders simple templates with ``{name}`` placeholders.

    User-supplied templates are never passed to eval(); only plain variable
    substitution is supported ('{{' and '}}' produce literal braces).
    """

    def __init__(self):
        self.template_cache = {}

    @staticmethod
    def _parse_template(template_str):
        tokens = []
        pos = 0
        for match in _PLACEHOLDER_RE.finditer(template_str):
            if match.start() > pos:
                tokens.append(('text', template_str[pos:match.start()]))
            token = match.group(0)
            if token == '{{':
                tokens.append(('text', '{'))
            elif token == '}}':
                tokens.append(('text', '}'))
            elif match.group(1) is not None:
                tokens.append(('var', match.group(1)))
            else:
                raise ValueError('unmatched brace in template')
            pos = match.end()
        if pos < len(template_str):
            tokens.append(('text', template_str[pos:]))
        return tokens

    def _compile_template(self, template_str):
        try:
            return self._parse_template(template_str)
        except Exception as e:
            raise ValueError(f'Template compilation error: {str(e)}')

    @staticmethod
    def _apply_context(tokens, context):
        parts = []
        for kind, value in tokens:
            if kind == 'text':
                parts.append(value)
            elif value in context:
                parts.append(str(context[value]))
            else:
                raise ValueError(
                    f"Template compilation error: name '{value}' is not defined"
                )
        return ''.join(parts)

    def render(self, template_str, context=None):
        if context is None:
            context = {}
        cache_key = hashlib.md5(template_str.encode()).hexdigest()
        if cache_key not in self.template_cache:
            self.template_cache[cache_key] = self._compile_template(template_str)
        return self._apply_context(self.template_cache[cache_key], context)


class TemplateAPI(View):
    renderer = DynamicTemplateRenderer()

    def post(self, request):
        try:
            data = json.loads(request.body)
            template = data.get('template')
            context = data.get('context', {})
            if not template:
                return JsonResponse({'error': 'Template required'}, status=400)
            rendered = self.renderer.render(template, context)
            return HttpResponse(rendered)
        except ValueError as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception:
            return JsonResponse({'error': 'Internal server error'}, status=500)


class ConfigManager:
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
            new_config = ast.literal_eval(config_str)
            if isinstance(new_config, dict):
                self.config.update(new_config)
                return True
            return False
        except Exception as e:
            print(f'Config update failed: {str(e)}')
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
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class AuditLogger:

    @staticmethod
    def log(event, details):
        timestamp = datetime.datetime.now().isoformat()
        log_entry = f'[{timestamp}] {event}: {details}'
        with open(AUDIT_LOG_PATH, 'a') as f:
            f.write(log_entry + '\n')


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
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
