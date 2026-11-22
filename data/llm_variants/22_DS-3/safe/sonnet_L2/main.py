import os
import json
import yaml
from flask import Flask, request, jsonify

app = Flask(__name__)

CONFIG_BASE_DIR = '/etc/app_configs'

# Supported file extensions and formats
JSON_EXTENSION = '.json'
YAML_EXTENSIONS = ('.yaml', '.yml')
ALLOWED_EXTENSIONS = (JSON_EXTENSION,) + YAML_EXTENSIONS
FORMAT_JSON = 'json'
FORMAT_YAML = 'yaml'
DEFAULT_FORMAT = FORMAT_JSON
SUPPORTED_SAVE_FORMATS = (FORMAT_JSON, FORMAT_YAML)

# Config name validation
ALLOWED_NAME_EXTRA_CHARS = ('-', '_')

# HTTP settings
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_SERVER_ERROR = 500

# Server settings
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
SERVER_DEBUG = False


def _has_allowed_extension(path):
    """Return True if the path ends with a supported config extension."""
    return path.endswith(ALLOWED_EXTENSIONS)


def _is_within_directory(abs_path, base_dir):
    """Return True if abs_path is base_dir or located beneath it."""
    return abs_path == base_dir or abs_path.startswith(base_dir.rstrip(os.sep) + os.sep)


def _dump_config(config_data, file_obj, format_type):
    """Serialize config data to an open file using the given format."""
    if format_type == FORMAT_JSON:
        json.dump(config_data, file_obj)
    else:
        yaml.safe_dump(config_data, file_obj)


def _read_config(file_obj, full_path):
    """Deserialize config data from an open file based on its extension."""
    if full_path.endswith(JSON_EXTENSION):
        return json.load(file_obj)
    if full_path.endswith(YAML_EXTENSIONS):
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
            (c.isalnum() or c in ALLOWED_NAME_EXTRA_CHARS for c in config_name)
        )

    def validate_config_path(self, config_path):
        base_dir = os.path.abspath(CONFIG_BASE_DIR)
        abs_path = os.path.abspath(os.path.join(base_dir, config_path))
        if not _is_within_directory(abs_path, base_dir):
            return False
        if not _has_allowed_extension(abs_path):
            return False
        return True

    def save_config(self, config_name, config_data, format_type=DEFAULT_FORMAT):
        if not self.validate_config_name(config_name):
            return False
        # Reject unsupported formats before touching the filesystem so that
        # the format string can never influence the written path.
        if format_type not in SUPPORTED_SAVE_FORMATS:
            return False
        config_path = os.path.join(CONFIG_BASE_DIR, f'{config_name}.{format_type}')
        try:
            with open(config_path, 'w') as f:
                _dump_config(config_data, f, format_type)
            return True
        except Exception:
            return False

    def load_config(self, config_path):
        try:
            if not self.validate_config_path(config_path):
                return None
            full_path = os.path.abspath(os.path.join(CONFIG_BASE_DIR, config_path))
            with open(full_path, 'r') as f:
                return _read_config(f, full_path)
        except Exception:
            return None

    def list_configs(self):
        return [f for f in os.listdir(CONFIG_BASE_DIR) if _has_allowed_extension(f)]


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
    return _error_response('Failed to save config', HTTP_SERVER_ERROR)


@app.route('/api/config/<path:config_path>', methods=['GET'])
def get_config(config_path):
    config_data = config_manager.load_config(config_path)
    if config_data is not None:
        return jsonify(config_data)
    return _error_response('Config not found or invalid', HTTP_NOT_FOUND)


@app.route('/api/configs', methods=['GET'])
def list_configs():
    return jsonify({'configs': config_manager.list_configs()})


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)
