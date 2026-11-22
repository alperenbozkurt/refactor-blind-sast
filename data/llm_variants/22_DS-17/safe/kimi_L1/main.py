"""Web-based JSON configuration manager.

Serves a small Flask UI and JSON API for listing, viewing, creating and
loading ``*.json`` configuration files stored under a fixed directory.
"""

import json
import os

from flask import Flask, abort, jsonify, render_template, request
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['CONFIG_DIR'] = os.path.abspath('/etc/app_configs')
app.config['TEMPLATE_DIR'] = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'templates')
)
app.config['MAX_CONFIG_SIZE'] = 1024 * 1024

# Permission bits for created directories (rwxr-x---) and files (rw-r-----).
_DIR_MODE = 0o750
_FILE_MODE = 0o640


class ConfigManager:
    """Read, write and list JSON config files stored in CONFIG_DIR."""

    def __init__(self):
        os.makedirs(app.config['CONFIG_DIR'], mode=_DIR_MODE, exist_ok=True)

    def is_safe_path(self, path):
        """Return True only when ``path`` resolves inside CONFIG_DIR."""
        base_path = os.path.abspath(app.config['CONFIG_DIR'])
        requested_path = os.path.abspath(path)
        return requested_path.startswith(base_path + os.sep)

    def list_configs(self):
        """Return the names of all usable ``*.json`` files in CONFIG_DIR.

        Logs the error and returns an empty list if the directory
        cannot be listed.
        """
        try:
            return [
                filename
                for filename in os.listdir(app.config['CONFIG_DIR'])
                if filename.endswith('.json')
                and self.is_safe_path(
                    os.path.join(app.config['CONFIG_DIR'], filename)
                )
            ]
        except Exception as e:
            app.logger.error(f'Error listing configs: {e}')
            return []

    def load_config(self, config_name):
        """Load and return the parsed JSON content of ``config_name``.

        Raises ValueError for an invalid name, a non-JSON file, an
        oversized file or malformed JSON, PermissionError if the path
        escapes CONFIG_DIR and FileNotFoundError if the file is missing.
        """
        try:
            config_path, safe_name = self._resolve_config_path(
                config_name, 'Only JSON config files are supported'
            )
            if not os.path.exists(config_path):
                raise FileNotFoundError(f'Config {safe_name} not found')
            if os.path.getsize(config_path) > app.config['MAX_CONFIG_SIZE']:
                raise ValueError('Config file too large')
            with open(config_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            raise ValueError('Invalid JSON format')

    def save_config(self, config_name, config_data):
        """Write ``config_data`` (a dict) as pretty-printed JSON.

        Applies the same name and path validation as load_config and
        re-raises any failure after logging it.
        """
        try:
            config_path, _ = self._resolve_config_path(
                config_name, 'Config must be a JSON file'
            )
            if not isinstance(config_data, dict):
                raise ValueError('Config data must be a dictionary')
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            app.logger.error(f'Error saving config: {e}')
            raise

    def _resolve_config_path(self, config_name, extension_error):
        """Validate ``config_name`` and return (config path, safe name)."""
        if not config_name or not isinstance(config_name, str):
            raise ValueError('Invalid config name')
        safe_name = secure_filename(config_name)
        if not safe_name.endswith('.json'):
            raise ValueError(extension_error)
        config_path = os.path.join(app.config['CONFIG_DIR'], safe_name)
        if not self.is_safe_path(config_path):
            raise PermissionError('Access denied')
        return config_path, safe_name


@app.route('/api/config/<config_name>', methods=['GET'])
def get_config(config_name):
    """Return the requested config as a JSON response."""
    try:
        manager = ConfigManager()
        config = manager.load_config(config_name)
        return jsonify(config)
    except FileNotFoundError:
        return jsonify({'error': 'Config not found'}), 404
    except PermissionError:
        return jsonify({'error': 'Access denied'}), 403
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/config', methods=['POST'])
def create_config():
    """Create or overwrite a config file from a JSON request body."""
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        config_name = request.json.get('name')
        config_data = request.json.get('data')
        if not config_name or not config_data:
            return jsonify({'error': 'Missing name or data'}), 400
        manager = ConfigManager()
        manager.save_config(config_name, config_data)
        return jsonify({'status': 'success'})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except PermissionError:
        return jsonify({'error': 'Access denied'}), 403
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/')
def index():
    """Render the config manager overview page."""
    try:
        manager = ConfigManager()
        configs = manager.list_configs()
        return render_template('config_manager.html', configs=configs)
    except Exception:
        abort(500)


@app.route('/view/<config_name>')
def view_config(config_name):
    """Render a page showing a single config file."""
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


_SAMPLE_CONFIGS = {
    'database.json': {'host': 'localhost', 'port': 5432},
    'app_settings.json': {'debug': False, 'timeout': 30},
}

_TEMPLATES = {
    'config_manager.html': (
        '\n'
        '            <h1>Config Manager</h1>\n'
        '            <ul>{% for config in configs %}\n'
        '                <li><a href="/view/{{ config }}">{{ config }}</a></li>\n'
        '            {% endfor %}</ul>\n'
        '        '
    ),
    'view_config.html': (
        '\n'
        '            <h1>Config: {{ config_name }}</h1>\n'
        '            <pre>{{ config_data }}</pre>\n'
        '        '
    ),
}


def _create_file_if_missing(path, content, description, as_json=False):
    """Write ``content`` to ``path`` unless the file already exists."""
    if os.path.exists(path):
        return
    try:
        with open(path, 'w') as f:
            if as_json:
                json.dump(content, f, indent=2)
            else:
                f.write(content)
        os.chmod(path, _FILE_MODE)
    except Exception as e:
        app.logger.error(f'Error creating {description}: {e}')


def main():
    """Create config/template directories, seed defaults and run the app."""
    os.makedirs(app.config['CONFIG_DIR'], mode=_DIR_MODE, exist_ok=True)
    os.makedirs(app.config['TEMPLATE_DIR'], mode=_DIR_MODE, exist_ok=True)

    for name, data in _SAMPLE_CONFIGS.items():
        _create_file_if_missing(
            os.path.join(app.config['CONFIG_DIR'], name),
            data,
            f'sample config {name}',
            as_json=True,
        )

    for name, content in _TEMPLATES.items():
        _create_file_if_missing(
            os.path.join(app.config['TEMPLATE_DIR'], name),
            content,
            f'template {name}',
        )

    app.run(host='0.0.0.0', port=8080)


if __name__ == '__main__':
    main()
