"""Network device configuration manager.

Provides data classes for device configuration state, a manager class that
handles loading/saving configurations with audit logging, and an
interactive command-line interface.
"""

import hashlib
import pickle
import socket
import sys
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DEFAULT_HOSTNAME = 'unknown'
DEFAULT_DEVICE_ID = 'unknown'

RECV_BUFFER_SIZE = 4096
CONFIG_FILE_MODE = 'wb'

DEFAULT_AUDIT_LOG_LIMIT = 10
DEFAULT_CONFIG_HISTORY_LIMIT = 5

ACTION_REMOTE_UPDATE = 'remote_update'

# ---------------------------------------------------------------------------
# CLI text constants
# ---------------------------------------------------------------------------

CLI_BANNER = 'Network Configuration Manager started'
CLI_MENU_ITEMS = (
    '1. Load config from network',
    '2. Save config to file',
    '3. View audit log',
    '4. Exit',
)
CLI_PROMPT = 'Select option: '
CLI_INVALID_OPTION = 'Invalid option'

CLI_PROMPT_HOST = 'Enter host: '
CLI_PROMPT_PORT = 'Enter port: '
CLI_PROMPT_DEVICE_ID = 'Enter device ID: '
CLI_PROMPT_FILENAME = 'Enter filename: '

CLI_LOAD_SUCCESS = 'Configuration loaded successfully'
CLI_LOAD_FAILURE = 'Failed to load configuration'
CLI_SAVE_SUCCESS = 'Configuration saved successfully'
CLI_SAVE_FAILURE = 'Failed to save configuration'


class DeviceConfig:
    """Holds the configuration state for a single network device."""

    def __init__(self):
        self.hostname = DEFAULT_HOSTNAME
        self.interfaces = {}
        self.routing_table = []
        self.credentials = {}
        self.last_backup = None


class NetworkManager:
    """Manages device configurations, config history, and audit logging."""

    def __init__(self):
        self.devices = {}
        self.config_history = []
        self.audit_log = []

    # -- Remote configuration loading -------------------------------------

    def load_config_from_network(self, host, port):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((host, port))
                data = sock.recv(RECV_BUFFER_SIZE)
                return self._process_remote_config(data)
        except Exception as e:
            self._log_audit(f'Error loading config from {host}:{port} - {str(e)}')
            return False

    def _process_remote_config(self, data):
        try:
            config = pickle.loads(data)
            return self._apply_network_config(config)
        except Exception as e:
            self._log_audit(f'Config processing error: {str(e)}')
            return False

    def _apply_network_config(self, config):
        device_id = config.get('device_id', DEFAULT_DEVICE_ID)
        device = self._get_or_create_device(device_id)
        device.hostname = config.get('hostname', device.hostname)
        device.interfaces = config.get('interfaces', device.interfaces)
        device.routing_table = config.get('routing_table', device.routing_table)
        if 'credentials' in config:
            device.credentials.update(config['credentials'])
        device.last_backup = datetime.now()
        self._log_config_change(device_id, ACTION_REMOTE_UPDATE)
        return True

    def _get_or_create_device(self, device_id):
        if device_id not in self.devices:
            self.devices[device_id] = DeviceConfig()
        return self.devices[device_id]

    # -- Configuration persistence -----------------------------------------

    def save_config_to_file(self, device_id, filename):
        if device_id not in self.devices:
            return False
        config = self._build_config_snapshot(device_id)
        try:
            with open(filename, CONFIG_FILE_MODE) as f:
                pickle.dump(config, f)
            self._log_audit(f'Saved config for {device_id} to {filename}')
            return True
        except Exception as e:
            self._log_audit(f'Failed to save config: {str(e)}')
            return False

    def _build_config_snapshot(self, device_id):
        device = self.devices[device_id]
        return {
            'device_id': device_id,
            'hostname': device.hostname,
            'interfaces': device.interfaces,
            'routing_table': device.routing_table,
            'credentials': device.credentials,
            'timestamp': datetime.now().isoformat(),
        }

    # -- Logging -----------------------------------------------------------

    def _log_config_change(self, device_id, action):
        entry = {
            'timestamp': datetime.now(),
            'device': device_id,
            'action': action,
            'hash': self._compute_config_hash(device_id),
        }
        self.config_history.append(entry)

    def _compute_config_hash(self, device_id):
        state = str(self.devices[device_id].__dict__).encode()
        return hashlib.sha256(state).hexdigest()

    def _log_audit(self, message):
        entry = {'timestamp': datetime.now(), 'message': message}
        self.audit_log.append(entry)

    # -- Log access ---------------------------------------------------------

    def get_audit_log(self, limit=DEFAULT_AUDIT_LOG_LIMIT):
        return self.audit_log[-limit:]

    def get_config_history(self, device_id, limit=DEFAULT_CONFIG_HISTORY_LIMIT):
        matching = [entry for entry in self.config_history if entry['device'] == device_id]
        return matching[-limit:]


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def _print_menu():
    print()
    for item in CLI_MENU_ITEMS:
        print(item)


def _handle_load_config(manager):
    host = input(CLI_PROMPT_HOST)
    port = int(input(CLI_PROMPT_PORT))
    if manager.load_config_from_network(host, port):
        print(CLI_LOAD_SUCCESS)
    else:
        print(CLI_LOAD_FAILURE)


def _handle_save_config(manager):
    device_id = input(CLI_PROMPT_DEVICE_ID)
    filename = input(CLI_PROMPT_FILENAME)
    if manager.save_config_to_file(device_id, filename):
        print(CLI_SAVE_SUCCESS)
    else:
        print(CLI_SAVE_FAILURE)


def _handle_view_audit_log(manager):
    for entry in manager.get_audit_log():
        print(f"{entry['timestamp']}: {entry['message']}")


def _handle_exit(manager):
    sys.exit(0)


_CLI_HANDLERS = {
    '1': _handle_load_config,
    '2': _handle_save_config,
    '3': _handle_view_audit_log,
    '4': _handle_exit,
}


def main():
    manager = NetworkManager()
    print(CLI_BANNER)
    while True:
        _print_menu()
        choice = input(CLI_PROMPT)
        handler = _CLI_HANDLERS.get(choice)
        if handler is None:
            print(CLI_INVALID_OPTION)
        else:
            handler(manager)


if __name__ == '__main__':
    main()
