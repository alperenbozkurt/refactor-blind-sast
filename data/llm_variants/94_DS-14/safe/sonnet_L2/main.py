import yaml
from flask import Flask, request, jsonify
import json
import hashlib
from datetime import datetime
from enum import Enum
from typing import Dict, Any

app = Flask(__name__)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
SERVER_DEBUG = False

CONFIG_KEY_DEBUG = 'debug'
CONFIG_KEY_MAX_CONNECTIONS = 'max_connections'
CONFIG_KEY_ALLOWED_HOSTS = 'allowed_hosts'
CONFIG_KEY_API_KEYS = 'api_keys'

DEFAULT_DEBUG = False
DEFAULT_MAX_CONNECTIONS = 10
DEFAULT_ALLOWED_HOSTS = ('localhost',)

CONFIG_FILE_INDENT = 2

HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401

ERR_JSON_REQUIRED = 'JSON data required'
ERR_ACTION_DATA_REQUIRED = 'Action and data required'
ERR_INVALID_CONFIG_ACTION = 'Invalid config action or data'
ERR_CREDENTIALS_REQUIRED = 'Username and password required'
ERR_INVALID_CREDENTIALS = 'Invalid credentials'
ERR_OPERATION_REQUIRED = 'Operation required'
ERR_OPERATION_NOT_IMPLEMENTED = 'Operation not implemented'
ERR_INVALID_OPERATION = 'Invalid operation'

MSG_CONFIG_UPDATED = 'Config updated'
MSG_LOGIN_SUCCESS = 'Login successful'


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _now_iso() -> str:
    return datetime.now().isoformat()


def _error_response(message: str, status: int, **extra: Any):
    payload = {'error': message}
    payload.update(extra)
    return (jsonify(payload), status)


def _default_config() -> Dict[str, Any]:
    return {
        CONFIG_KEY_DEBUG: DEFAULT_DEBUG,
        CONFIG_KEY_MAX_CONNECTIONS: DEFAULT_MAX_CONNECTIONS,
        CONFIG_KEY_ALLOWED_HOSTS: list(DEFAULT_ALLOWED_HOSTS),
        CONFIG_KEY_API_KEYS: [],
    }


# --------------------------------------------------------------------------- #
# Configuration management
# --------------------------------------------------------------------------- #

class ConfigAction(Enum):
    SET_DEBUG = 'set_debug'
    SET_MAX_CONNECTIONS = 'set_max_connections'
    ADD_ALLOWED_HOST = 'add_allowed_host'
    REMOVE_ALLOWED_HOST = 'remove_allowed_host'


class ConfigManager:

    def __init__(self):
        self.config = _default_config()

    # -- individual action handlers ---------------------------------------- #

    def _set_debug(self, data: Any) -> bool:
        if isinstance(data, bool):
            self.config[CONFIG_KEY_DEBUG] = data
            return True
        return False

    def _set_max_connections(self, data: Any) -> bool:
        if isinstance(data, int) and data > 0:
            self.config[CONFIG_KEY_MAX_CONNECTIONS] = data
            return True
        return False

    def _add_allowed_host(self, data: Any) -> bool:
        hosts = self.config[CONFIG_KEY_ALLOWED_HOSTS]
        if isinstance(data, str) and data not in hosts:
            hosts.append(data)
            return True
        return False

    def _remove_allowed_host(self, data: Any) -> bool:
        hosts = self.config[CONFIG_KEY_ALLOWED_HOSTS]
        if isinstance(data, str) and data in hosts:
            hosts.remove(data)
            return True
        return False

    def _get_handler(self, action: ConfigAction):
        handlers = {
            ConfigAction.SET_DEBUG: self._set_debug,
            ConfigAction.SET_MAX_CONNECTIONS: self._set_max_connections,
            ConfigAction.ADD_ALLOWED_HOST: self._add_allowed_host,
            ConfigAction.REMOVE_ALLOWED_HOST: self._remove_allowed_host,
        }
        return handlers.get(action)

    # -- public API -------------------------------------------------------- #

    def update_config(self, action: str, data: Any) -> bool:
        try:
            action = ConfigAction(action)
        except ValueError:
            return False
        handler = self._get_handler(action)
        if handler is None:
            return False
        return handler(data)

    def save_config(self, filename: str) -> None:
        with open(filename, 'w') as f:
            json.dump(self.config, f, indent=CONFIG_FILE_INDENT)

    def get_secure_config(self) -> Dict[str, Any]:
        safe_config = self.config.copy()
        safe_config.pop(CONFIG_KEY_API_KEYS, None)
        return safe_config


# --------------------------------------------------------------------------- #
# User management
# --------------------------------------------------------------------------- #

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


# --------------------------------------------------------------------------- #
# Operations
# --------------------------------------------------------------------------- #

class OperationType(Enum):
    LIST_CONFIG = 'list_config'
    SYSTEM_INFO = 'system_info'
    TIME = 'time'


config_manager = ConfigManager()
user_manager = UserManager()


def _op_list_config() -> Dict[str, Any]:
    return config_manager.get_secure_config()


def _op_system_info() -> Dict[str, Any]:
    return {
        'system_time': _now_iso(),
        'config_summary': {
            'debug_mode': config_manager.config[CONFIG_KEY_DEBUG],
            'num_allowed_hosts': len(config_manager.config[CONFIG_KEY_ALLOWED_HOSTS]),
        },
    }


def _op_time() -> Dict[str, Any]:
    return {'current_time': _now_iso()}


def _get_operation_handlers():
    return {
        OperationType.LIST_CONFIG: _op_list_config,
        OperationType.SYSTEM_INFO: _op_system_info,
        OperationType.TIME: _op_time,
    }


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    if request.method == 'GET':
        return jsonify(config_manager.get_secure_config())
    if not request.is_json:
        return _error_response(ERR_JSON_REQUIRED, HTTP_BAD_REQUEST)
    data = request.get_json()
    if 'action' not in data or 'data' not in data:
        return _error_response(ERR_ACTION_DATA_REQUIRED, HTTP_BAD_REQUEST)
    if config_manager.update_config(data['action'], data['data']):
        return jsonify({'status': MSG_CONFIG_UPDATED})
    return _error_response(
        ERR_INVALID_CONFIG_ACTION,
        HTTP_BAD_REQUEST,
        valid_actions=[action.value for action in ConfigAction],
    )


@app.route('/api/login', methods=['POST'])
def login():
    if not request.is_json:
        return _error_response(ERR_JSON_REQUIRED, HTTP_BAD_REQUEST)
    data = request.get_json()
    if 'username' not in data or 'password' not in data:
        return _error_response(ERR_CREDENTIALS_REQUIRED, HTTP_BAD_REQUEST)
    user = user_manager.validate_user(data['username'], data['password'])
    if not user:
        return _error_response(ERR_INVALID_CREDENTIALS, HTTP_UNAUTHORIZED)
    return jsonify({
        'message': MSG_LOGIN_SUCCESS,
        'user': {
            'username': data['username'],
            'role': user['role'],
            'login_time': _now_iso(),
        },
    })


@app.route('/api/execute', methods=['POST'])
def execute_operation():
    if not request.is_json:
        return _error_response(ERR_JSON_REQUIRED, HTTP_BAD_REQUEST)
    data = request.get_json()
    if 'operation' not in data:
        return _error_response(ERR_OPERATION_REQUIRED, HTTP_BAD_REQUEST)
    try:
        operation = OperationType(data['operation'])
        handler = _get_operation_handlers().get(operation)
        if handler is None:
            return _error_response(ERR_OPERATION_NOT_IMPLEMENTED, HTTP_BAD_REQUEST)
        return jsonify({'result': handler()})
    except ValueError:
        return _error_response(
            ERR_INVALID_OPERATION,
            HTTP_BAD_REQUEST,
            valid_operations=[op.value for op in OperationType],
        )


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)
