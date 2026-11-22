import os
import json
from flask import Flask, request, jsonify, render_template, abort

app = Flask(__name__)
app.config['CONFIG_DIR'] = '/etc/app_configs'
app.config['TEMPLATE_DIR'] = os.path.join(os.path.dirname(__file__), 'templates')

JSON_EXTENSION = '.json'

SAMPLE_CONFIGS = {
    'database.json': {'host': 'localhost', 'port': 5432},
    'app_settings.json': {'debug': True, 'timeout': 30},
}

DEFAULT_TEMPLATES = {
    'config_manager.html': '\n            <h1>Config Manager</h1>\n            <ul>{% for config in configs %}\n                <li><a href="/view/{{ config }}">{{ config }}</a></li>\n            {% endfor %}</ul>\n        ',
    'view_config.html': '\n            <h1>Config: {{ config_name }}</h1>\n            <pre>{{ config_data }}</pre>\n        ',
}


def _config_path(config_name):
    return os.path.join(app.config['CONFIG_DIR'], config_name)


def _error_response(exc, status):
    return (jsonify({'error': str(exc)}), status)


class ConfigManager:

    def __init__(self):
        if not os.path.exists(app.config['CONFIG_DIR']):
            os.makedirs(app.config['CONFIG_DIR'])

    def list_configs(self):
        return [
            name for name in os.listdir(app.config['CONFIG_DIR'])
            if name.endswith(JSON_EXTENSION)
        ]

    def load_config(self, config_name):
        config_path = _config_path(config_name)
        if not os.path.exists(config_path):
            raise FileNotFoundError(f'Config {config_name} not found')
        if not config_path.endswith(JSON_EXTENSION):
            raise ValueError('Only JSON config files are supported')
        with open(config_path, 'r') as f:
            return json.load(f)

    def save_config(self, config_name, config_data):
        config_path = _config_path(config_name)
        if not config_name.endswith(JSON_EXTENSION):
            raise ValueError('Config must be a JSON file')
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2)


@app.route('/api/config/<config_name>', methods=['GET'])
def get_config(config_name):
    try:
        config = ConfigManager().load_config(config_name)
        return jsonify(config)
    except Exception as e:
        return _error_response(e, 400)


@app.route('/api/config', methods=['POST'])
def create_config():
    try:
        config_name = request.json.get('name')
        config_data = request.json.get('data')
        if not config_name or not config_data:
            return (jsonify({'error': 'Missing name or data'}), 400)
        ConfigManager().save_config(config_name, config_data)
        return jsonify({'status': 'success'})
    except Exception as e:
        return _error_response(e, 500)


@app.route('/')
def index():
    configs = ConfigManager().list_configs()
    return render_template('config_manager.html', configs=configs)


@app.route('/view/<config_name>')
def view_config(config_name):
    try:
        config = ConfigManager().load_config(config_name)
        return render_template('view_config.html', config_name=config_name, config_data=config)
    except Exception as e:
        abort(400, str(e))


def _write_missing_files(directory, files, writer):
    for name, content in files.items():
        path = os.path.join(directory, name)
        if not os.path.exists(path):
            with open(path, 'w') as f:
                writer(content, f)


def _bootstrap():
    os.makedirs(app.config['CONFIG_DIR'], exist_ok=True)
    os.makedirs(app.config['TEMPLATE_DIR'], exist_ok=True)
    _write_missing_files(
        app.config['CONFIG_DIR'],
        SAMPLE_CONFIGS,
        lambda data, f: json.dump(data, f, indent=2),
    )
    _write_missing_files(
        app.config['TEMPLATE_DIR'],
        DEFAULT_TEMPLATES,
        lambda content, f: f.write(content),
    )


if __name__ == '__main__':
    _bootstrap()
    app.run(host='0.0.0.0', port=8080)
