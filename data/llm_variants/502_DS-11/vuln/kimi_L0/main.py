import pickle
import json
import yaml
from datetime import datetime


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
        handlers = (
            ('.json', json.load, self._apply_json_config),
            ('.yaml', yaml.safe_load, self._apply_yaml_config),
            ('.pkl', pickle.load, self._apply_pickle_config),
        )
        with open(file_path, 'r') as f:
            for extension, loader, apply_config in handlers:
                if file_path.endswith(extension):
                    apply_config(loader(f))
                    return
            raise ValueError('Unsupported config format')

    def _apply_json_config(self, config_data):
        self._apply_mapping_config(config_data)

    def _apply_yaml_config(self, config_data):
        self._apply_mapping_config(config_data)

    def _apply_mapping_config(self, config_data):
        self.config.tracking_id = config_data.get('tracking_id')
        self.config.endpoints = config_data.get('endpoints', [])
        self.config.sample_rate = config_data.get('sample_rate', 1.0)
        self.config.filters = config_data.get('filters', {})
        self.config.last_updated = datetime.now()

    def _apply_pickle_config(self, config_data):
        self.config.tracking_id = config_data.tracking_id
        self.config.endpoints = config_data.endpoints
        self.config.sample_rate = config_data.sample_rate
        self.config.filters = config_data.filters
        self.config.last_updated = datetime.now()

    def track_event(self, user_id, event_type, data):
        if user_id not in self.user_data_cache:
            self.user_data_cache[user_id] = self._create_user_profile(user_id)
        event = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'event_type': event_type,
            'data': data,
            'config_version': self.config.last_updated,
        }
        self.analytics_buffer.append(event)

    def _create_user_profile(self, user_id):
        return {
            'user_id': user_id,
            'first_seen': datetime.now(),
            'last_seen': datetime.now(),
            'event_count': 0,
        }

    def flush_buffer(self):
        events, self.analytics_buffer = self.analytics_buffer, []
        return events


def main():
    service = AnalyticsService()
    print('Analytics service initialized')
    config_path = input('Enter path to config file: ')
    service.load_config_from_file(config_path)
    print(f'Loaded configuration with tracking ID: {service.config.tracking_id}')
    service.track_event('user123', 'page_view', {'url': '/home'})
    print('Event tracked successfully')


if __name__ == '__main__':
    main()
