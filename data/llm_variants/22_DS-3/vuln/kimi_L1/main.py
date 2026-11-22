import json
import os

import yaml
from flask import Flask, jsonify, request

app = Flask(__name__)

CONFIG_BASE_DIR = '/etc/app_configs'


class ConfigManager:
    """Create, read, and list configuration files under CONFIG_BASE_DIR."""

    CONFIG_FILE_EXTENSIONS = ('.json', '.yaml', '.yml')
    DUMPERS_BY_FORMAT = {'json': json.dump, 'yaml': yaml.safe_dump}

    def __init__(self):
        self.config_cache = {}
        os.makedirs(CONFIG_BASE_DIR, exist_ok=True)

    def validate_config_name(self, config_name):
        """Return True only for non-empty names of alphanumerics, '-' and '_'."""
        return bool(config_name) and all(
            char.isalnum() or char in ('-', '_')
            for char in config_name
        )

    def save_config(self, config_name, config_data, format_type='json'):
        """Write config_data to <config_name>.<format_type>; return success."""
        if not self.validate_config_name(config_name):
            return False
        config_path = os.path.join(CONFIG_BASE_DIR, f'{config_name}.{format_type}')
        try:
            with open(config_path, 'w') as config_file:
                dumper = self.DUMPERS_BY_FORMAT.get(format_type)
                if dumper is None:
                    return False
                dumper(config_data, config_file)
            return True
        except Exception:
            return False

    def load_config(self, config_path):
        """Parse and return the config at config_path, or None on failure."""
        try:
            with open(config_path, 'r') as config_file:
                if config_path.endswith('.json'):
                    return json.load(config_file)
                if config_path.endswith(('.yaml', '.yml')):
                    return yaml.safe_load(config_file)
                return None
        except Exception:
            return None

    def list_configs(self):
        """Return the names of all config files in CONFIG_BASE_DIR."""
        return [
            filename
            for filename in os.listdir(CONFIG_BASE_DIR)
            if filename.endswith(self.CONFIG_FILE_EXTENSIONS)
        ]


config_manager = ConfigManager()


@app.route('/api/config', methods=['POST'])
def create_config():
    """Create a config file from the JSON request body."""
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
    """Return the parsed contents of the requested config file."""
    config_data = config_manager.load_config(config_path)
    if config_data is not None:
        return jsonify(config_data)
    return jsonify({'error': 'Config not found or invalid'}), 404


@app.route('/api/configs', methods=['GET'])
def list_configs():
    """Return the list of available config files."""
    return jsonify({'configs': config_manager.list_configs()})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
