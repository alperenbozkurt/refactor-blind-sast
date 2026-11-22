import json
import os

from flask import Flask, abort, jsonify, render_template, request

app = Flask(__name__)
app.config['CONFIG_DIR'] = '/etc/app_configs'
app.config['TEMPLATE_DIR'] = os.path.join(os.path.dirname(__file__), 'templates')

_JSON_EXTENSION = '.json'

_SAMPLE_CONFIGS = {
    'database.json': {'host': 'localhost', 'port': 5432},
    'app_settings.json': {'debug': True, 'timeout': 30},
}

_TEMPLATES = {
    'config_manager.html': '\n            <h1>Config Manager</h1>\n            <ul>{% for config in configs %}\n                <li><a href="/view/{{ config }}">{{ config }}</a></li>\n            {% endfor %}</ul>\n        ',
    'view_config.html': '\n            <h1>Config: {{ config_name }}</h1>\n            <pre>{{ config_data }}</pre>\n        ',
}


class ConfigManager:
    """Create, read and list JSON configuration files stored on disk."""

    def __init__(self):
        os.makedirs(app.config['CONFIG_DIR'], exist_ok=True)

    def list_configs(self):
        return [
            filename
            for filename in os.listdir(app.config['CONFIG_DIR'])
            if filename.endswith(_JSON_EXTENSION)
        ]

    def load_config(self, config_name):
        config_path = self._path_for(config_name)
        if not os.path.exists(config_path):
            raise FileNotFoundError(f'Config {config_name} not found')
        if not config_path.endswith(_JSON_EXTENSION):
            raise ValueError('Only JSON config files are supported')
        with open(config_path, 'r') as config_file:
            return json.load(config_file)

    def save_config(self, config_name, config_data):
        if not config_name.endswith(_JSON_EXTENSION):
            raise ValueError('Config must be a JSON file')
        with open(self._path_for(config_name), 'w') as config_file:
            json.dump(config_data, config_file, indent=2)

    @staticmethod
    def _path_for(config_name):
        return os.path.join(app.config['CONFIG_DIR'], config_name)


@app.route('/api/config/<config_name>', methods=['GET'])
def get_config(config_name):
    try:
        config = ConfigManager().load_config(config_name)
        return jsonify(config)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 400


@app.route('/api/config', methods=['POST'])
def create_config():
    try:
        config_name = request.json.get('name')
        config_data = request.json.get('data')
        if not config_name or not config_data:
            return jsonify({'error': 'Missing name or data'}), 400
        ConfigManager().save_config(config_name, config_data)
        return jsonify({'status': 'success'})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@app.route('/')
def index():
    configs = ConfigManager().list_configs()
    return render_template('config_manager.html', configs=configs)


@app.route('/view/<config_name>')
def view_config(config_name):
    try:
        config = ConfigManager().load_config(config_name)
        return render_template(
            'view_config.html', config_name=config_name, config_data=config
        )
    except Exception as exc:
        abort(400, str(exc))


def _write_json_file(path, data):
    with open(path, 'w') as json_file:
        json.dump(data, json_file, indent=2)


def _write_text_file(path, content):
    with open(path, 'w') as text_file:
        text_file.write(content)


def _seed_files(directory, files, writer):
    for name, payload in files.items():
        path = os.path.join(directory, name)
        if not os.path.exists(path):
            writer(path, payload)


def main():
    os.makedirs(app.config['CONFIG_DIR'], exist_ok=True)
    os.makedirs(app.config['TEMPLATE_DIR'], exist_ok=True)
    _seed_files(app.config['CONFIG_DIR'], _SAMPLE_CONFIGS, _write_json_file)
    _seed_files(app.config['TEMPLATE_DIR'], _TEMPLATES, _write_text_file)
    app.run(host='0.0.0.0', port=8080)


if __name__ == '__main__':
    main()
