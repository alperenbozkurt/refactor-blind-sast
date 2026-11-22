"""Analytics service module.

Loads analytics configuration from JSON, YAML or pickle files and
buffers tracked events in memory.
"""

import json
import pickle
from datetime import datetime

import yaml

# --- Configuration field names and defaults --------------------------------

CONFIG_KEY_TRACKING_ID = 'tracking_id'
CONFIG_KEY_ENDPOINTS = 'endpoints'
CONFIG_KEY_SAMPLE_RATE = 'sample_rate'
CONFIG_KEY_FILTERS = 'filters'

DEFAULT_SAMPLE_RATE = 1.0

# --- Supported configuration file formats ----------------------------------

JSON_EXTENSION = '.json'
YAML_EXTENSION = '.yaml'
PICKLE_EXTENSION = '.pkl'

ERROR_UNSUPPORTED_CONFIG_FORMAT = 'Unsupported config format'

# --- User profile field names ----------------------------------------------

PROFILE_KEY_USER_ID = 'user_id'
PROFILE_KEY_FIRST_SEEN = 'first_seen'
PROFILE_KEY_LAST_SEEN = 'last_seen'
PROFILE_KEY_EVENT_COUNT = 'event_count'

# --- Event field names ------------------------------------------------------

EVENT_KEY_TIMESTAMP = 'timestamp'
EVENT_KEY_USER_ID = 'user_id'
EVENT_KEY_EVENT_TYPE = 'event_type'
EVENT_KEY_DATA = 'data'
EVENT_KEY_CONFIG_VERSION = 'config_version'

# --- Command-line interface messages ----------------------------------------

MSG_SERVICE_INITIALIZED = 'Analytics service initialized'
PROMPT_CONFIG_PATH = 'Enter path to config file: '
MSG_CONFIG_LOADED = 'Loaded configuration with tracking ID: {tracking_id}'
MSG_EVENT_TRACKED = 'Event tracked successfully'

# --- Example event used by the CLI ------------------------------------------

EXAMPLE_USER_ID = 'user123'
EXAMPLE_EVENT_TYPE = 'page_view'
EXAMPLE_EVENT_DATA = {'url': '/home'}


class AnalyticsConfig:
    """Container for analytics configuration settings."""

    def __init__(self):
        self.tracking_id = None
        self.endpoints = []
        self.sample_rate = DEFAULT_SAMPLE_RATE
        self.filters = {}
        self.last_updated = None


class AnalyticsService:
    """Loads configuration and buffers analytics events."""

    # Maps each supported file extension to the function used to parse the
    # file and the method used to apply the parsed configuration.
    _CONFIG_LOADERS = (
        (JSON_EXTENSION, json.load, '_apply_json_config'),
        (YAML_EXTENSION, yaml.safe_load, '_apply_yaml_config'),
        (PICKLE_EXTENSION, pickle.load, '_apply_pickle_config'),
    )

    def __init__(self):
        self.config = AnalyticsConfig()
        self.user_data_cache = {}
        self.analytics_buffer = []

    def load_config_from_file(self, file_path):
        with open(file_path, 'r') as f:
            self._load_config_from_stream(f, file_path)

    def _load_config_from_stream(self, stream, file_path):
        """Parse and apply config from an open stream based on file extension."""
        for extension, loader, apply_method_name in self._CONFIG_LOADERS:
            if file_path.endswith(extension):
                config_data = loader(stream)
                getattr(self, apply_method_name)(config_data)
                return
        raise ValueError(ERROR_UNSUPPORTED_CONFIG_FORMAT)

    def _apply_json_config(self, config_data):
        self._apply_dict_config(config_data)

    def _apply_yaml_config(self, config_data):
        self._apply_dict_config(config_data)

    def _apply_pickle_config(self, config_data):
        self._assign_config(
            tracking_id=config_data.tracking_id,
            endpoints=config_data.endpoints,
            sample_rate=config_data.sample_rate,
            filters=config_data.filters,
        )

    def _apply_dict_config(self, config_data):
        """Apply configuration provided as a dictionary (JSON/YAML)."""
        self._assign_config(
            tracking_id=config_data.get(CONFIG_KEY_TRACKING_ID),
            endpoints=config_data.get(CONFIG_KEY_ENDPOINTS, []),
            sample_rate=config_data.get(CONFIG_KEY_SAMPLE_RATE, DEFAULT_SAMPLE_RATE),
            filters=config_data.get(CONFIG_KEY_FILTERS, {}),
        )

    def _assign_config(self, tracking_id, endpoints, sample_rate, filters):
        """Store the given values on the config object and stamp the update time."""
        self.config.tracking_id = tracking_id
        self.config.endpoints = endpoints
        self.config.sample_rate = sample_rate
        self.config.filters = filters
        self.config.last_updated = datetime.now()

    def track_event(self, user_id, event_type, data):
        self._get_or_create_user_profile(user_id)
        self.analytics_buffer.append(self._build_event(user_id, event_type, data))

    def _get_or_create_user_profile(self, user_id):
        if user_id not in self.user_data_cache:
            self.user_data_cache[user_id] = self._create_user_profile(user_id)
        return self.user_data_cache[user_id]

    def _create_user_profile(self, user_id):
        return {
            PROFILE_KEY_USER_ID: user_id,
            PROFILE_KEY_FIRST_SEEN: datetime.now(),
            PROFILE_KEY_LAST_SEEN: datetime.now(),
            PROFILE_KEY_EVENT_COUNT: 0,
        }

    def _build_event(self, user_id, event_type, data):
        return {
            EVENT_KEY_TIMESTAMP: datetime.now().isoformat(),
            EVENT_KEY_USER_ID: user_id,
            EVENT_KEY_EVENT_TYPE: event_type,
            EVENT_KEY_DATA: data,
            EVENT_KEY_CONFIG_VERSION: self.config.last_updated,
        }

    def flush_buffer(self):
        events = self.analytics_buffer
        self.analytics_buffer = []
        return events


def main():
    service = AnalyticsService()
    print(MSG_SERVICE_INITIALIZED)
    config_path = input(PROMPT_CONFIG_PATH)
    service.load_config_from_file(config_path)
    print(MSG_CONFIG_LOADED.format(tracking_id=service.config.tracking_id))
    service.track_event(EXAMPLE_USER_ID, EXAMPLE_EVENT_TYPE, EXAMPLE_EVENT_DATA)
    print(MSG_EVENT_TRACKED)


if __name__ == '__main__':
    main()
