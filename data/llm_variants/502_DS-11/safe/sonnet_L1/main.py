import json
import yaml
from datetime import datetime

_JSON_EXTENSIONS = ('.json',)
_YAML_EXTENSIONS = ('.yaml', '.yml')


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
            if file_path.endswith(_JSON_EXTENSIONS):
                config_data = json.load(f)
                self._apply_json_config(config_data)
            elif file_path.endswith(_YAML_EXTENSIONS):
                config_data = yaml.safe_load(f)
                self._apply_yaml_config(config_data)
            else:
                raise ValueError('Unsupported config format. Only JSON and YAML are supported.')

    def _apply_json_config(self, config_data):
        self._apply_config(config_data)

    def _apply_yaml_config(self, config_data):
        self._apply_config(config_data)

    def _apply_config(self, config_data):
        self._validate_config_data(config_data)
        self.config.tracking_id = config_data.get('tracking_id')
        self.config.endpoints = config_data.get('endpoints', [])
        self.config.sample_rate = self._clamp_sample_rate(config_data.get('sample_rate', 1.0))
        self.config.filters = config_data.get('filters', {})
        self.config.last_updated = datetime.now()

    @staticmethod
    def _clamp_sample_rate(value):
        return min(1.0, max(0.0, float(value)))

    def _validate_config_data(self, config_data):
        if not isinstance(config_data, dict):
            raise ValueError('Configuration data must be a dictionary')
        if 'tracking_id' not in config_data:
            raise ValueError('Configuration must include a tracking_id')
        if 'endpoints' in config_data and not isinstance(config_data['endpoints'], list):
            raise ValueError('Endpoints must be a list')
        if 'filters' in config_data and not isinstance(config_data['filters'], dict):
            raise ValueError('Filters must be a dictionary')

    def track_event(self, user_id, event_type, data):
        self._validate_event(user_id, event_type, data)
        self._update_user_profile(user_id)
        event = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'event_type': event_type,
            'data': data,
            'config_version': self.config.last_updated,
        }
        self.analytics_buffer.append(event)

    @staticmethod
    def _validate_event(user_id, event_type, data):
        if not isinstance(user_id, str) or not user_id:
            raise ValueError('Invalid user_id')
        if not isinstance(event_type, str) or not event_type:
            raise ValueError('Invalid event_type')
        if not isinstance(data, dict):
            raise ValueError('Event data must be a dictionary')

    def _update_user_profile(self, user_id):
        user_profile = self.user_data_cache.get(user_id)
        if user_profile is not None:
            user_profile['last_seen'] = datetime.now()
            user_profile['event_count'] += 1
        else:
            self.user_data_cache[user_id] = self._create_user_profile(user_id)

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


def main():
    service = AnalyticsService()
    print('Analytics service initialized')
    try:
        config_path = input('Enter path to config file: ').strip()
        if not config_path:
            raise ValueError('No config file path provided')
        if not config_path.endswith(_JSON_EXTENSIONS + _YAML_EXTENSIONS):
            raise ValueError('Only .json and .yaml/.yml files are supported')
        service.load_config_from_file(config_path)
        print(f'Loaded configuration with tracking ID: {service.config.tracking_id}')
        service.track_event('user123', 'page_view', {'url': '/home'})
        print('Event tracked successfully')
    except Exception as e:
        print(f'Error: {e}')


if __name__ == '__main__':
    main()
