import os
import json

import yaml
from flask import Flask, jsonify, request

app = Flask(__name__)

CONFIG_BASE_DIR = '/etc/app_configs'


class ConfigManager:
    """Manage configuration files stored under CONFIG_BASE_DIR."""

    def __init__(self):
        self.config_cache = {}
        os.makedirs(CONFIG_BASE_DIR, exist_ok=True)

    def validate_config_name(self, config_name):
        """Return True if config_name is non-empty and contains only
        alphanumeric characters, hyphens, or underscores."""
        if not config_name:
            return False
        return all(c.isalnum() or c in ('-', '_') for c in config_name)

    def validate_config_path(self, config_path):
        """Return True if config_path resolves to a .json/.yaml/.yml file
        located inside CONFIG_BASE_DIR."""
        base_dir = os.path.abspath(CONFIG_BASE_DIR)
        abs_path = os.path.abspath(os.path.join(base_dir, config_path))
        if not abs_path.startswith(base_dir):
            return False
        if not abs_path.endswith(('.json', '.yaml', '.yml')):
            return False
        return True

    def save_config(self, config_name, config_data, format_type='json'):
        """Write config_data to CONFIG_BASE_DIR/<config_name>.<format_type>.

        Return True on success and False on any failure.
        """
        if not self.validate_config_name(config_name):
            return False
        config_path = os.path.join(
            CONFIG_BASE_DIR, f'{config_name}.{format_type}'
        )
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
        """Load the config at config_path relative to CONFIG_BASE_DIR.

        Return the parsed config, or None if the path is invalid or the
        file cannot be read or parsed.
        """
        try:
            if not self.validate_config_path(config_path):
                return None
            full_path = os.path.abspath(
                os.path.join(CONFIG_BASE_DIR, config_path)
            )
            with open(full_path, 'r') as f:
                if full_path.endswith('.json'):
                    return json.load(f)
                elif full_path.endswith(('.yaml', '.yml')):
                    return yaml.safe_load(f)
                else:
                    return None
        except Exception:
            return None

    def list_configs(self):
        """Return the names of all config files in CONFIG_BASE_DIR."""
        return [
            f
            for f in os.listdir(CONFIG_BASE_DIR)
            if f.endswith(('.json', '.yaml', '.yml'))
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
    else:
        return (jsonify({'error': 'Failed to save config'}), 500)


@app.route('/api/config/<path:config_path>', methods=['GET'])
def get_config(config_path):
    config_data = config_manager.load_config(config_path)
    if config_data is not None:
        return jsonify(config_data)
    else:
        return (jsonify({'error': 'Config not found or invalid'}), 404)


@app.route('/api/configs', methods=['GET'])
def list_configs():
    return jsonify({'configs': config_manager.list_configs()})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
