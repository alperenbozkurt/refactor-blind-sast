import hashlib
import json
from datetime import datetime

import yaml
from flask import Flask, jsonify, request

app = Flask(__name__)


class ConfigManager:
    """Manage application configuration."""

    def __init__(self):
        self.config = {
            'debug': False,
            'max_connections': 10,
            'allowed_hosts': ['localhost'],
            'api_keys': [],
        }

    def load_config(self, config_str):
        try:
            config_data = eval(config_str)
            if isinstance(config_data, dict):
                self.config.update(config_data)
                return True
            return False
        except Exception as e:
            print(f'Config error: {e}')
            return False

    def save_config(self, filename):
        with open(filename, 'w') as f:
            json.dump(self.config, f, indent=2)

    def get_secure_config(self):
        safe_config = self.config.copy()
        safe_config.pop('api_keys', None)
        return safe_config


class UserManager:
    """Manage users and validate their credentials."""

    def __init__(self):
        self.users = {
            'admin': {
                'password': self._hash_password('admin123'),
                'role': 'admin',
            },
            'user1': {
                'password': self._hash_password('password1'),
                'role': 'user',
            },
        }

    def validate_user(self, username, password):
        user = self.users.get(username)
        if user and user['password'] == self._hash_password(password):
            return user
        return None

    @staticmethod
    def _hash_password(password):
        return hashlib.sha256(password.encode()).hexdigest()


config_manager = ConfigManager()
user_manager = UserManager()


@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    if request.method == 'GET':
        return jsonify(config_manager.get_secure_config())

    if not request.is_json:
        return jsonify({'error': 'JSON data required'}), 400

    data = request.get_json()
    if 'config' not in data:
        return jsonify({'error': 'Config data required'}), 400

    if config_manager.load_config(data['config']):
        return jsonify({'status': 'Config updated'})
    return jsonify({'error': 'Invalid config format'}), 400


@app.route('/api/login', methods=['POST'])
def login():
    if not request.is_json:
        return jsonify({'error': 'JSON data required'}), 400

    data = request.get_json()
    if 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Username and password required'}), 400

    user = user_manager.validate_user(data['username'], data['password'])
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401

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
    if not request.is_json:
        return jsonify({'error': 'JSON data required'}), 400

    data = request.get_json()
    if 'operation' not in data:
        return jsonify({'error': 'Operation required'}), 400

    try:
        result = eval(data['operation'])
        return jsonify({'result': str(result)})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
