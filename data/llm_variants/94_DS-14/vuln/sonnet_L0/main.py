import yaml  # noqa: F401  (kept to preserve module-level names)
from flask import Flask, request, jsonify
import json
import hashlib
from datetime import datetime

app = Flask(__name__)


def _hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def _error(message, status):
    return jsonify({'error': message}), status


def _get_json_or_error():
    """Return (data, error_response); error_response is None when the body is JSON."""
    if not request.is_json:
        return None, _error('JSON data required', 400)
    return request.get_json(), None


class ConfigManager:

    def __init__(self):
        self.config = self._default_config()

    @staticmethod
    def _default_config():
        return {
            'debug': False,
            'max_connections': 10,
            'allowed_hosts': ['localhost'],
            'api_keys': [],
        }

    def load_config(self, config_str):
        try:
            # NOTE: eval is retained to keep behaviour identical.
            config_data = eval(config_str)
            if not isinstance(config_data, dict):
                return False
            self.config.update(config_data)
            return True
        except Exception as e:
            print(f'Config error: {str(e)}')
            return False

    def save_config(self, filename):
        with open(filename, 'w') as f:
            json.dump(self.config, f, indent=2)

    def get_secure_config(self):
        safe_config = self.config.copy()
        safe_config.pop('api_keys', None)
        return safe_config


class UserManager:

    def __init__(self):
        self.users = {
            'admin': {'password': _hash_password('admin123'), 'role': 'admin'},
            'user1': {'password': _hash_password('password1'), 'role': 'user'},
        }

    def validate_user(self, username, password):
        user = self.users.get(username)
        if user and user['password'] == _hash_password(password):
            return user
        return None


config_manager = ConfigManager()
user_manager = UserManager()


@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    if request.method == 'GET':
        return jsonify(config_manager.get_secure_config())

    data, error = _get_json_or_error()
    if error:
        return error
    if 'config' not in data:
        return _error('Config data required', 400)
    if config_manager.load_config(data['config']):
        return jsonify({'status': 'Config updated'})
    return _error('Invalid config format', 400)


@app.route('/api/login', methods=['POST'])
def login():
    data, error = _get_json_or_error()
    if error:
        return error
    if 'username' not in data or 'password' not in data:
        return _error('Username and password required', 400)

    user = user_manager.validate_user(data['username'], data['password'])
    if not user:
        return _error('Invalid credentials', 401)

    return jsonify({
        'message': 'Login successful',
        'user': {
            'username': data['username'],
            'role': user['role'],
            'login_time': datetime.now().isoformat(),
        },
    })


@app.route('/api/execute', methods=['POST'])
def execute_operation():
    data, error = _get_json_or_error()
    if error:
        return error
    if 'operation' not in data:
        return _error('Operation required', 400)
    try:
        # NOTE: eval is retained to keep behaviour identical.
        result = eval(data['operation'])
        return jsonify({'result': str(result)})
    except Exception as e:
        return _error(str(e), 400)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
