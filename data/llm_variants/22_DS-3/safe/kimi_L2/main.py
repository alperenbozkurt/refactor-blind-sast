"""Flask-based configuration file management service.

Exposes a small REST API for creating, retrieving and listing
configuration files stored under ``CONFIG_BASE_DIR``.
"""

import json
import os

import yaml
from flask import Flask, jsonify, request

# ---------------------------------------------------------------------------
# Filesystem / format constants
# ---------------------------------------------------------------------------

CONFIG_BASE_DIR = '/etc/app_configs'

JSON_FORMAT = 'json'
YAML_FORMAT = 'yaml'
DEFAULT_FORMAT = JSON_FORMAT

JSON_EXTENSION = '.json'
YAML_EXTENSIONS = ('.yaml', '.yml')
SUPPORTED_EXTENSIONS = (JSON_EXTENSION,) + YAML_EXTENSIONS

ALLOWED_NAME_SPECIAL_CHARS = ('-', '_')

# ---------------------------------------------------------------------------
# API constants
# ---------------------------------------------------------------------------

ROUTE_CREATE_CONFIG = '/api/config'
ROUTE_GET_CONFIG = '/api/config/<path:config_path>'
ROUTE_LIST_CONFIGS = '/api/configs'

HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500

MSG_CONFIG_SAVED = 'Config saved successfully'
ERR_MISSING_FIELDS = 'Missing required fields'
ERR_SAVE_FAILED = 'Failed to save config'
ERR_CONFIG_NOT_FOUND = 'Config not found or invalid'

# ---------------------------------------------------------------------------
# Server settings
# ---------------------------------------------------------------------------

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
DEBUG_MODE = False

app = Flask(__name__)


def _is_allowed_name_char(char):
    """Return True if *char* may appear in a configuration name."""
    return char.isalnum() or char in ALLOWED_NAME_SPECIAL_CHARS


def _has_supported_extension(path):
    """Return True if *path* ends with a supported config file extension."""
    return path.endswith(SUPPORTED_EXTENSIONS)


def _error_response(message, status_code):
    """Build a JSON error response tuple."""
    return jsonify({'error': message}), status_code


class ConfigManager:
    """Create, read and list configuration files stored on disk."""

    def __init__(self):
        self.config_cache = {}
        os.makedirs(CONFIG_BASE_DIR, exist_ok=True)

    # -- validation --------------------------------------------------------

    def validate_config_name(self, config_name):
        return bool(config_name) and all(
            _is_allowed_name_char(c) for c in config_name
        )

    def validate_config_path(self, config_path):
        base_dir = os.path.abspath(CONFIG_BASE_DIR)
        abs_path = os.path.abspath(os.path.join(base_dir, config_path))
        if not abs_path.startswith(base_dir):
            return False
        if not _has_supported_extension(abs_path):
            return False
        return True

    # -- persistence -------------------------------------------------------

    def save_config(self, config_name, config_data, format_type=DEFAULT_FORMAT):
        if not self.validate_config_name(config_name):
            return False
        config_path = os.path.join(
            CONFIG_BASE_DIR, f'{config_name}.{format_type}'
        )
        try:
            with open(config_path, 'w') as config_file:
                return self._dump_config(config_file, config_data, format_type)
        except Exception:
            return False

    def load_config(self, config_path):
        try:
            if not self.validate_config_path(config_path):
                return None
            full_path = os.path.abspath(
                os.path.join(CONFIG_BASE_DIR, config_path)
            )
            with open(full_path, 'r') as config_file:
                return self._load_serialized_config(config_file, full_path)
        except Exception:
            return None

    def list_configs(self):
        return [
            filename
            for filename in os.listdir(CONFIG_BASE_DIR)
            if _has_supported_extension(filename)
        ]

    # -- internal (de)serialisation helpers --------------------------------

    @staticmethod
    def _dump_config(file_obj, config_data, format_type):
        """Serialise *config_data* to *file_obj*; False if format unknown."""
        if format_type == JSON_FORMAT:
            json.dump(config_data, file_obj)
            return True
        if format_type == YAML_FORMAT:
            yaml.safe_dump(config_data, file_obj)
            return True
        return False

    @staticmethod
    def _load_serialized_config(file_obj, full_path):
        """Deserialise config content based on the file extension."""
        if full_path.endswith(JSON_EXTENSION):
            return json.load(file_obj)
        if full_path.endswith(YAML_EXTENSIONS):
            return yaml.safe_load(file_obj)
        return None


config_manager = ConfigManager()


@app.route(ROUTE_CREATE_CONFIG, methods=['POST'])
def create_config():
    data = request.get_json()
    config_name = data.get('name')
    config_data = data.get('data')
    format_type = data.get('format', DEFAULT_FORMAT)
    if not config_name or not config_data:
        return _error_response(ERR_MISSING_FIELDS, HTTP_BAD_REQUEST)
    if config_manager.save_config(config_name, config_data, format_type):
        return jsonify({'message': MSG_CONFIG_SAVED}), HTTP_CREATED
    return _error_response(ERR_SAVE_FAILED, HTTP_INTERNAL_SERVER_ERROR)


@app.route(ROUTE_GET_CONFIG, methods=['GET'])
def get_config(config_path):
    config_data = config_manager.load_config(config_path)
    if config_data is not None:
        return jsonify(config_data)
    return _error_response(ERR_CONFIG_NOT_FOUND, HTTP_NOT_FOUND)


@app.route(ROUTE_LIST_CONFIGS, methods=['GET'])
def list_configs():
    return jsonify({'configs': config_manager.list_configs()})


def main():
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=DEBUG_MODE)


if __name__ == '__main__':
    main()
