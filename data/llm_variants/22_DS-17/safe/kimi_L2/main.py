"""Flask-based JSON configuration manager.

Provides a small web UI and REST API for listing, viewing, loading and
creating JSON configuration files stored in a fixed configuration directory.
"""

import json
import os

from flask import Flask, abort, jsonify, render_template, request
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# Application configuration
# ---------------------------------------------------------------------------

CONFIG_DIR = os.path.abspath('/etc/app_configs')
TEMPLATE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))
MAX_CONFIG_SIZE = 1024 * 1024

JSON_EXTENSION = '.json'

DIRECTORY_MODE = 0o750
CONFIG_FILE_MODE = 0o640

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8080

CONFIG_MANAGER_TEMPLATE = 'config_manager.html'
VIEW_CONFIG_TEMPLATE = 'view_config.html'

# Error messages
ERROR_INVALID_CONFIG_NAME = 'Invalid config name'
ERROR_ONLY_JSON_CONFIGS = 'Only JSON config files are supported'
ERROR_CONFIG_MUST_BE_JSON = 'Config must be a JSON file'
ERROR_ACCESS_DENIED = 'Access denied'
ERROR_CONFIG_FILE_TOO_LARGE = 'Config file too large'
ERROR_INVALID_JSON_FORMAT = 'Invalid JSON format'
ERROR_CONFIG_DATA_MUST_BE_DICT = 'Config data must be a dictionary'
ERROR_CONFIG_NOT_FOUND = 'Config not found'
ERROR_INTERNAL_SERVER_ERROR = 'Internal server error'
ERROR_REQUEST_MUST_BE_JSON = 'Request must be JSON'
ERROR_MISSING_NAME_OR_DATA = 'Missing name or data'

SAMPLE_CONFIGS = {
    'database.json': {'host': 'localhost', 'port': 5432},
    'app_settings.json': {'debug': False, 'timeout': 30},
}

DEFAULT_TEMPLATES = {
    CONFIG_MANAGER_TEMPLATE: '\n            <h1>Config Manager</h1>\n            <ul>{% for config in configs %}\n                <li><a href="/view/{{ config }}">{{ config }}</a></li>\n            {% endfor %}</ul>\n        ',
    VIEW_CONFIG_TEMPLATE: '\n            <h1>Config: {{ config_name }}</h1>\n            <pre>{{ config_data }}</pre>\n        ',
}

app = Flask(__name__)
app.config['CONFIG_DIR'] = CONFIG_DIR
app.config['TEMPLATE_DIR'] = TEMPLATE_DIR
app.config['MAX_CONFIG_SIZE'] = MAX_CONFIG_SIZE


def _error_response(message, status_code):
    """Build a JSON error response tuple."""
    return (jsonify({'error': message}), status_code)


class ConfigManager:
    """Manage JSON configuration files stored in the config directory."""

    def __init__(self):
        os.makedirs(app.config['CONFIG_DIR'], mode=DIRECTORY_MODE, exist_ok=True)

    def is_safe_path(self, path):
        """Return True if ``path`` resolves inside the config directory."""
        base_path = os.path.abspath(app.config['CONFIG_DIR'])
        requested_path = os.path.abspath(path)
        return requested_path.startswith(base_path + os.sep)

    def list_configs(self):
        """Return the names of all JSON config files in the config directory."""
        try:
            config_dir = app.config['CONFIG_DIR']
            return [
                filename
                for filename in os.listdir(config_dir)
                if filename.endswith(JSON_EXTENSION)
                and self.is_safe_path(os.path.join(config_dir, filename))
            ]
        except Exception as e:
            app.logger.error(f'Error listing configs: {e}')
            return []

    def load_config(self, config_name):
        """Load and return the JSON config stored under ``config_name``."""
        try:
            safe_name = self._validated_safe_name(config_name, ERROR_ONLY_JSON_CONFIGS)
            config_path = self._config_path_for(safe_name)
            if not os.path.exists(config_path):
                raise FileNotFoundError(f'Config {safe_name} not found')
            if os.path.getsize(config_path) > app.config['MAX_CONFIG_SIZE']:
                raise ValueError(ERROR_CONFIG_FILE_TOO_LARGE)
            with open(config_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            raise ValueError(ERROR_INVALID_JSON_FORMAT)

    def save_config(self, config_name, config_data):
        """Write ``config_data`` as JSON to the config file ``config_name``."""
        try:
            safe_name = self._validated_safe_name(config_name, ERROR_CONFIG_MUST_BE_JSON)
            config_path = self._config_path_for(safe_name)
            if not isinstance(config_data, dict):
                raise ValueError(ERROR_CONFIG_DATA_MUST_BE_DICT)
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            app.logger.error(f'Error saving config: {e}')
            raise

    def _validated_safe_name(self, config_name, extension_error):
        """Validate ``config_name`` and return its sanitised file name."""
        if not config_name or not isinstance(config_name, str):
            raise ValueError(ERROR_INVALID_CONFIG_NAME)
        safe_name = secure_filename(config_name)
        if not safe_name.endswith(JSON_EXTENSION):
            raise ValueError(extension_error)
        return safe_name

    def _config_path_for(self, safe_name):
        """Return the full path for ``safe_name`` after a safety check."""
        config_path = os.path.join(app.config['CONFIG_DIR'], safe_name)
        if not self.is_safe_path(config_path):
            raise PermissionError(ERROR_ACCESS_DENIED)
        return config_path


@app.route('/api/config/<config_name>', methods=['GET'])
def get_config(config_name):
    try:
        manager = ConfigManager()
        config = manager.load_config(config_name)
        return jsonify(config)
    except FileNotFoundError:
        return _error_response(ERROR_CONFIG_NOT_FOUND, 404)
    except PermissionError:
        return _error_response(ERROR_ACCESS_DENIED, 403)
    except ValueError as e:
        return _error_response(str(e), 400)
    except Exception:
        return _error_response(ERROR_INTERNAL_SERVER_ERROR, 500)


@app.route('/api/config', methods=['POST'])
def create_config():
    try:
        if not request.is_json:
            return _error_response(ERROR_REQUEST_MUST_BE_JSON, 400)
        config_name = request.json.get('name')
        config_data = request.json.get('data')
        if not config_name or not config_data:
            return _error_response(ERROR_MISSING_NAME_OR_DATA, 400)
        manager = ConfigManager()
        manager.save_config(config_name, config_data)
        return jsonify({'status': 'success'})
    except ValueError as e:
        return _error_response(str(e), 400)
    except PermissionError:
        return _error_response(ERROR_ACCESS_DENIED, 403)
    except Exception:
        return _error_response(ERROR_INTERNAL_SERVER_ERROR, 500)


@app.route('/')
def index():
    try:
        manager = ConfigManager()
        configs = manager.list_configs()
        return render_template(CONFIG_MANAGER_TEMPLATE, configs=configs)
    except Exception:
        abort(500)


@app.route('/view/<config_name>')
def view_config(config_name):
    try:
        manager = ConfigManager()
        config = manager.load_config(config_name)
        return render_template(
            VIEW_CONFIG_TEMPLATE,
            config_name=secure_filename(config_name),
            config_data=config,
        )
    except FileNotFoundError:
        abort(404, ERROR_CONFIG_NOT_FOUND)
    except PermissionError:
        abort(403, ERROR_ACCESS_DENIED)
    except ValueError as e:
        abort(400, str(e))
    except Exception:
        abort(500, ERROR_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# Command-line entry point helpers
# ---------------------------------------------------------------------------

def _ensure_directories():
    """Create the config and template directories if they are missing."""
    os.makedirs(app.config['CONFIG_DIR'], mode=DIRECTORY_MODE, exist_ok=True)
    os.makedirs(app.config['TEMPLATE_DIR'], mode=DIRECTORY_MODE, exist_ok=True)


def _create_sample_configs():
    """Write the bundled sample configs that do not exist yet."""
    for name, data in SAMPLE_CONFIGS.items():
        path = os.path.join(app.config['CONFIG_DIR'], name)
        if not os.path.exists(path):
            try:
                with open(path, 'w') as f:
                    json.dump(data, f, indent=2)
                os.chmod(path, CONFIG_FILE_MODE)
            except Exception as e:
                app.logger.error(f'Error creating sample config {name}: {e}')


def _create_default_templates():
    """Write the bundled templates that do not exist yet."""
    for name, content in DEFAULT_TEMPLATES.items():
        path = os.path.join(app.config['TEMPLATE_DIR'], name)
        if not os.path.exists(path):
            try:
                with open(path, 'w') as f:
                    f.write(content)
                os.chmod(path, CONFIG_FILE_MODE)
            except Exception as e:
                app.logger.error(f'Error creating template {name}: {e}')


def main():
    """Bootstrap the environment and run the development server."""
    _ensure_directories()
    _create_sample_configs()
    _create_default_templates()
    app.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
