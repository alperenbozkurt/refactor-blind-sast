import os
import json
import yaml
from flask import Flask, request, jsonify

app = Flask(__name__)

CONFIG_BASE_DIR = '/etc/app_configs'

# Format / extension constants
FORMAT_JSON = 'json'
FORMAT_YAML = 'yaml'
DEFAULT_FORMAT = FORMAT_JSON
JSON_EXTENSIONS = ('.json',)
YAML_EXTENSIONS = ('.yaml', '.yml')
CONFIG_EXTENSIONS = JSON_EXTENSIONS + YAML_EXTENSIONS
ALLOWED_NAME_EXTRA_CHARS = ('-', '_')

# HTTP status codes
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_SERVER_ERROR = 500

# Server settings
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
SERVER_DEBUG = True


def _is_valid_name_char(char):
    return char.isalnum() or char in ALLOWED_NAME_EXTRA_CHARS


def _build_config_path(config_name, format_type):
    return os.path.join(CONFIG_BASE_DIR, f'{config_name}.{format_type}')


def _dump_config(file_obj, config_data, format_type):
    """Write config_data to file_obj. Return False if format is unsupported."""
    if format_type == FORMAT_JSON:
        json.dump(config_data, file_obj)
        return True
    if format_type == FORMAT_YAML:
        yaml.safe_dump(config_data, file_obj)
        return True
    return False


def _parse_config(file_obj, config_path):
    """Parse file_obj based on the path's extension. Return None if unsupported."""
    if config_path.endswith(JSON_EXTENSIONS):
        return json.load(file_obj)
    if config_path.endswith(YAML_EXTENSIONS):
        return yaml.safe_load(file_obj)
    return None


def _error_response(message, status_code):
    return (jsonify({'error': message}), status_code)


class ConfigManager:

    def __init__(self):
        self.config_cache = {}
        os.makedirs(CONFIG_BASE_DIR, exist_ok=True)

    def validate_config_name(self, config_name):
        return bool(config_name) and all(
            (_is_valid_name_char(c) for c in config_name)
        )

    def save_config(self, config_name, config_data, format_type=DEFAULT_FORMAT):
        if not self.validate_config_name(config_name):
            return False
        config_path = _build_config_path(config_name, format_type)
        try:
            with open(config_path, 'w') as f:
                return _dump_config(f, config_data, format_type)
        except Exception:
            return False

    def load_config(self, config_path):
        try:
            with open(config_path, 'r') as f:
                return _parse_config(f, config_path)
        except Exception:
            return None

    def list_configs(self):
        return [
            f for f in os.listdir(CONFIG_BASE_DIR)
            if f.endswith(CONFIG_EXTENSIONS)
        ]


config_manager = ConfigManager()


@app.route('/api/config', methods=['POST'])
def create_config():
    data = request.get_json()
    config_name = data.get('name')
    config_data = data.get('data')
    format_type = data.get('format', DEFAULT_FORMAT)
    if not config_name or not config_data:
        return _error_response('Missing required fields', HTTP_BAD_REQUEST)
    if config_manager.save_config(config_name, config_data, format_type):
        return (jsonify({'message': 'Config saved successfully'}), HTTP_CREATED)
    else:
        return _error_response('Failed to save config', HTTP_SERVER_ERROR)


@app.route('/api/config/<path:config_path>', methods=['GET'])
def get_config(config_path):
    config_data = config_manager.load_config(config_path)
    if config_data is not None:
        return jsonify(config_data)
    else:
        return _error_response('Config not found or invalid', HTTP_NOT_FOUND)


@app.route('/api/configs', methods=['GET'])
def list_configs():
    return jsonify({'configs': config_manager.list_configs()})


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)
