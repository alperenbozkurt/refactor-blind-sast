import os
import json
from flask import Flask, request, jsonify, render_template, abort

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
DEFAULT_CONFIG_DIR = '/etc/app_configs'
DEFAULT_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')

JSON_EXTENSION = '.json'
JSON_INDENT = 2

HOST = '0.0.0.0'
PORT = 8080

HTTP_BAD_REQUEST = 400
HTTP_SERVER_ERROR = 500

INDEX_TEMPLATE_NAME = 'config_manager.html'
VIEW_TEMPLATE_NAME = 'view_config.html'

SAMPLE_CONFIGS = {
    'database.json': {'host': 'localhost', 'port': 5432},
    'app_settings.json': {'debug': True, 'timeout': 30},
}

DEFAULT_TEMPLATES = {
    INDEX_TEMPLATE_NAME: (
        '\n            <h1>Config Manager</h1>\n'
        '            <ul>{% for config in configs %}\n'
        '                <li><a href="/view/{{ config }}">{{ config }}</a></li>\n'
        '            {% endfor %}</ul>\n        '
    ),
    VIEW_TEMPLATE_NAME: (
        '\n            <h1>Config: {{ config_name }}</h1>\n'
        '            <pre>{{ config_data }}</pre>\n        '
    ),
}

# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #
app = Flask(__name__)
app.config['CONFIG_DIR'] = DEFAULT_CONFIG_DIR
app.config['TEMPLATE_DIR'] = DEFAULT_TEMPLATE_DIR


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _config_dir():
    return app.config['CONFIG_DIR']


def _template_dir():
    return app.config['TEMPLATE_DIR']


def _config_path(config_name):
    return os.path.join(_config_dir(), config_name)


def _is_json_name(name):
    return name.endswith(JSON_EXTENSION)


def _write_json_file(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=JSON_INDENT)


def _read_json_file(path):
    with open(path, 'r') as f:
        return json.load(f)


def _error_response(message, status):
    return (jsonify({'error': message}), status)


def _write_if_missing(path, writer):
    """Invoke ``writer(path)`` only when ``path`` does not yet exist."""
    if not os.path.exists(path):
        writer(path)


def _write_text_file(content):
    def writer(path):
        with open(path, 'w') as f:
            f.write(content)
    return writer


def _write_json_writer(data):
    def writer(path):
        _write_json_file(path, data)
    return writer


# --------------------------------------------------------------------------- #
# Domain logic
# --------------------------------------------------------------------------- #
class ConfigManager:

    def __init__(self):
        if not os.path.exists(_config_dir()):
            os.makedirs(_config_dir())

    def list_configs(self):
        return [f for f in os.listdir(_config_dir()) if _is_json_name(f)]

    def load_config(self, config_name):
        config_path = _config_path(config_name)
        if not os.path.exists(config_path):
            raise FileNotFoundError(f'Config {config_name} not found')
        if not _is_json_name(config_path):
            raise ValueError('Only JSON config files are supported')
        return _read_json_file(config_path)

    def save_config(self, config_name, config_data):
        config_path = _config_path(config_name)
        if not _is_json_name(config_name):
            raise ValueError('Config must be a JSON file')
        _write_json_file(config_path, config_data)


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/api/config/<config_name>', methods=['GET'])
def get_config(config_name):
    try:
        manager = ConfigManager()
        config = manager.load_config(config_name)
        return jsonify(config)
    except Exception as e:
        return _error_response(str(e), HTTP_BAD_REQUEST)


@app.route('/api/config', methods=['POST'])
def create_config():
    try:
        config_name = request.json.get('name')
        config_data = request.json.get('data')
        if not config_name or not config_data:
            return _error_response('Missing name or data', HTTP_BAD_REQUEST)
        manager = ConfigManager()
        manager.save_config(config_name, config_data)
        return jsonify({'status': 'success'})
    except Exception as e:
        return _error_response(str(e), HTTP_SERVER_ERROR)


@app.route('/')
def index():
    manager = ConfigManager()
    configs = manager.list_configs()
    return render_template(INDEX_TEMPLATE_NAME, configs=configs)


@app.route('/view/<config_name>')
def view_config(config_name):
    try:
        manager = ConfigManager()
        config = manager.load_config(config_name)
        return render_template(VIEW_TEMPLATE_NAME, config_name=config_name, config_data=config)
    except Exception as e:
        abort(HTTP_BAD_REQUEST, str(e))


# --------------------------------------------------------------------------- #
# Bootstrap / CLI
# --------------------------------------------------------------------------- #
def _ensure_directories():
    os.makedirs(_config_dir(), exist_ok=True)
    os.makedirs(_template_dir(), exist_ok=True)


def _ensure_sample_configs():
    for name, data in SAMPLE_CONFIGS.items():
        _write_if_missing(_config_path(name), _write_json_writer(data))


def _ensure_default_templates():
    for name, content in DEFAULT_TEMPLATES.items():
        path = os.path.join(_template_dir(), name)
        _write_if_missing(path, _write_text_file(content))


def main():
    _ensure_directories()
    _ensure_sample_configs()
    _ensure_default_templates()
    app.run(host=HOST, port=PORT)


if __name__ == '__main__':
    main()
