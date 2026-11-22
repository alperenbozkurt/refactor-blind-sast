import pickle
import socket
import sys
import hashlib
from datetime import datetime

# --- Constants -------------------------------------------------------------

DEFAULT_HOSTNAME = 'unknown'
DEFAULT_DEVICE_ID = 'unknown'
RECV_BUFFER_SIZE = 4096
DEFAULT_AUDIT_LIMIT = 10
DEFAULT_HISTORY_LIMIT = 5
REMOTE_UPDATE_ACTION = 'remote_update'

MENU_LOAD = '1'
MENU_SAVE = '2'
MENU_AUDIT = '3'
MENU_EXIT = '4'

MENU_TEXT_LINES = (
    '\n1. Load config from network',
    '2. Save config to file',
    '3. View audit log',
    '4. Exit',
)


# --- Helpers ---------------------------------------------------------------

def _now():
    return datetime.now()


def _hash_device_state(device):
    return hashlib.sha256(str(device.__dict__).encode()).hexdigest()


def _deserialize_config(data):
    # NOTE: pickle is unsafe with untrusted input; behaviour is preserved
    # intentionally. Consider replacing with a safe format (e.g. JSON).
    return pickle.loads(data)


def _receive_raw_config(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        return s.recv(RECV_BUFFER_SIZE)


# --- Domain classes --------------------------------------------------------

class DeviceConfig:

    def __init__(self):
        self.hostname = DEFAULT_HOSTNAME
        self.interfaces = {}
        self.routing_table = []
        self.credentials = {}
        self.last_backup = None


class NetworkManager:

    def __init__(self):
        self.devices = {}
        self.config_history = []
        self.audit_log = []

    # -- Remote loading --

    def load_config_from_network(self, host, port):
        try:
            data = _receive_raw_config(host, port)
            return self._process_remote_config(data)
        except Exception as e:
            self._log_audit(f'Error loading config from {host}:{port} - {str(e)}')
            return False

    def _process_remote_config(self, data):
        try:
            config = _deserialize_config(data)
            return self._apply_network_config(config)
        except Exception as e:
            self._log_audit(f'Config processing error: {str(e)}')
            return False

    def _get_or_create_device(self, device_id):
        if device_id not in self.devices:
            self.devices[device_id] = DeviceConfig()
        return self.devices[device_id]

    def _apply_network_config(self, config):
        device_id = config.get('device_id', DEFAULT_DEVICE_ID)
        device = self._get_or_create_device(device_id)
        device.hostname = config.get('hostname', device.hostname)
        device.interfaces = config.get('interfaces', device.interfaces)
        device.routing_table = config.get('routing_table', device.routing_table)
        if 'credentials' in config:
            device.credentials.update(config['credentials'])
        device.last_backup = _now()
        self._log_config_change(device_id, REMOTE_UPDATE_ACTION)
        return True

    # -- Saving --

    def _build_export_config(self, device_id):
        device = self.devices[device_id]
        return {
            'device_id': device_id,
            'hostname': device.hostname,
            'interfaces': device.interfaces,
            'routing_table': device.routing_table,
            'credentials': device.credentials,
            'timestamp': _now().isoformat(),
        }

    def save_config_to_file(self, device_id, filename):
        if device_id not in self.devices:
            return False
        config = self._build_export_config(device_id)
        try:
            with open(filename, 'wb') as f:
                pickle.dump(config, f)
            self._log_audit(f'Saved config for {device_id} to {filename}')
            return True
        except Exception as e:
            self._log_audit(f'Failed to save config: {str(e)}')
            return False

    # -- Logging --

    def _log_config_change(self, device_id, action):
        entry = {
            'timestamp': _now(),
            'device': device_id,
            'action': action,
            'hash': _hash_device_state(self.devices[device_id]),
        }
        self.config_history.append(entry)

    def _log_audit(self, message):
        entry = {'timestamp': _now(), 'message': message}
        self.audit_log.append(entry)

    def get_audit_log(self, limit=DEFAULT_AUDIT_LIMIT):
        return self.audit_log[-limit:]

    def get_config_history(self, device_id, limit=DEFAULT_HISTORY_LIMIT):
        return [entry for entry in self.config_history if entry['device'] == device_id][-limit:]


# --- CLI -------------------------------------------------------------------

def _print_menu():
    for line in MENU_TEXT_LINES:
        print(line)


def _handle_load(manager):
    host = input('Enter host: ')
    port = int(input('Enter port: '))
    if manager.load_config_from_network(host, port):
        print('Configuration loaded successfully')
    else:
        print('Failed to load configuration')


def _handle_save(manager):
    device_id = input('Enter device ID: ')
    filename = input('Enter filename: ')
    if manager.save_config_to_file(device_id, filename):
        print('Configuration saved successfully')
    else:
        print('Failed to save configuration')


def _handle_view_audit(manager):
    for entry in manager.get_audit_log():
        print(f"{entry['timestamp']}: {entry['message']}")


def _handle_exit(manager):
    sys.exit(0)


MENU_HANDLERS = {
    MENU_LOAD: _handle_load,
    MENU_SAVE: _handle_save,
    MENU_AUDIT: _handle_view_audit,
    MENU_EXIT: _handle_exit,
}


def main():
    manager = NetworkManager()
    print('Network Configuration Manager started')
    while True:
        _print_menu()
        choice = input('Select option: ')
        handler = MENU_HANDLERS.get(choice)
        if handler is None:
            print('Invalid option')
        else:
            handler(manager)


if __name__ == '__main__':
    main()
