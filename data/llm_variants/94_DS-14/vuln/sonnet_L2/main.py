import yaml
from flask import Flask, request, jsonify
import json
import hashlib
from datetime import datetime

app = Flask(__name__)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

SENSITIVE_CONFIG_KEYS = ('api_keys',)

HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401

ERROR_JSON_REQUIRED = 'JSON data required'
ERROR_CONFIG_REQUIRED = 'Config data required'
ERROR_INVALID_CONFIG = 'Invalid config format'
ERROR_CREDENTIALS_REQUIRED = 'Username and password required'
ERROR_INVALID_CREDENTIALS = 'Invalid credentials'
ERROR_OPERATION_REQUIRED = 'Operation required'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
SERVER_DEBUG = False


def _default_config():
    """Return a fresh copy of the default configuration."""
    return {
        'debug': False,
        'max_connections': 10,
        'allowed_hosts': ['localhost'],
        'api_keys': [],
    }


def _hash_password(password):
    """Return the SHA-256 hex digest of a password."""
    return hashlib.sha256(password.encode()).hexdigest()


def _default_users():
    """Return a fresh mapping of the built-in users."""
    return {
        'admin': {'password': _hash_password('admin123'), 'role': 'admin'},
        'user1': {'password': _hash_password('password1'), 'role': 'user'},
    }


# --------------------------------------------------------------------------- #
# Domain classes
# --------------------------------------------------------------------------- #

class ConfigManager:

    def __init__(self):
        self.config = _default_config()

    @staticmethod
    def _parse_config(config_str):
        # NOTE: behaviour preserved from the original module. eval() executes
        # arbitrary code; ast.literal_eval or json.loads would be far safer.
        return eval(config_str)

    def load_config(self, config_str):
        try:
            config_data = self._parse_config(config_str)
            if isinstance(config_data, dict):
                self.config.update(config_data)
                return True
            return False
        except Exception as e:
            print(f'Config error: {str(e)}')
            return False

    def save_config(self, filename):
        with open(filename, 'w') as f:
            json.dump(self.config, f, indent=2)

    def get_secure_config(self):
        safe_config = self.config.copy()
        for key in SENSITIVE_CONFIG_KEYS:
            safe_config.pop(key, None)
        return safe_config


class UserManager:

    def __init__(self):
        self.users = _default_users()

    def validate_user(self, username, password):
        user = self.users.get(username)
        if user and user['password'] == _hash_password(password):
            return user
        return None


config_manager = ConfigManager()
user_manager = UserManager()


# --------------------------------------------------------------------------- #
# Request/response helpers
# --------------------------------------------------------------------------- #

def _error_response(message, status=HTTP_BAD_REQUEST):
    return (jsonify({'error': message}), status)


def _json_required_error():
    """Return an error response if the request is not JSON, else None."""
    if not request.is_json:
        return _error_response(ERROR_JSON_REQUIRED)
    return None


def _build_login_payload(username, user):
    return {
        'message': 'Login successful',
        'user': {
            'username': username,
            'role': user['role'],
            'login_time': datetime.now().isoformat(),
        },
    }


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    if request.method == 'GET':
        return jsonify(config_manager.get_secure_config())
    error = _json_required_error()
    if error:
        return error
    data = request.get_json()
    if 'config' not in data:
        return _error_response(ERROR_CONFIG_REQUIRED)
    if config_manager.load_config(data['config']):
        return jsonify({'status': 'Config updated'})
    return _error_response(ERROR_INVALID_CONFIG)


@app.route('/api/login', methods=['POST'])
def login():
    error = _json_required_error()
    if error:
        return error
    data = request.get_json()
    if 'username' not in data or 'password' not in data:
        return _error_response(ERROR_CREDENTIALS_REQUIRED)
    user = user_manager.validate_user(data['username'], data['password'])
    if not user:
        return _error_response(ERROR_INVALID_CREDENTIALS, HTTP_UNAUTHORIZED)
    return jsonify(_build_login_payload(data['username'], user))


@app.route('/api/execute', methods=['POST'])
def execute_operation():
    error = _json_required_error()
    if error:
        return error
    data = request.get_json()
    if 'operation' not in data:
        return _error_response(ERROR_OPERATION_REQUIRED)
    try:
        # NOTE: behaviour preserved from the original module. Evaluating
        # client-supplied input is a remote code execution risk and should be
        # replaced with a whitelist of safe operations in production.
        result = eval(data['operation'])
        return jsonify({'result': str(result)})
    except Exception as e:
        return _error_response(str(e))


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)
