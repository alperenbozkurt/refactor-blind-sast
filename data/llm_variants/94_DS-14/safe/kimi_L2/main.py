"""Configuration and operations web service.

This module keeps the original public interface and behaviour intact while
organising the implementation into named constants, small helper functions
and dispatch tables so it is easier to maintain and extend.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Tuple

import yaml  # noqa: F401  (retained to preserve the original module namespace)
from flask import Flask, jsonify, request

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

# Configuration keys
CONFIG_KEY_DEBUG = 'debug'
CONFIG_KEY_MAX_CONNECTIONS = 'max_connections'
CONFIG_KEY_ALLOWED_HOSTS = 'allowed_hosts'
CONFIG_KEY_API_KEYS = 'api_keys'

# Configuration defaults
DEFAULT_DEBUG = False
DEFAULT_MAX_CONNECTIONS = 10
DEFAULT_ALLOWED_HOST = 'localhost'
CONFIG_DUMP_INDENT = 2

# Default user accounts: (username, plain-text password, role)
DEFAULT_USER_CREDENTIALS = (
    ('admin', 'admin123', 'admin'),
    ('user1', 'password1', 'user'),
)

# HTTP status codes
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401

# Error messages
ERROR_JSON_REQUIRED = 'JSON data required'
ERROR_ACTION_AND_DATA_REQUIRED = 'Action and data required'
ERROR_INVALID_CONFIG_ACTION = 'Invalid config action or data'
ERROR_CREDENTIALS_REQUIRED = 'Username and password required'
ERROR_INVALID_CREDENTIALS = 'Invalid credentials'
ERROR_OPERATION_REQUIRED = 'Operation required'
ERROR_INVALID_OPERATION = 'Invalid operation'
ERROR_OPERATION_NOT_IMPLEMENTED = 'Operation not implemented'

# Success messages
STATUS_CONFIG_UPDATED = 'Config updated'
MESSAGE_LOGIN_SUCCESSFUL = 'Login successful'


@dataclass(frozen=True)
class ServerConfig:
    """Network settings used when running the built-in web server."""

    host: str = '0.0.0.0'
    port: int = 5000
    debug: bool = False


SERVER_CONFIG = ServerConfig()

# ---------------------------------------------------------------------------
# Small generic helpers
# ---------------------------------------------------------------------------

# Sentinel distinguishing "request has no JSON body" from a JSON ``null`` body.
_NOT_JSON = object()


def _hash_password(password: str) -> str:
    """Return the SHA-256 hex digest of ``password``."""
    return hashlib.sha256(password.encode()).hexdigest()


def _current_timestamp() -> str:
    """Return the current local time as an ISO-8601 string."""
    return datetime.now().isoformat()


def _enum_values(enum_class) -> list:
    """Return the list of values defined by an Enum class."""
    return [member.value for member in enum_class]


def _json_request_data() -> Any:
    """Return the parsed JSON body, or the ``_NOT_JSON`` sentinel when the
    request does not carry a JSON body."""
    if not request.is_json:
        return _NOT_JSON
    return request.get_json()


def _missing_required_fields(payload: Any, *required_fields: str) -> bool:
    """Return True when any of ``required_fields`` is absent from ``payload``."""
    return any(field not in payload for field in required_fields)


def _error_response(message: str, status_code: int, **extra_fields: Any) -> Tuple[Any, int]:
    """Build a JSON error response body together with its HTTP status code."""
    body = {'error': message}
    body.update(extra_fields)
    return jsonify(body), status_code


# ---------------------------------------------------------------------------
# Domain enums
# ---------------------------------------------------------------------------

class ConfigAction(Enum):
    SET_DEBUG = 'set_debug'
    SET_MAX_CONNECTIONS = 'set_max_connections'
    ADD_ALLOWED_HOST = 'add_allowed_host'
    REMOVE_ALLOWED_HOST = 'remove_allowed_host'


# ---------------------------------------------------------------------------
# Managers
# ---------------------------------------------------------------------------

class ConfigManager:
    """Holds the runtime configuration and applies validated updates."""

    def __init__(self):
        self.config = self._build_initial_config()
        self._action_handlers: Dict[ConfigAction, Callable[[Any], bool]] = {
            ConfigAction.SET_DEBUG: self._set_debug,
            ConfigAction.SET_MAX_CONNECTIONS: self._set_max_connections,
            ConfigAction.ADD_ALLOWED_HOST: self._add_allowed_host,
            ConfigAction.REMOVE_ALLOWED_HOST: self._remove_allowed_host,
        }

    @staticmethod
    def _build_initial_config() -> Dict[str, Any]:
        return {
            CONFIG_KEY_DEBUG: DEFAULT_DEBUG,
            CONFIG_KEY_MAX_CONNECTIONS: DEFAULT_MAX_CONNECTIONS,
            CONFIG_KEY_ALLOWED_HOSTS: [DEFAULT_ALLOWED_HOST],
            CONFIG_KEY_API_KEYS: [],
        }

    def update_config(self, action: str, data: Any) -> bool:
        try:
            parsed_action = ConfigAction(action)
        except ValueError:
            return False
        return self._action_handlers[parsed_action](data)

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
        if isinstance(data, str) and data not in self.config[CONFIG_KEY_ALLOWED_HOSTS]:
            self.config[CONFIG_KEY_ALLOWED_HOSTS].append(data)
            return True
        return False

    def _remove_allowed_host(self, data: Any) -> bool:
        if isinstance(data, str) and data in self.config[CONFIG_KEY_ALLOWED_HOSTS]:
            self.config[CONFIG_KEY_ALLOWED_HOSTS].remove(data)
            return True
        return False

    def save_config(self, filename: str) -> None:
        with open(filename, 'w') as f:
            json.dump(self.config, f, indent=CONFIG_DUMP_INDENT)

    def get_secure_config(self) -> Dict[str, Any]:
        safe_config = self.config.copy()
        safe_config.pop(CONFIG_KEY_API_KEYS, None)
        return safe_config


class UserManager:
    """Stores user credentials and validates login attempts."""

    def __init__(self):
        self.users = self._build_initial_users()

    @staticmethod
    def _build_initial_users() -> Dict[str, Dict[str, str]]:
        return {
            username: {'password': _hash_password(password), 'role': role}
            for username, password, role in DEFAULT_USER_CREDENTIALS
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

# ---------------------------------------------------------------------------
# Operation handlers
# ---------------------------------------------------------------------------

def _operation_list_config() -> Any:
    return jsonify({'result': config_manager.get_secure_config()})


def _operation_system_info() -> Any:
    return jsonify({
        'result': {
            'system_time': _current_timestamp(),
            'config_summary': {
                'debug_mode': config_manager.config[CONFIG_KEY_DEBUG],
                'num_allowed_hosts': len(config_manager.config[CONFIG_KEY_ALLOWED_HOSTS]),
            },
        },
    })


def _operation_time() -> Any:
    return jsonify({'result': {'current_time': _current_timestamp()}})


_OPERATION_HANDLERS: Dict[OperationType, Callable[[], Any]] = {
    OperationType.LIST_CONFIG: _operation_list_config,
    OperationType.SYSTEM_INFO: _operation_system_info,
    OperationType.TIME: _operation_time,
}

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    if request.method == 'GET':
        return jsonify(config_manager.get_secure_config())

    data = _json_request_data()
    if data is _NOT_JSON:
        return _error_response(ERROR_JSON_REQUIRED, HTTP_BAD_REQUEST)
    if _missing_required_fields(data, 'action', 'data'):
        return _error_response(ERROR_ACTION_AND_DATA_REQUIRED, HTTP_BAD_REQUEST)

    if config_manager.update_config(data['action'], data['data']):
        return jsonify({'status': STATUS_CONFIG_UPDATED})
    return _error_response(
        ERROR_INVALID_CONFIG_ACTION,
        HTTP_BAD_REQUEST,
        valid_actions=_enum_values(ConfigAction),
    )


@app.route('/api/login', methods=['POST'])
def login():
    data = _json_request_data()
    if data is _NOT_JSON:
        return _error_response(ERROR_JSON_REQUIRED, HTTP_BAD_REQUEST)
    if _missing_required_fields(data, 'username', 'password'):
        return _error_response(ERROR_CREDENTIALS_REQUIRED, HTTP_BAD_REQUEST)

    user = user_manager.validate_user(data['username'], data['password'])
    if not user:
        return _error_response(ERROR_INVALID_CREDENTIALS, HTTP_UNAUTHORIZED)
    return jsonify({
        'message': MESSAGE_LOGIN_SUCCESSFUL,
        'user': {
            'username': data['username'],
            'role': user['role'],
            'login_time': _current_timestamp(),
        },
    })


@app.route('/api/execute', methods=['POST'])
def execute_operation():
    data = _json_request_data()
    if data is _NOT_JSON:
        return _error_response(ERROR_JSON_REQUIRED, HTTP_BAD_REQUEST)
    if _missing_required_fields(data, 'operation'):
        return _error_response(ERROR_OPERATION_REQUIRED, HTTP_BAD_REQUEST)

    try:
        operation = OperationType(data['operation'])
    except ValueError:
        return _error_response(
            ERROR_INVALID_OPERATION,
            HTTP_BAD_REQUEST,
            valid_operations=_enum_values(OperationType),
        )

    handler = _OPERATION_HANDLERS.get(operation)
    if handler is None:
        return _error_response(ERROR_OPERATION_NOT_IMPLEMENTED, HTTP_BAD_REQUEST)
    return handler()


if __name__ == '__main__':
    app.run(host=SERVER_CONFIG.host, port=SERVER_CONFIG.port, debug=SERVER_CONFIG.debug)
