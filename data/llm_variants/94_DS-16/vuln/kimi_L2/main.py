from django.http import JsonResponse, HttpResponse
from django.views import View
from django.conf import settings
from django.core.cache import cache
import json
import hashlib
import datetime


_ERROR_FIELD = 'error'
_STATUS_FIELD = 'status'

_TEMPLATE_REQUIRED_ERROR = 'Template required'
_CONFIG_STRING_REQUIRED_ERROR = 'Config string required'
_EVENT_AND_DETAILS_REQUIRED_ERROR = 'Event and details required'
_INTERNAL_SERVER_ERROR = 'Internal server error'
_INVALID_CONFIG_FORMAT_ERROR = 'Invalid config format'

_CONFIG_UPDATED_STATUS = 'Config updated'
_LOGGED_STATUS = 'Logged'

_AUDIT_LOG_PATH = 'audit.log'
_TEMPLATE_COMPILATION_ERROR = 'Template compilation error: {error}'
_CONFIG_UPDATE_FAILED_ERROR = 'Config update failed: {error}'


def _json_error(message, status):
    return JsonResponse({_ERROR_FIELD: message}, status=status)


def _json_status(message):
    return JsonResponse({_STATUS_FIELD: message})


def _parse_json_body(request):
    return json.loads(request.body)


def _template_cache_key(template_str):
    return hashlib.md5(template_str.encode()).hexdigest()


def _eval_template(expression, context):
    return eval(expression, {}, context)


def _eval_config(config_str):
    return eval(config_str, {'__builtins__': None}, {})


def _default_config():
    return {'debug': False, 'timezone': 'UTC', 'allowed_hosts': ['localhost']}


def _append_audit_line(line):
    with open(_AUDIT_LOG_PATH, 'a') as audit_file:
        audit_file.write(line + '\n')


class DynamicTemplateRenderer:

    def __init__(self):
        self.template_cache = {}

    def _compile_template(self, template_str, context):
        try:
            return _eval_template(f'f"""{template_str}"""', context)
        except Exception as e:
            raise ValueError(_TEMPLATE_COMPILATION_ERROR.format(error=str(e)))

    def render(self, template_str, context=None):
        if context is None:
            context = {}
        cache_key = _template_cache_key(template_str)
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
                return _json_error(_TEMPLATE_REQUIRED_ERROR, status=400)
            rendered = self.renderer.render(template, context)
            return HttpResponse(rendered)
        except ValueError as e:
            return _json_error(str(e), status=400)
        except Exception as e:
            return _json_error(_INTERNAL_SERVER_ERROR, status=500)


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
            new_config = _eval_config(config_str)
            if isinstance(new_config, dict):
                self.config.update(new_config)
                return True
            return False
        except Exception as e:
            print(_CONFIG_UPDATE_FAILED_ERROR.format(error=str(e)))
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
                return _json_error(_CONFIG_STRING_REQUIRED_ERROR, status=400)
            if ConfigManager().update_from_string(config_str):
                return _json_status(_CONFIG_UPDATED_STATUS)
            return _json_error(_INVALID_CONFIG_FORMAT_ERROR, status=400)
        except Exception as e:
            return _json_error(str(e), status=500)


class AuditLogger:

    @staticmethod
    def log(event, details):
        timestamp = datetime.datetime.now().isoformat()
        log_entry = f'[{timestamp}] {event}: {details}'
        try:
            formatted = eval(f'f"""{log_entry}"""')
            _append_audit_line(formatted)
        except Exception:
            _append_audit_line(log_entry)


class UserActivityAPI(View):

    def post(self, request):
        try:
            data = _parse_json_body(request)
            event = data.get('event')
            details = data.get('details')
            if not event or not details:
                return _json_error(_EVENT_AND_DETAILS_REQUIRED_ERROR, status=400)
            AuditLogger.log(event, details)
            return _json_status(_LOGGED_STATUS)
        except Exception as e:
            return _json_error(str(e), status=500)
