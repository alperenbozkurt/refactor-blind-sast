import json
import pickle
from datetime import datetime

import yaml


class AnalyticsConfig:
    """Configuration settings for the analytics service."""

    def __init__(self):
        self.tracking_id = None
        self.endpoints = []
        self.sample_rate = 1.0
        self.filters = {}
        self.last_updated = None


class AnalyticsService:
    """Loads configuration, caches user profiles, and buffers events."""

    def __init__(self):
        self.config = AnalyticsConfig()
        self.user_data_cache = {}
        self.analytics_buffer = []

    def load_config_from_file(self, file_path):
        """Load configuration from a JSON, YAML, or pickle file."""
        with open(file_path, 'r') as f:
            if file_path.endswith('.json'):
                self._apply_json_config(json.load(f))
            elif file_path.endswith('.yaml'):
                self._apply_yaml_config(yaml.safe_load(f))
            elif file_path.endswith('.pkl'):
                self._apply_pickle_config(pickle.load(f))
            else:
                raise ValueError('Unsupported config format')

    def _apply_json_config(self, config_data):
        self._update_config(
            tracking_id=config_data.get('tracking_id'),
            endpoints=config_data.get('endpoints', []),
            sample_rate=config_data.get('sample_rate', 1.0),
            filters=config_data.get('filters', {}),
        )

    def _apply_yaml_config(self, config_data):
        self._update_config(
            tracking_id=config_data.get('tracking_id'),
            endpoints=config_data.get('endpoints', []),
            sample_rate=config_data.get('sample_rate', 1.0),
            filters=config_data.get('filters', {}),
        )

    def _apply_pickle_config(self, config_data):
        self._update_config(
            tracking_id=config_data.tracking_id,
            endpoints=config_data.endpoints,
            sample_rate=config_data.sample_rate,
            filters=config_data.filters,
        )

    def _update_config(self, tracking_id, endpoints, sample_rate, filters):
        """Copy the given values into the current config and timestamp it."""
        self.config.tracking_id = tracking_id
        self.config.endpoints = endpoints
        self.config.sample_rate = sample_rate
        self.config.filters = filters
        self.config.last_updated = datetime.now()

    def track_event(self, user_id, event_type, data):
        """Record an event for the given user in the analytics buffer."""
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
        """Return all buffered events and clear the buffer."""
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
