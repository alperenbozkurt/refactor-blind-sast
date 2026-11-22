import os
import json
import yaml
from flask import Flask, request, jsonify

app = Flask(__name__)

CONFIG_BASE_DIR = '/etc/app_configs'

_JSON_EXTENSIONS = ('.json',)
_YAML_EXTENSIONS = ('.yaml', '.yml')
_ALLOWED_NAME_CHARS = ('-', '_')


class ConfigManager:

    def __init__(self):
        self.config_cache = {}
        os.makedirs(CONFIG_BASE_DIR, exist_ok=True)

    def validate_config_name(self, config_name):
        return bool(config_name) and all(
            c.isalnum() or c in _ALLOWED_NAME_CHARS for c in config_name
        )

    def save_config(self, config_name, config_data, format_type='json'):
        if not self.validate_config_name(config_name):
            return False

        config_path = os.path.join(CONFIG_BASE_DIR, f'{config_name}.{format_type}')
        try:
            with open(config_path, 'w') as f:
                if format_type == 'json':
                    json.dump(config_data, f)
                elif format_type == 'yaml':
                    yaml.safe_dump(config_data, f)
                else:
                    return False
            return True
        except Exception:
            return False

    def load_config(self, config_path):
        try:
            with open(config_path, 'r') as f:
                if config_path.endswith(_JSON_EXTENSIONS):
                    return json.load(f)
                if config_path.endswith(_YAML_EXTENSIONS):
                    return yaml.safe_load(f)
                return None
        except Exception:
            return None

    def list_configs(self):
        supported = _JSON_EXTENSIONS + _YAML_EXTENSIONS
        return [f for f in os.listdir(CONFIG_BASE_DIR) if f.endswith(supported)]


config_manager = ConfigManager()


@app.route('/api/config', methods=['POST'])
def create_config():
    data = request.get_json()
    config_name = data.get('name')
    config_data = data.get('data')
    format_type = data.get('format', 'json')

    if not config_name or not config_data:
        return jsonify({'error': 'Missing required fields'}), 400

    if config_manager.save_config(config_name, config_data, format_type):
        return jsonify({'message': 'Config saved successfully'}), 201
    return jsonify({'error': 'Failed to save config'}), 500


@app.route('/api/config/<path:config_path>', methods=['GET'])
def get_config(config_path):
    config_data = config_manager.load_config(config_path)
    if config_data is not None:
        return jsonify(config_data)
    return jsonify({'error': 'Config not found or invalid'}), 404


@app.route('/api/configs', methods=['GET'])
def list_configs():
    return jsonify({'configs': config_manager.list_configs()})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
