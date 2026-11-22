import json
import yaml
from datetime import datetime

_JSON_CONFIG_EXTENSION = '.json'
_YAML_CONFIG_EXTENSION = '.yaml'
_YML_CONFIG_EXTENSION = '.yml'

_DEFAULT_SAMPLE_RATE = 1.0
_MIN_SAMPLE_RATE = 0.0
_MAX_SAMPLE_RATE = 1.0

_UNSUPPORTED_CONFIG_FORMAT_MESSAGE = 'Unsupported config format. Only JSON and YAML are supported.'
_CONFIG_DATA_MUST_BE_DICT_MESSAGE = 'Configuration data must be a dictionary'
_TRACKING_ID_REQUIRED_MESSAGE = 'Configuration must include a tracking_id'
_ENDPOINTS_MUST_BE_LIST_MESSAGE = 'Endpoints must be a list'
_FILTERS_MUST_BE_DICT_MESSAGE = 'Filters must be a dictionary'

_INVALID_USER_ID_MESSAGE = 'Invalid user_id'
_INVALID_EVENT_TYPE_MESSAGE = 'Invalid event_type'
_INVALID_EVENT_DATA_MESSAGE = 'Event data must be a dictionary'

_SERVICE_INITIALIZED_MESSAGE = 'Analytics service initialized'
_CONFIG_PATH_PROMPT = 'Enter path to config file: '
_NO_CONFIG_PATH_MESSAGE = 'No config file path provided'
_UNSUPPORTED_CLI_EXTENSION_MESSAGE = 'Only .json and .yaml/.yml files are supported'
_EVENT_TRACKED_MESSAGE = 'Event tracked successfully'

_EXAMPLE_USER_ID = 'user123'
_EXAMPLE_EVENT_TYPE = 'page_view'
_EXAMPLE_EVENT_URL = '/home'


def _is_json_config_path(file_path):
    return file_path.endswith(_JSON_CONFIG_EXTENSION)


def _is_yaml_config_path(file_path):
    return file_path.endswith(_YAML_CONFIG_EXTENSION) or file_path.endswith(_YML_CONFIG_EXTENSION)


def _is_supported_config_path(file_path):
    return _is_json_config_path(file_path) or _is_yaml_config_path(file_path)


def _clamp_sample_rate(sample_rate):
    return min(_MAX_SAMPLE_RATE, max(_MIN_SAMPLE_RATE, float(sample_rate)))


def _prompt_for_config_path():
    return input(_CONFIG_PATH_PROMPT).strip()


def _validate_cli_config_path(config_path):
    if not config_path:
        raise ValueError(_NO_CONFIG_PATH_MESSAGE)
    if not _is_supported_config_path(config_path):
        raise ValueError(_UNSUPPORTED_CLI_EXTENSION_MESSAGE)


class AnalyticsConfig:

    def __init__(self):
        self.tracking_id = None
        self.endpoints = []
        self.sample_rate = 1.0
        self.filters = {}
        self.last_updated = None

class AnalyticsService:

    def __init__(self):
        self.config = AnalyticsConfig()
        self.user_data_cache = {}
        self.analytics_buffer = []

    def load_config_from_file(self, file_path):
        with open(file_path, 'r') as f:
            if _is_json_config_path(file_path):
                config_data = json.load(f)
                self._apply_json_config(config_data)
            elif _is_yaml_config_path(file_path):
                config_data = yaml.safe_load(f)
                self._apply_yaml_config(config_data)
            else:
                raise ValueError(_UNSUPPORTED_CONFIG_FORMAT_MESSAGE)

    def _apply_json_config(self, config_data):
        self._apply_config_data(config_data)

    def _apply_yaml_config(self, config_data):
        self._apply_config_data(config_data)

    def _apply_config_data(self, config_data):
        self._validate_config_data(config_data)
        self.config.tracking_id = config_data.get('tracking_id')
        self.config.endpoints = config_data.get('endpoints', [])
        self.config.sample_rate = _clamp_sample_rate(config_data.get('sample_rate', _DEFAULT_SAMPLE_RATE))
        self.config.filters = config_data.get('filters', {})
        self.config.last_updated = datetime.now()

    def _validate_config_data(self, config_data):
        if not isinstance(config_data, dict):
            raise ValueError(_CONFIG_DATA_MUST_BE_DICT_MESSAGE)
        if 'tracking_id' not in config_data:
            raise ValueError(_TRACKING_ID_REQUIRED_MESSAGE)
        if 'endpoints' in config_data and (not isinstance(config_data['endpoints'], list)):
            raise ValueError(_ENDPOINTS_MUST_BE_LIST_MESSAGE)
        if 'filters' in config_data and (not isinstance(config_data['filters'], dict)):
            raise ValueError(_FILTERS_MUST_BE_DICT_MESSAGE)

    def track_event(self, user_id, event_type, data):
        self._validate_event_input(user_id, event_type, data)
        self._record_user_activity(user_id)
        event = self._build_event(user_id, event_type, data)
        self.analytics_buffer.append(event)

    def _validate_event_input(self, user_id, event_type, data):
        if not isinstance(user_id, str) or not user_id:
            raise ValueError(_INVALID_USER_ID_MESSAGE)
        if not isinstance(event_type, str) or not event_type:
            raise ValueError(_INVALID_EVENT_TYPE_MESSAGE)
        if not isinstance(data, dict):
            raise ValueError(_INVALID_EVENT_DATA_MESSAGE)

    def _record_user_activity(self, user_id):
        if user_id in self.user_data_cache:
            user_profile = self.user_data_cache[user_id]
            user_profile['last_seen'] = datetime.now()
            user_profile['event_count'] += 1
            return user_profile
        user_profile = self._create_user_profile(user_id)
        self.user_data_cache[user_id] = user_profile
        return user_profile

    def _build_event(self, user_id, event_type, data):
        return {'timestamp': datetime.now().isoformat(), 'user_id': user_id, 'event_type': event_type, 'data': data, 'config_version': self.config.last_updated}

    def _create_user_profile(self, user_id):
        return {'user_id': user_id, 'first_seen': datetime.now(), 'last_seen': datetime.now(), 'event_count': 1}

    def flush_buffer(self):
        events = self.analytics_buffer
        self.analytics_buffer = []
        return events

def main():
    service = AnalyticsService()
    print(_SERVICE_INITIALIZED_MESSAGE)
    try:
        config_path = _prompt_for_config_path()
        _validate_cli_config_path(config_path)
        service.load_config_from_file(config_path)
        print(f'Loaded configuration with tracking ID: {service.config.tracking_id}')
        service.track_event(_EXAMPLE_USER_ID, _EXAMPLE_EVENT_TYPE, {'url': _EXAMPLE_EVENT_URL})
        print(_EVENT_TRACKED_MESSAGE)
    except Exception as e:
        print(f'Error: {e}')
if __name__ == '__main__':
    main()
