import os
import json
import yaml
from flask import Flask, request, jsonify

app = Flask(__name__)

CONFIG_BASE_DIR = '/etc/app_configs'
JSON_EXTENSION = '.json'
YAML_EXTENSIONS = ('.yaml', '.yml')
ALLOWED_EXTENSIONS = (JSON_EXTENSION,) + YAML_EXTENSIONS


class ConfigManager:
    """Manages reading and writing configuration files in CONFIG_BASE_DIR."""

    def __init__(self):
        self.config_cache = {}
        os.makedirs(CONFIG_BASE_DIR, exist_ok=True)

    def validate_config_name(self, config_name):
        if not config_name:
            return False
        return all(c.isalnum() or c in ('-', '_') for c in config_name)

    def validate_config_path(self, config_path):
        base_dir = os.path.abspath(CONFIG_BASE_DIR)
        abs_path = os.path.abspath(os.path.join(base_dir, config_path))
        if not abs_path.startswith(base_dir):
            return False
        if not abs_path.endswith(ALLOWED_EXTENSIONS):
            return False
        return True

    def save_config(self, config_name, config_data, format_type='json'):
        if not self.validate_config_name(config_name):
            return False

        config_path = os.path.join(CONFIG_BASE_DIR, f'{config_name}.{format_type}')
        try:
            with open(config_path, 'w') as f:
                return self._write_config(f, config_data, format_type)
        except Exception:
            return False

    @staticmethod
    def _write_config(file_obj, config_data, format_type):
        if format_type == 'json':
            json.dump(config_data, file_obj)
        elif format_type == 'yaml':
            yaml.safe_dump(config_data, file_obj)
        else:
            return False
        return True

    def load_config(self, config_path):
        try:
            if not self.validate_config_path(config_path):
                return None
            full_path = os.path.abspath(os.path.join(CONFIG_BASE_DIR, config_path))
            with open(full_path, 'r') as f:
                return self._parse_config(f, full_path)
        except Exception:
            return None

    @staticmethod
    def _parse_config(file_obj, full_path):
        if full_path.endswith(JSON_EXTENSION):
            return json.load(file_obj)
        if full_path.endswith(YAML_EXTENSIONS):
            return yaml.safe_load(file_obj)
        return None

    def list_configs(self):
        return [
            name for name in os.listdir(CONFIG_BASE_DIR)
            if name.endswith(ALLOWED_EXTENSIONS)
        ]


config_manager = ConfigManager()


@app.route('/api/config', methods=['POST'])
def create_config():
    data = request.get_json()
    config_name = data.get('name')
    config_data = data.get('data')
    format_type = data.get('format', 'json')

    if not config_name or not config_data:
        return (jsonify({'error': 'Missing required fields'}), 400)

    if config_manager.save_config(config_name, config_data, format_type):
        return (jsonify({'message': 'Config saved successfully'}), 201)
    return (jsonify({'error': 'Failed to save config'}), 500)


@app.route('/api/config/<path:config_path>', methods=['GET'])
def get_config(config_path):
    config_data = config_manager.load_config(config_path)
    if config_data is not None:
        return jsonify(config_data)
    return (jsonify({'error': 'Config not found or invalid'}), 404)


@app.route('/api/configs', methods=['GET'])
def list_configs():
    return jsonify({'configs': config_manager.list_configs()})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
