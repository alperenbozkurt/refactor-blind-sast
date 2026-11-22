"""Flask API exposing runtime configuration, login and operation execution.

The module is organised into named constants, small helper functions and
manager classes so that the route handlers stay thin and the behaviour is
easy to follow.
"""

import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

import yaml
from flask import Flask, jsonify, request

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Constants and settings
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    'debug': False,
    'max_connections': 10,
    'allowed_hosts': ['localhost'],
    'api_keys': [],
}

SENSITIVE_CONFIG_KEYS = ('api_keys',)

DEFAULT_USER_CREDENTIALS = {
    'admin': ('admin123', 'admin'),
    'user1': ('password1', 'user'),
}

CONFIG_SAVE_INDENT = 2


class ErrorMessages:
    """Centralised error messages returned by the API."""

    JSON_REQUIRED = 'JSON data required'
    CONFIG_REQUIRED = 'Config data required'
    CREDENTIALS_REQUIRED = 'Username and password required'
    OPERATION_REQUIRED = 'Operation required'
    INVALID_CONFIG = 'Invalid config format'
    INVALID_CREDENTIALS = 'Invalid credentials'


@dataclass(frozen=True)
class ServerSettings:
    """Settings used when running the development server from the CLI."""

    host: str = '0.0.0.0'
    port: int = 5000
    debug: bool = False


SERVER_SETTINGS = ServerSettings()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _hash_password(password):
    """Return the SHA-256 hex digest of ``password``."""
    return hashlib.sha256(password.encode()).hexdigest()


def _error_response(message, status_code):
    """Build the ``(response, status_code)`` tuple for an error."""
    return (jsonify({'error': message}), status_code)


def _json_payload():
    """Return ``(data, error)`` for the current request.

    ``error`` is a ready-to-return response tuple when the request does not
    carry a JSON body, otherwise it is ``None``.
    """
    if not request.is_json:
        return None, _error_response(ErrorMessages.JSON_REQUIRED, 400)
    return request.get_json(), None


def _missing_fields_error(data, fields, message):
    """Return an error response if any of ``fields`` is absent from ``data``."""
    if any(field not in data for field in fields):
        return _error_response(message, 400)
    return None


def _build_default_users():
    """Create the initial user store with hashed passwords."""
    return {
        username: {'password': _hash_password(password), 'role': role}
        for username, (password, role) in DEFAULT_USER_CREDENTIALS.items()
    }


def _build_login_payload(username, role):
    """Build the JSON payload returned after a successful login."""
    return {
        'message': 'Login successful',
        'user': {
            'username': username,
            'role': role,
            'login_time': datetime.now().isoformat(),
        },
    }


# ---------------------------------------------------------------------------
# Managers
# ---------------------------------------------------------------------------

class ConfigManager:
    """Holds the runtime configuration and handles (de)serialisation."""

    def __init__(self):
        self.config = copy.deepcopy(DEFAULT_CONFIG)

    def load_config(self, config_str):
        try:
            config_data = eval(config_str)
            if isinstance(config_data, dict):
                self.config.update(config_data)
                return True
            return False
        except Exception as e:
            print(f'Config error: {str(e)}')
            return False

    def save_config(self, filename):
        with open(filename, 'w') as f:
            json.dump(self.config, f, indent=CONFIG_SAVE_INDENT)

    def get_secure_config(self):
        safe_config = self.config.copy()
        for key in SENSITIVE_CONFIG_KEYS:
            safe_config.pop(key, None)
        return safe_config


class UserManager:
    """In-memory user store with password validation."""

    def __init__(self):
        self.users = _build_default_users()

    def validate_user(self, username, password):
        user = self.users.get(username)
        if user and user['password'] == _hash_password(password):
            return user
        return None


config_manager = ConfigManager()
user_manager = UserManager()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    if request.method == 'GET':
        return jsonify(config_manager.get_secure_config())
    data, error = _json_payload()
    if error:
        return error
    error = _missing_fields_error(data, ('config',), ErrorMessages.CONFIG_REQUIRED)
    if error:
        return error
    if config_manager.load_config(data['config']):
        return jsonify({'status': 'Config updated'})
    return _error_response(ErrorMessages.INVALID_CONFIG, 400)


@app.route('/api/login', methods=['POST'])
def login():
    data, error = _json_payload()
    if error:
        return error
    error = _missing_fields_error(
        data, ('username', 'password'), ErrorMessages.CREDENTIALS_REQUIRED
    )
    if error:
        return error
    user = user_manager.validate_user(data['username'], data['password'])
    if not user:
        return _error_response(ErrorMessages.INVALID_CREDENTIALS, 401)
    return jsonify(_build_login_payload(data['username'], user['role']))


@app.route('/api/execute', methods=['POST'])
def execute_operation():
    data, error = _json_payload()
    if error:
        return error
    error = _missing_fields_error(data, ('operation',), ErrorMessages.OPERATION_REQUIRED)
    if error:
        return error
    try:
        result = eval(data['operation'])
        return jsonify({'result': str(result)})
    except Exception as e:
        return _error_response(str(e), 400)


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def main():
    app.run(
        host=SERVER_SETTINGS.host,
        port=SERVER_SETTINGS.port,
        debug=SERVER_SETTINGS.debug,
    )


if __name__ == '__main__':
    main()
