import os
import json
from flask import Flask, request, jsonify, render_template, abort
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['CONFIG_DIR'] = os.path.abspath('/etc/app_configs')
app.config['TEMPLATE_DIR'] = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))
app.config['MAX_CONFIG_SIZE'] = 1024 * 1024

DIRECTORY_MODE = 0o750  # 488
FILE_MODE = 0o640       # 416

SAMPLE_CONFIGS = {
    'database.json': {'host': 'localhost', 'port': 5432},
    'app_settings.json': {'debug': False, 'timeout': 30},
}

DEFAULT_TEMPLATES = {
    'config_manager.html': (
        '\n            <h1>Config Manager</h1>\n            <ul>{% for config in configs %}\n'
        '                <li><a href="/view/{{ config }}">{{ config }}</a></li>\n'
        '            {% endfor %}</ul>\n        '
    ),
    'view_config.html': (
        '\n            <h1>Config: {{ config_name }}</h1>\n'
        '            <pre>{{ config_data }}</pre>\n        '
    ),
}


class ConfigManager:

    def __init__(self):
        os.makedirs(app.config['CONFIG_DIR'], mode=DIRECTORY_MODE, exist_ok=True)

    def is_safe_path(self, path):
        base_path = os.path.abspath(app.config['CONFIG_DIR'])
        requested_path = os.path.abspath(path)
        return requested_path.startswith(base_path + os.sep)

    def _resolve_config_path(self, config_name, extension_error):
        """Validate a config name and return (safe_name, config_path)."""
        if not config_name or not isinstance(config_name, str):
            raise ValueError('Invalid config name')
        safe_name = secure_filename(config_name)
        if not safe_name.endswith('.json'):
            raise ValueError(extension_error)
        config_path = os.path.join(app.config['CONFIG_DIR'], safe_name)
        if not self.is_safe_path(config_path):
            raise PermissionError('Access denied')
        return safe_name, config_path

    def list_configs(self):
        config_dir = app.config['CONFIG_DIR']
        try:
            return [
                name for name in os.listdir(config_dir)
                if name.endswith('.json') and self.is_safe_path(os.path.join(config_dir, name))
            ]
        except Exception as e:
            app.logger.error(f'Error listing configs: {e}')
            return []

    def load_config(self, config_name):
        try:
            safe_name, config_path = self._resolve_config_path(
                config_name, 'Only JSON config files are supported')
            if not os.path.exists(config_path):
                raise FileNotFoundError(f'Config {safe_name} not found')
            if os.path.getsize(config_path) > app.config['MAX_CONFIG_SIZE']:
                raise ValueError('Config file too large')
            with open(config_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            raise ValueError('Invalid JSON format')

    def save_config(self, config_name, config_data):
        try:
            _, config_path = self._resolve_config_path(
                config_name, 'Config must be a JSON file')
            if not isinstance(config_data, dict):
                raise ValueError('Config data must be a dictionary')
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            app.logger.error(f'Error saving config: {e}')
            raise


def _error_response(message, status):
    return (jsonify({'error': message}), status)


@app.route('/api/config/<config_name>', methods=['GET'])
def get_config(config_name):
    try:
        manager = ConfigManager()
        config = manager.load_config(config_name)
        return jsonify(config)
    except FileNotFoundError:
        return _error_response('Config not found', 404)
    except PermissionError:
        return _error_response('Access denied', 403)
    except ValueError as e:
        return _error_response(str(e), 400)
    except Exception:
        return _error_response('Internal server error', 500)


@app.route('/api/config', methods=['POST'])
def create_config():
    try:
        if not request.is_json:
            return _error_response('Request must be JSON', 400)
        config_name = request.json.get('name')
        config_data = request.json.get('data')
        if not config_name or not config_data:
            return _error_response('Missing name or data', 400)
        manager = ConfigManager()
        manager.save_config(config_name, config_data)
        return jsonify({'status': 'success'})
    except ValueError as e:
        return _error_response(str(e), 400)
    except PermissionError:
        return _error_response('Access denied', 403)
    except Exception:
        return _error_response('Internal server error', 500)


@app.route('/')
def index():
    try:
        manager = ConfigManager()
        configs = manager.list_configs()
        return render_template('config_manager.html', configs=configs)
    except Exception:
        abort(500)


@app.route('/view/<config_name>')
def view_config(config_name):
    try:
        manager = ConfigManager()
        config = manager.load_config(config_name)
        return render_template(
            'view_config.html',
            config_name=secure_filename(config_name),
            config_data=config,
        )
    except FileNotFoundError:
        abort(404, 'Config not found')
    except PermissionError:
        abort(403, 'Access denied')
    except ValueError as e:
        abort(400, str(e))
    except Exception:
        abort(500, 'Internal server error')


def _create_file_if_missing(directory, name, content, description):
    """Write `content` to directory/name with restricted permissions if absent."""
    path = os.path.join(directory, name)
    if os.path.exists(path):
        return
    try:
        with open(path, 'w') as f:
            f.write(content)
        os.chmod(path, FILE_MODE)
    except Exception as e:
        app.logger.error(f'Error creating {description} {name}: {e}')


def _setup_environment():
    os.makedirs(app.config['CONFIG_DIR'], mode=DIRECTORY_MODE, exist_ok=True)
    os.makedirs(app.config['TEMPLATE_DIR'], mode=DIRECTORY_MODE, exist_ok=True)

    for name, data in SAMPLE_CONFIGS.items():
        _create_file_if_missing(
            app.config['CONFIG_DIR'], name, json.dumps(data, indent=2), 'sample config')

    for name, content in DEFAULT_TEMPLATES.items():
        _create_file_if_missing(
            app.config['TEMPLATE_DIR'], name, content, 'template')


if __name__ == '__main__':
    _setup_environment()
    app.run(host='0.0.0.0', port=8080)
