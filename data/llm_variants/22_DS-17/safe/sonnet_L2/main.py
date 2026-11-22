import os
import json
from flask import Flask, request, jsonify, render_template, abort
from werkzeug.utils import secure_filename

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
DEFAULT_CONFIG_DIR = '/etc/app_configs'
TEMPLATES_SUBDIR = 'templates'
DEFAULT_MAX_CONFIG_SIZE = 1024 * 1024

JSON_EXTENSION = '.json'

DIR_MODE = 0o750   # 488
FILE_MODE = 0o640  # 416

JSON_INDENT = 2

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8080

INDEX_TEMPLATE_NAME = 'config_manager.html'
VIEW_TEMPLATE_NAME = 'view_config.html'

ERR_INVALID_NAME = 'Invalid config name'
ERR_LOAD_NOT_JSON = 'Only JSON config files are supported'
ERR_SAVE_NOT_JSON = 'Config must be a JSON file'
ERR_ACCESS_DENIED = 'Access denied'
ERR_TOO_LARGE = 'Config file too large'
ERR_INVALID_JSON = 'Invalid JSON format'
ERR_DATA_NOT_DICT = 'Config data must be a dictionary'
ERR_NOT_FOUND = 'Config not found'
ERR_INTERNAL = 'Internal server error'
ERR_REQUEST_NOT_JSON = 'Request must be JSON'
ERR_MISSING_FIELDS = 'Missing name or data'

SAMPLE_CONFIGS = {
    'database.json': {'host': 'localhost', 'port': 5432},
    'app_settings.json': {'debug': False, 'timeout': 30},
}

DEFAULT_TEMPLATES = {
    INDEX_TEMPLATE_NAME: (
        '\n            <h1>Config Manager</h1>\n            <ul>{% for config in configs %}\n'
        '                <li><a href="/view/{{ config }}">{{ config }}</a></li>\n'
        '            {% endfor %}</ul>\n        '
    ),
    VIEW_TEMPLATE_NAME: (
        '\n            <h1>Config: {{ config_name }}</h1>\n            <pre>{{ config_data }}</pre>\n        '
    ),
}

# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #
app = Flask(__name__)
app.config['CONFIG_DIR'] = os.path.abspath(DEFAULT_CONFIG_DIR)
app.config['TEMPLATE_DIR'] = os.path.abspath(
    os.path.join(os.path.dirname(__file__), TEMPLATES_SUBDIR)
)
app.config['MAX_CONFIG_SIZE'] = DEFAULT_MAX_CONFIG_SIZE


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _config_dir():
    return app.config['CONFIG_DIR']


def _ensure_directory(path):
    os.makedirs(path, mode=DIR_MODE, exist_ok=True)


def _error_response(message, status):
    return (jsonify({'error': message}), status)


def _is_valid_name(config_name):
    return bool(config_name) and isinstance(config_name, str)


# --------------------------------------------------------------------------- #
# Config manager
# --------------------------------------------------------------------------- #
class ConfigManager:

    def __init__(self):
        _ensure_directory(_config_dir())

    def is_safe_path(self, path):
        base_path = os.path.abspath(_config_dir())
        requested_path = os.path.abspath(path)
        return requested_path.startswith(base_path + os.sep)

    def _resolve_config_path(self, config_name, not_json_message):
        """Validate a config name and return (safe_name, safe_path)."""
        if not _is_valid_name(config_name):
            raise ValueError(ERR_INVALID_NAME)
        safe_name = secure_filename(config_name)
        if not safe_name.endswith(JSON_EXTENSION):
            raise ValueError(not_json_message)
        config_path = os.path.join(_config_dir(), safe_name)
        if not self.is_safe_path(config_path):
            raise PermissionError(ERR_ACCESS_DENIED)
        return safe_name, config_path

    def list_configs(self):
        try:
            return [
                f for f in os.listdir(_config_dir())
                if f.endswith(JSON_EXTENSION)
                and self.is_safe_path(os.path.join(_config_dir(), f))
            ]
        except Exception as e:
            app.logger.error(f'Error listing configs: {e}')
            return []

    def load_config(self, config_name):
        try:
            safe_name, config_path = self._resolve_config_path(
                config_name, ERR_LOAD_NOT_JSON
            )
            if not os.path.exists(config_path):
                raise FileNotFoundError(f'Config {safe_name} not found')
            if os.path.getsize(config_path) > app.config['MAX_CONFIG_SIZE']:
                raise ValueError(ERR_TOO_LARGE)
            with open(config_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            raise ValueError(ERR_INVALID_JSON)

    def save_config(self, config_name, config_data):
        try:
            _, config_path = self._resolve_config_path(
                config_name, ERR_SAVE_NOT_JSON
            )
            if not isinstance(config_data, dict):
                raise ValueError(ERR_DATA_NOT_DICT)
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=JSON_INDENT, ensure_ascii=False)
        except Exception as e:
            app.logger.error(f'Error saving config: {e}')
            raise


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/api/config/<config_name>', methods=['GET'])
def get_config(config_name):
    try:
        manager = ConfigManager()
        config = manager.load_config(config_name)
        return jsonify(config)
    except FileNotFoundError:
        return _error_response(ERR_NOT_FOUND, 404)
    except PermissionError:
        return _error_response(ERR_ACCESS_DENIED, 403)
    except ValueError as e:
        return _error_response(str(e), 400)
    except Exception:
        return _error_response(ERR_INTERNAL, 500)


@app.route('/api/config', methods=['POST'])
def create_config():
    try:
        if not request.is_json:
            return _error_response(ERR_REQUEST_NOT_JSON, 400)
        config_name = request.json.get('name')
        config_data = request.json.get('data')
        if not config_name or not config_data:
            return _error_response(ERR_MISSING_FIELDS, 400)
        manager = ConfigManager()
        manager.save_config(config_name, config_data)
        return jsonify({'status': 'success'})
    except ValueError as e:
        return _error_response(str(e), 400)
    except PermissionError:
        return _error_response(ERR_ACCESS_DENIED, 403)
    except Exception:
        return _error_response(ERR_INTERNAL, 500)


@app.route('/')
def index():
    try:
        manager = ConfigManager()
        configs = manager.list_configs()
        return render_template(INDEX_TEMPLATE_NAME, configs=configs)
    except Exception:
        abort(500)


@app.route('/view/<config_name>')
def view_config(config_name):
    try:
        manager = ConfigManager()
        config = manager.load_config(config_name)
        return render_template(
            VIEW_TEMPLATE_NAME,
            config_name=secure_filename(config_name),
            config_data=config,
        )
    except FileNotFoundError:
        abort(404, ERR_NOT_FOUND)
    except PermissionError:
        abort(403, ERR_ACCESS_DENIED)
    except ValueError as e:
        abort(400, str(e))
    except Exception:
        abort(500, ERR_INTERNAL)


# --------------------------------------------------------------------------- #
# Bootstrap helpers (used by the command-line entry point)
# --------------------------------------------------------------------------- #
def _create_file_if_missing(path, write_func, description):
    if os.path.exists(path):
        return
    try:
        with open(path, 'w') as f:
            write_func(f)
        os.chmod(path, FILE_MODE)
    except Exception as e:
        app.logger.error(f'Error creating {description}: {e}')


def _create_sample_configs():
    for name, data in SAMPLE_CONFIGS.items():
        path = os.path.join(_config_dir(), name)
        _create_file_if_missing(
            path,
            lambda f, data=data: json.dump(data, f, indent=JSON_INDENT),
            f'sample config {name}',
        )


def _create_default_templates():
    for name, content in DEFAULT_TEMPLATES.items():
        path = os.path.join(app.config['TEMPLATE_DIR'], name)
        _create_file_if_missing(
            path,
            lambda f, content=content: f.write(content),
            f'template {name}',
        )


def main():
    _ensure_directory(_config_dir())
    _ensure_directory(app.config['TEMPLATE_DIR'])
    _create_sample_configs()
    _create_default_templates()
    app.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
