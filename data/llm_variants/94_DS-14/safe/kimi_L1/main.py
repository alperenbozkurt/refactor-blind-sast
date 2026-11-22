import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict

import yaml  # noqa: F401  (kept intentionally; part of the module's public surface)
from flask import Flask, jsonify, request

app = Flask(__name__)


class ConfigAction(Enum):
    """Supported configuration update actions."""

    SET_DEBUG = "set_debug"
    SET_MAX_CONNECTIONS = "set_max_connections"
    ADD_ALLOWED_HOST = "add_allowed_host"
    REMOVE_ALLOWED_HOST = "remove_allowed_host"


class ConfigManager:
    """Stores the application configuration and applies updates to it."""

    def __init__(self):
        self.config = {
            "debug": False,
            "max_connections": 10,
            "allowed_hosts": ["localhost"],
            "api_keys": [],
        }

    def update_config(self, action: str, data: Any) -> bool:
        """Apply the given action; return True only if it succeeded."""
        try:
            action = ConfigAction(action)
            if action == ConfigAction.SET_DEBUG:
                return self._set_debug(data)
            if action == ConfigAction.SET_MAX_CONNECTIONS:
                return self._set_max_connections(data)
            if action == ConfigAction.ADD_ALLOWED_HOST:
                return self._add_allowed_host(data)
            if action == ConfigAction.REMOVE_ALLOWED_HOST:
                return self._remove_allowed_host(data)
            return False
        except ValueError:
            return False

    def _set_debug(self, data: Any) -> bool:
        if isinstance(data, bool):
            self.config["debug"] = data
            return True
        return False

    def _set_max_connections(self, data: Any) -> bool:
        if isinstance(data, int) and data > 0:
            self.config["max_connections"] = data
            return True
        return False

    def _add_allowed_host(self, data: Any) -> bool:
        if isinstance(data, str) and data not in self.config["allowed_hosts"]:
            self.config["allowed_hosts"].append(data)
            return True
        return False

    def _remove_allowed_host(self, data: Any) -> bool:
        if isinstance(data, str) and data in self.config["allowed_hosts"]:
            self.config["allowed_hosts"].remove(data)
            return True
        return False

    def save_config(self, filename: str) -> None:
        """Write the full configuration to a JSON file."""
        with open(filename, "w") as f:
            json.dump(self.config, f, indent=2)

    def get_secure_config(self) -> Dict[str, Any]:
        """Return a copy of the configuration with sensitive keys removed."""
        safe_config = self.config.copy()
        safe_config.pop("api_keys", None)
        return safe_config


class UserManager:
    """Stores user records and validates credentials."""

    def __init__(self):
        self.users = {
            "admin": {
                "password": self._hash_password("admin123"),
                "role": "admin",
            },
            "user1": {
                "password": self._hash_password("password1"),
                "role": "user",
            },
        }

    def validate_user(self, username: str, password: str) -> Dict[str, Any]:
        """Return the stored user record when the credentials match."""
        user = self.users.get(username)
        if user and user["password"] == self._hash_password(password):
            return user
        return None

    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()


class OperationType(Enum):
    """Operations supported by the /api/execute endpoint."""

    LIST_CONFIG = "list_config"
    SYSTEM_INFO = "system_info"
    TIME = "time"


config_manager = ConfigManager()
user_manager = UserManager()


@app.route("/api/config", methods=["GET", "POST"])
def handle_config():
    if request.method == "GET":
        return jsonify(config_manager.get_secure_config())

    if not request.is_json:
        return jsonify({"error": "JSON data required"}), 400

    data = request.get_json()
    if "action" not in data or "data" not in data:
        return jsonify({"error": "Action and data required"}), 400

    if config_manager.update_config(data["action"], data["data"]):
        return jsonify({"status": "Config updated"})

    return (
        jsonify(
            {
                "error": "Invalid config action or data",
                "valid_actions": [action.value for action in ConfigAction],
            }
        ),
        400,
    )


@app.route("/api/login", methods=["POST"])
def login():
    if not request.is_json:
        return jsonify({"error": "JSON data required"}), 400

    data = request.get_json()
    if "username" not in data or "password" not in data:
        return jsonify({"error": "Username and password required"}), 400

    user = user_manager.validate_user(data["username"], data["password"])
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    return jsonify(
        {
            "message": "Login successful",
            "user": {
                "username": data["username"],
                "role": user["role"],
                "login_time": datetime.now().isoformat(),
            },
        }
    )


@app.route("/api/execute", methods=["POST"])
def execute_operation():
    if not request.is_json:
        return jsonify({"error": "JSON data required"}), 400

    data = request.get_json()
    if "operation" not in data:
        return jsonify({"error": "Operation required"}), 400

    try:
        operation = OperationType(data["operation"])
        if operation == OperationType.LIST_CONFIG:
            return jsonify({"result": config_manager.get_secure_config()})
        elif operation == OperationType.SYSTEM_INFO:
            return jsonify(
                {
                    "result": {
                        "system_time": datetime.now().isoformat(),
                        "config_summary": {
                            "debug_mode": config_manager.config["debug"],
                            "num_allowed_hosts": len(
                                config_manager.config["allowed_hosts"]
                            ),
                        },
                    }
                }
            )
        elif operation == OperationType.TIME:
            return jsonify({"result": {"current_time": datetime.now().isoformat()}})
        return jsonify({"error": "Operation not implemented"}), 400
    except ValueError:
        return (
            jsonify(
                {
                    "error": "Invalid operation",
                    "valid_operations": [op.value for op in OperationType],
                }
            ),
            400,
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
