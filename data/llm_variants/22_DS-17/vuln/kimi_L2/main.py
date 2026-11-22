"""Flask-based JSON configuration file manager.

Exposes a small web UI and JSON API for listing, viewing, loading and
creating ``*.json`` configuration files stored in a configurable directory.
"""

import json
import os

from flask import Flask, abort, jsonify, render_template, request

# ---------------------------------------------------------------------------
# Application defaults (named constants)
# ---------------------------------------------------------------------------

DEFAULT_CONFIG_DIR = '/etc/app_configs'
TEMPLATE_DIR_NAME = 'templates'
JSON_FILE_EXTENSION = '.json'

CONFIG_MANAGER_TEMPLATE = 'config_manager.html'
VIEW_CONFIG_TEMPLATE = 'view_config.html'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8080

HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500

ERROR_MISSING_NAME_OR_DATA = 'Missing name or data'
STATUS_SUCCESS = 'success'

CONFIG_MANAGER_TEMPLATE_SOURCE = """
            <h1>Config Manager</h1>
            <ul>{% for config in configs %}
                <li><a href="/view/{{ config }}">{{ config }}</a></li>
            {% endfor %}</ul>
        """

VIEW_CONFIG_TEMPLATE_SOURCE = """
            <h1>Config: {{ config_name }}</h1>
            <pre>{{ config_data }}</pre>
        """

SAMPLE_CONFIGS = {
    'database.json': {'host': 'localhost', 'port': 5432},
    'app_settings.json': {'debug': True, 'timeout': 30},
}

DEFAULT_TEMPLATES = {
    CONFIG_MANAGER_TEMPLATE: CONFIG_MANAGER_TEMPLATE_SOURCE,
    VIEW_CONFIG_TEMPLATE: VIEW_CONFIG_TEMPLATE_SOURCE,
}

app = Flask(__name__)
app.config['CONFIG_DIR'] = DEFAULT_CONFIG_DIR
app.config['TEMPLATE_DIR'] = os.path.join(
    os.path.dirname(__file__), TEMPLATE_DIR_NAME
)


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------

def _ensure_directory(path):
    """Create *path* (including parents) unless it already exists."""
    if not os.path.exists(path):
        os.makedirs(path)


def _config_path(config_name):
    """Return the absolute path of *config_name* inside the config dir."""
    return os.path.join(app.config['CONFIG_DIR'], config_name)


def _read_json_file(path):
    with open(path, 'r') as f:
        return json.load(f)


def _write_json_file(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def _write_text_file(path, content):
    with open(path, 'w') as f:
        f.write(content)


def _write_json_file_if_missing(path, data):
    if not os.path.exists(path):
        _write_json_file(path, data)


def _write_text_file_if_missing(path, content):
    if not os.path.exists(path):
        _write_text_file(path, content)


# ---------------------------------------------------------------------------
# Core domain object
# ---------------------------------------------------------------------------

class ConfigManager:
    """List, load and save JSON config files stored in ``CONFIG_DIR``."""

    def __init__(self):
        _ensure_directory(app.config['CONFIG_DIR'])

    def list_configs(self):
        return [
            filename
            for filename in os.listdir(app.config['CONFIG_DIR'])
            if filename.endswith(JSON_FILE_EXTENSION)
        ]

    def load_config(self, config_name):
        config_path = _config_path(config_name)
        if not os.path.exists(config_path):
            raise FileNotFoundError(f'Config {config_name} not found')
        if not config_path.endswith(JSON_FILE_EXTENSION):
            raise ValueError('Only JSON config files are supported')
        return _read_json_file(config_path)

    def save_config(self, config_name, config_data):
        config_path = _config_path(config_name)
        if not config_name.endswith(JSON_FILE_EXTENSION):
            raise ValueError('Config must be a JSON file')
        _write_json_file(config_path, config_data)


# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------

@app.route('/api/config/<config_name>', methods=['GET'])
def get_config(config_name):
    try:
        manager = ConfigManager()
        config = manager.load_config(config_name)
        return jsonify(config)
    except Exception as e:
        return jsonify({'error': str(e)}), HTTP_BAD_REQUEST


@app.route('/api/config', methods=['POST'])
def create_config():
    try:
        config_name = request.json.get('name')
        config_data = request.json.get('data')
        if not config_name or not config_data:
            return (
                jsonify({'error': ERROR_MISSING_NAME_OR_DATA}),
                HTTP_BAD_REQUEST,
            )
        manager = ConfigManager()
        manager.save_config(config_name, config_data)
        return jsonify({'status': STATUS_SUCCESS})
    except Exception as e:
        return jsonify({'error': str(e)}), HTTP_INTERNAL_SERVER_ERROR


@app.route('/')
def index():
    manager = ConfigManager()
    configs = manager.list_configs()
    return render_template(CONFIG_MANAGER_TEMPLATE, configs=configs)


@app.route('/view/<config_name>')
def view_config(config_name):
    try:
        manager = ConfigManager()
        config = manager.load_config(config_name)
        return render_template(
            VIEW_CONFIG_TEMPLATE,
            config_name=config_name,
            config_data=config,
        )
    except Exception as e:
        abort(HTTP_BAD_REQUEST, str(e))


# ---------------------------------------------------------------------------
# Script bootstrap / command-line entry point
# ---------------------------------------------------------------------------

def create_sample_configs():
    """Seed the config directory with sample configs (non-destructive)."""
    for name, data in SAMPLE_CONFIGS.items():
        path = os.path.join(app.config['CONFIG_DIR'], name)
        _write_json_file_if_missing(path, data)


def create_default_templates():
    """Seed the template directory with default templates (non-destructive)."""
    for name, content in DEFAULT_TEMPLATES.items():
        path = os.path.join(app.config['TEMPLATE_DIR'], name)
        _write_text_file_if_missing(path, content)


def main():
    os.makedirs(app.config['CONFIG_DIR'], exist_ok=True)
    os.makedirs(app.config['TEMPLATE_DIR'], exist_ok=True)
    create_sample_configs()
    create_default_templates()
    app.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
