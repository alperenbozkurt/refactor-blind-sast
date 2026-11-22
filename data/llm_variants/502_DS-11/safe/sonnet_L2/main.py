import json
import yaml
from datetime import datetime

JSON_EXTENSIONS = ('.json',)
YAML_EXTENSIONS = ('.yaml', '.yml')
SUPPORTED_EXTENSIONS = JSON_EXTENSIONS + YAML_EXTENSIONS

DEFAULT_SAMPLE_RATE = 1.0
MIN_SAMPLE_RATE = 0.0
MAX_SAMPLE_RATE = 1.0

UNSUPPORTED_FORMAT_MESSAGE = 'Unsupported config format. Only JSON and YAML are supported.'
UNSUPPORTED_CLI_FORMAT_MESSAGE = 'Only .json and .yaml/.yml files are supported'

DEMO_USER_ID = 'user123'
DEMO_EVENT_TYPE = 'page_view'
DEMO_EVENT_DATA = {'url': '/home'}


def _clamp_sample_rate(value):
    """Convert a raw sample rate to float and clamp it to the valid range."""
    return min(MAX_SAMPLE_RATE, max(MIN_SAMPLE_RATE, float(value)))


def _has_extension(path, extensions):
    return path.endswith(extensions)


class AnalyticsConfig:

    def __init__(self):
        self.tracking_id = None
        self.endpoints = []
        self.sample_rate = DEFAULT_SAMPLE_RATE
        self.filters = {}
        self.last_updated = None


class AnalyticsService:

    def __init__(self):
        self.config = AnalyticsConfig()
        self.user_data_cache = {}
        self.analytics_buffer = []

    # ------------------------------------------------------------------
    # Configuration handling
    # ------------------------------------------------------------------
    def load_config_from_file(self, file_path):
        with open(file_path, 'r') as f:
            if _has_extension(file_path, JSON_EXTENSIONS):
                config_data = json.load(f)
                self._apply_json_config(config_data)
            elif _has_extension(file_path, YAML_EXTENSIONS):
                config_data = yaml.safe_load(f)
                self._apply_yaml_config(config_data)
            else:
                raise ValueError(UNSUPPORTED_FORMAT_MESSAGE)

    def _apply_json_config(self, config_data):
        self._apply_config_data(config_data)

    def _apply_yaml_config(self, config_data):
        self._apply_config_data(config_data)

    def _apply_config_data(self, config_data):
        self._validate_config_data(config_data)
        self.config.tracking_id = config_data.get('tracking_id')
        self.config.endpoints = config_data.get('endpoints', [])
        self.config.sample_rate = _clamp_sample_rate(
            config_data.get('sample_rate', DEFAULT_SAMPLE_RATE))
        self.config.filters = config_data.get('filters', {})
        self.config.last_updated = datetime.now()

    def _validate_config_data(self, config_data):
        if not isinstance(config_data, dict):
            raise ValueError('Configuration data must be a dictionary')
        if 'tracking_id' not in config_data:
            raise ValueError('Configuration must include a tracking_id')
        if 'endpoints' in config_data and (not isinstance(config_data['endpoints'], list)):
            raise ValueError('Endpoints must be a list')
        if 'filters' in config_data and (not isinstance(config_data['filters'], dict)):
            raise ValueError('Filters must be a dictionary')

    # ------------------------------------------------------------------
    # Event tracking
    # ------------------------------------------------------------------
    def track_event(self, user_id, event_type, data):
        self._validate_event_input(user_id, event_type, data)
        self._update_user_profile(user_id)
        event = self._build_event(user_id, event_type, data)
        self.analytics_buffer.append(event)

    @staticmethod
    def _validate_event_input(user_id, event_type, data):
        if not isinstance(user_id, str) or not user_id:
            raise ValueError('Invalid user_id')
        if not isinstance(event_type, str) or not event_type:
            raise ValueError('Invalid event_type')
        if not isinstance(data, dict):
            raise ValueError('Event data must be a dictionary')

    def _update_user_profile(self, user_id):
        if user_id in self.user_data_cache:
            user_profile = self.user_data_cache[user_id]
            user_profile['last_seen'] = datetime.now()
            user_profile['event_count'] += 1
        else:
            user_profile = self._create_user_profile(user_id)
            self.user_data_cache[user_id] = user_profile
        return user_profile

    def _build_event(self, user_id, event_type, data):
        return {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'event_type': event_type,
            'data': data,
            'config_version': self.config.last_updated,
        }

    def _create_user_profile(self, user_id):
        return {
            'user_id': user_id,
            'first_seen': datetime.now(),
            'last_seen': datetime.now(),
            'event_count': 1,
        }

    def flush_buffer(self):
        events = self.analytics_buffer
        self.analytics_buffer = []
        return events


def _prompt_config_path():
    config_path = input('Enter path to config file: ').strip()
    if not config_path:
        raise ValueError('No config file path provided')
    if not _has_extension(config_path, SUPPORTED_EXTENSIONS):
        raise ValueError(UNSUPPORTED_CLI_FORMAT_MESSAGE)
    return config_path


def main():
    service = AnalyticsService()
    print('Analytics service initialized')
    try:
        config_path = _prompt_config_path()
        service.load_config_from_file(config_path)
        print(f'Loaded configuration with tracking ID: {service.config.tracking_id}')
        service.track_event(DEMO_USER_ID, DEMO_EVENT_TYPE, {'url': DEMO_EVENT_DATA['url']})
        print('Event tracked successfully')
    except Exception as e:
        print(f'Error: {e}')


if __name__ == '__main__':
    main()
