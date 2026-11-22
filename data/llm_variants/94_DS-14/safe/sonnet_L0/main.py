import yaml  # noqa: F401  (kept to preserve module-level names)
from flask import Flask, request, jsonify
import json
import hashlib
from datetime import datetime
from enum import Enum
from typing import Dict, Any

app = Flask(__name__)

JSON_REQUIRED_RESPONSE = ('error', 'JSON data required')


def _error(message: str, status: int, **extra):
    return jsonify({'error': message, **extra}), status


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


class ConfigAction(Enum):
    SET_DEBUG = 'set_debug'
    SET_MAX_CONNECTIONS = 'set_max_connections'
    ADD_ALLOWED_HOST = 'add_allowed_host'
    REMOVE_ALLOWED_HOST = 'remove_allowed_host'


class ConfigManager:

    def __init__(self):
        self.config = {
            'debug': False,
            'max_connections': 10,
            'allowed_hosts': ['localhost'],
            'api_keys': [],
        }

    def _set_debug(self, data: Any) -> bool:
        if isinstance(data, bool):
            self.config['debug'] = data
            return True
        return False

    def _set_max_connections(self, data: Any) -> bool:
        if isinstance(data, int) and data > 0:
            self.config['max_connections'] = data
            return True
        return False

    def _add_allowed_host(self, data: Any) -> bool:
        if isinstance(data, str) and data not in self.config['allowed_hosts']:
            self.config['allowed_hosts'].append(data)
            return True
        return False

    def _remove_allowed_host(self, data: Any) -> bool:
        if isinstance(data, str) and data in self.config['allowed_hosts']:
            self.config['allowed_hosts'].remove(data)
            return True
        return False

    def update_config(self, action: str, data: Any) -> bool:
        try:
            action = ConfigAction(action)
        except ValueError:
            return False

        handlers = {
            ConfigAction.SET_DEBUG: self._set_debug,
            ConfigAction.SET_MAX_CONNECTIONS: self._set_max_connections,
            ConfigAction.ADD_ALLOWED_HOST: self._add_allowed_host,
            ConfigAction.REMOVE_ALLOWED_HOST: self._remove_allowed_host,
        }
        return handlers[action](data)

    def save_config(self, filename: str) -> None:
        with open(filename, 'w') as f:
            json.dump(self.config, f, indent=2)

    def get_secure_config(self) -> Dict[str, Any]:
        safe_config = self.config.copy()
        safe_config.pop('api_keys', None)
        return safe_config


class UserManager:

    def __init__(self):
        self.users = {
            'admin': {'password': _hash_password('admin123'), 'role': 'admin'},
            'user1': {'password': _hash_password('password1'), 'role': 'user'},
        }

    def validate_user(self, username: str, password: str) -> Dict[str, Any]:
        user = self.users.get(username)
        if user and user['password'] == _hash_password(password):
            return user
        return None


class OperationType(Enum):
    LIST_CONFIG = 'list_config'
    SYSTEM_INFO = 'system_info'
    TIME = 'time'


config_manager = ConfigManager()
user_manager = UserManager()


@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    if request.method == 'GET':
        return jsonify(config_manager.get_secure_config())
    if not request.is_json:
        return _error('JSON data required', 400)
    data = request.get_json()
    if 'action' not in data or 'data' not in data:
        return _error('Action and data required', 400)
    if config_manager.update_config(data['action'], data['data']):
        return jsonify({'status': 'Config updated'})
    return _error(
        'Invalid config action or data',
        400,
        valid_actions=[action.value for action in ConfigAction],
    )


@app.route('/api/login', methods=['POST'])
def login():
    if not request.is_json:
        return _error('JSON data required', 400)
    data = request.get_json()
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


def _run_operation(operation: OperationType):
    if operation == OperationType.LIST_CONFIG:
        return jsonify({'result': config_manager.get_secure_config()})
    if operation == OperationType.SYSTEM_INFO:
        return jsonify({'result': {
            'system_time': datetime.now().isoformat(),
            'config_summary': {
                'debug_mode': config_manager.config['debug'],
                'num_allowed_hosts': len(config_manager.config['allowed_hosts']),
            },
        }})
    if operation == OperationType.TIME:
        return jsonify({'result': {'current_time': datetime.now().isoformat()}})
    return _error('Operation not implemented', 400)


@app.route('/api/execute', methods=['POST'])
def execute_operation():
    if not request.is_json:
        return _error('JSON data required', 400)
    data = request.get_json()
    if 'operation' not in data:
        return _error('Operation required', 400)
    try:
        operation = OperationType(data['operation'])
    except ValueError:
        return _error(
            'Invalid operation',
            400,
            valid_operations=[op.value for op in OperationType],
        )
    return _run_operation(operation)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
