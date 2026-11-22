"""Flask service for managing JSON/YAML configuration files."""

import json
import os

import yaml
from flask import Flask, jsonify, request

app = Flask(__name__)

CONFIG_BASE_DIR = '/etc/app_configs'


class ConfigManager:
    """Create, read, and list config files stored under CONFIG_BASE_DIR."""

    ALLOWED_EXTENSIONS = ('.json', '.yaml', '.yml')

    def __init__(self):
        self.config_cache = {}
        os.makedirs(CONFIG_BASE_DIR, exist_ok=True)

    def validate_config_name(self, config_name):
        """Check that the name is non-empty and uses only safe characters."""
        return bool(config_name) and all(
            c.isalnum() or c in ('-', '_') for c in config_name
        )

    def validate_config_path(self, config_path):
        """Check that the path stays under the base dir with a valid extension."""
        base_dir = os.path.abspath(CONFIG_BASE_DIR)
        abs_path = os.path.abspath(os.path.join(base_dir, config_path))
        if not abs_path.startswith(base_dir):
            return False
        return abs_path.endswith(self.ALLOWED_EXTENSIONS)

    def save_config(self, config_name, config_data, format_type='json'):
        """Write config_data to <config_name>.<format_type>; return success."""
        if not self.validate_config_name(config_name):
            return False
        config_path = os.path.join(CONFIG_BASE_DIR, f'{config_name}.{format_type}')
        try:
            with open(config_path, 'w') as config_file:
                if format_type == 'json':
                    json.dump(config_data, config_file)
                elif format_type == 'yaml':
                    yaml.safe_dump(config_data, config_file)
                else:
                    return False
        except Exception:
            return False
        return True

    def load_config(self, config_path):
        """Load and parse a config file; return None on any failure."""
        try:
            if not self.validate_config_path(config_path):
                return None
            full_path = os.path.abspath(os.path.join(CONFIG_BASE_DIR, config_path))
            with open(full_path, 'r') as config_file:
                if full_path.endswith('.json'):
                    return json.load(config_file)
                if full_path.endswith(('.yaml', '.yml')):
                    return yaml.safe_load(config_file)
                return None
        except Exception:
            return None

    def list_configs(self):
        """List the config filenames stored in the base directory."""
        return [
            filename
            for filename in os.listdir(CONFIG_BASE_DIR)
            if filename.endswith(self.ALLOWED_EXTENSIONS)
        ]


config_manager = ConfigManager()


@app.route('/api/config', methods=['POST'])
def create_config():
    """Create or replace a config file from a JSON request body."""
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
    """Return the names of all available config files."""
    return jsonify({'configs': config_manager.list_configs()})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
