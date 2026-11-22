import json
import os

import yaml
from flask import Flask, jsonify, request

CONFIG_BASE_DIR = '/etc/app_configs'

FORMAT_JSON = 'json'
FORMAT_YAML = 'yaml'

JSON_EXTENSION = '.json'
YAML_EXTENSIONS = ('.yaml', '.yml')
CONFIG_FILE_EXTENSIONS = (JSON_EXTENSION,) + YAML_EXTENSIONS

ALLOWED_NAME_SPECIAL_CHARS = ('-', '_')

HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500

MSG_CONFIG_SAVED = 'Config saved successfully'
ERR_MISSING_FIELDS = 'Missing required fields'
ERR_SAVE_FAILED = 'Failed to save config'
ERR_CONFIG_NOT_FOUND = 'Config not found or invalid'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
SERVER_DEBUG = True

app = Flask(__name__)


def _serialize_config(config_data, format_type, file_obj):
    """Write ``config_data`` to ``file_obj`` using ``format_type``.

    Returns True when the format is supported, False otherwise.
    """
    if format_type == FORMAT_JSON:
        json.dump(config_data, file_obj)
        return True
    if format_type == FORMAT_YAML:
        yaml.safe_dump(config_data, file_obj)
        return True
    return False


def _deserialize_config(config_path, file_obj):
    """Parse ``file_obj`` based on the extension of ``config_path``.

    Returns the parsed config, or None for unsupported extensions.
    """
    if config_path.endswith(JSON_EXTENSION):
        return json.load(file_obj)
    if config_path.endswith(YAML_EXTENSIONS):
        return yaml.safe_load(file_obj)
    return None


class ConfigManager:

    def __init__(self):
        self.config_cache = {}
        os.makedirs(CONFIG_BASE_DIR, exist_ok=True)

    def validate_config_name(self, config_name):
        return bool(config_name) and all(
            c.isalnum() or c in ALLOWED_NAME_SPECIAL_CHARS for c in config_name
        )

    def save_config(self, config_name, config_data, format_type=FORMAT_JSON):
        if not self.validate_config_name(config_name):
            return False
        config_path = self._build_config_path(config_name, format_type)
        try:
            with open(config_path, 'w') as f:
                if not _serialize_config(config_data, format_type, f):
                    return False
            return True
        except Exception:
            return False

    def load_config(self, config_path):
        try:
            with open(config_path, 'r') as f:
                return _deserialize_config(config_path, f)
        except Exception:
            return None

    def list_configs(self):
        return [
            f for f in os.listdir(CONFIG_BASE_DIR)
            if f.endswith(CONFIG_FILE_EXTENSIONS)
        ]

    @staticmethod
    def _build_config_path(config_name, format_type):
        return os.path.join(CONFIG_BASE_DIR, f'{config_name}.{format_type}')


config_manager = ConfigManager()


@app.route('/api/config', methods=['POST'])
def create_config():
    data = request.get_json()
    config_name = data.get('name')
    config_data = data.get('data')
    format_type = data.get('format', FORMAT_JSON)
    if not config_name or not config_data:
        return jsonify({'error': ERR_MISSING_FIELDS}), HTTP_BAD_REQUEST
    if config_manager.save_config(config_name, config_data, format_type):
        return jsonify({'message': MSG_CONFIG_SAVED}), HTTP_CREATED
    return jsonify({'error': ERR_SAVE_FAILED}), HTTP_INTERNAL_SERVER_ERROR


@app.route('/api/config/<path:config_path>', methods=['GET'])
def get_config(config_path):
    config_data = config_manager.load_config(config_path)
    if config_data is not None:
        return jsonify(config_data)
    return jsonify({'error': ERR_CONFIG_NOT_FOUND}), HTTP_NOT_FOUND


@app.route('/api/configs', methods=['GET'])
def list_configs():
    return jsonify({'configs': config_manager.list_configs()})


def main():
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)


if __name__ == '__main__':
    main()
