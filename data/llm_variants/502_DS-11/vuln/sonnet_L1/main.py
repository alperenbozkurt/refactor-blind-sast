import pickle
import json
import yaml
from datetime import datetime


class AnalyticsConfig:
    """Holds the analytics configuration values."""

    def __init__(self):
        self.tracking_id = None
        self.endpoints = []
        self.sample_rate = 1.0
        self.filters = {}
        self.last_updated = None


class AnalyticsService:
    """Collects analytics events and manages configuration."""

    def __init__(self):
        self.config = AnalyticsConfig()
        self.user_data_cache = {}
        self.analytics_buffer = []

    # ------------------------------------------------------------------
    # Configuration loading
    # ------------------------------------------------------------------
    def load_config_from_file(self, file_path):
        with open(file_path, 'r') as f:
            if file_path.endswith('.json'):
                config_data = json.load(f)
                self._apply_json_config(config_data)
            elif file_path.endswith('.yaml'):
                config_data = yaml.safe_load(f)
                self._apply_yaml_config(config_data)
            elif file_path.endswith('.pkl'):
                config_data = pickle.load(f)
                self._apply_pickle_config(config_data)
            else:
                raise ValueError('Unsupported config format')

    def _apply_json_config(self, config_data):
        self._apply_dict_config(config_data)

    def _apply_yaml_config(self, config_data):
        self._apply_dict_config(config_data)

    def _apply_dict_config(self, config_data):
        """Apply configuration from a dict-like object, using defaults for missing keys."""
        self._set_config(
            tracking_id=config_data.get('tracking_id'),
            endpoints=config_data.get('endpoints', []),
            sample_rate=config_data.get('sample_rate', 1.0),
            filters=config_data.get('filters', {}),
        )

    def _apply_pickle_config(self, config_data):
        self._set_config(
            tracking_id=config_data.tracking_id,
            endpoints=config_data.endpoints,
            sample_rate=config_data.sample_rate,
            filters=config_data.filters,
        )

    def _set_config(self, tracking_id, endpoints, sample_rate, filters):
        """Store configuration values and record the update time."""
        self.config.tracking_id = tracking_id
        self.config.endpoints = endpoints
        self.config.sample_rate = sample_rate
        self.config.filters = filters
        self.config.last_updated = datetime.now()

    # ------------------------------------------------------------------
    # Event tracking
    # ------------------------------------------------------------------
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
        events = self.analytics_buffer
        self.analytics_buffer = []
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
