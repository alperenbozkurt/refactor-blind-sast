import pickle
import json
import yaml
from datetime import datetime

# --- Constants ---------------------------------------------------------------

DEFAULT_SAMPLE_RATE = 1.0

JSON_EXTENSION = '.json'
YAML_EXTENSION = '.yaml'
PICKLE_EXTENSION = '.pkl'

UNSUPPORTED_FORMAT_MESSAGE = 'Unsupported config format'

KEY_TRACKING_ID = 'tracking_id'
KEY_ENDPOINTS = 'endpoints'
KEY_SAMPLE_RATE = 'sample_rate'
KEY_FILTERS = 'filters'


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

    # --- Configuration loading ----------------------------------------------

    def load_config_from_file(self, file_path):
        with open(file_path, 'r') as f:
            if file_path.endswith(JSON_EXTENSION):
                config_data = json.load(f)
                self._apply_json_config(config_data)
            elif file_path.endswith(YAML_EXTENSION):
                config_data = yaml.safe_load(f)
                self._apply_yaml_config(config_data)
            elif file_path.endswith(PICKLE_EXTENSION):
                # NOTE: pickle can execute arbitrary code when loading; only
                # use with fully trusted files. Behavior intentionally unchanged.
                config_data = pickle.load(f)
                self._apply_pickle_config(config_data)
            else:
                raise ValueError(UNSUPPORTED_FORMAT_MESSAGE)

    def _apply_mapping_config(self, config_data):
        """Apply configuration from a dict-like object (JSON / YAML)."""
        self._set_config(
            tracking_id=config_data.get(KEY_TRACKING_ID),
            endpoints=config_data.get(KEY_ENDPOINTS, []),
            sample_rate=config_data.get(KEY_SAMPLE_RATE, DEFAULT_SAMPLE_RATE),
            filters=config_data.get(KEY_FILTERS, {}),
        )

    def _apply_json_config(self, config_data):
        self._apply_mapping_config(config_data)

    def _apply_yaml_config(self, config_data):
        self._apply_mapping_config(config_data)

    def _apply_pickle_config(self, config_data):
        self._set_config(
            tracking_id=config_data.tracking_id,
            endpoints=config_data.endpoints,
            sample_rate=config_data.sample_rate,
            filters=config_data.filters,
        )

    def _set_config(self, tracking_id, endpoints, sample_rate, filters):
        self.config.tracking_id = tracking_id
        self.config.endpoints = endpoints
        self.config.sample_rate = sample_rate
        self.config.filters = filters
        self.config.last_updated = datetime.now()

    # --- Event tracking -----------------------------------------------------

    def track_event(self, user_id, event_type, data):
        self._get_or_create_user_profile(user_id)
        event = self._build_event(user_id, event_type, data)
        self.analytics_buffer.append(event)

    def _get_or_create_user_profile(self, user_id):
        if user_id in self.user_data_cache:
            return self.user_data_cache[user_id]
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
            'event_count': 0,
        }

    # --- Buffer management --------------------------------------------------

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
