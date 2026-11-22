import pickle
import socket
import sys
import hashlib
from datetime import datetime

RECV_BUFFER_SIZE = 4096

MENU_TEXT = (
    '\n1. Load config from network',
    '2. Save config to file',
    '3. View audit log',
    '4. Exit',
)


class DeviceConfig:
    """Configuration state for a single network device."""

    def __init__(self):
        self.hostname = 'unknown'
        self.interfaces = {}
        self.routing_table = []
        self.credentials = {}
        self.last_backup = None


class NetworkManager:
    """Manages device configurations, their history and an audit log."""

    def __init__(self):
        self.devices = {}
        self.config_history = []
        self.audit_log = []

    # ------------------------------------------------------------------
    # Loading configuration from the network
    # ------------------------------------------------------------------
    def load_config_from_network(self, host, port):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((host, port))
                data = s.recv(RECV_BUFFER_SIZE)
                return self._process_remote_config(data)
        except Exception as e:
            self._log_audit(f'Error loading config from {host}:{port} - {e}')
            return False

    def _process_remote_config(self, data):
        try:
            # NOTE: pickle is retained to preserve the existing wire format
            # and behaviour; unpickling data from untrusted sources is unsafe.
            config = pickle.loads(data)
            return self._apply_network_config(config)
        except Exception as e:
            self._log_audit(f'Config processing error: {e}')
            return False

    def _apply_network_config(self, config):
        device_id = config.get('device_id', 'unknown')
        if device_id not in self.devices:
            self.devices[device_id] = DeviceConfig()
        device = self.devices[device_id]

        device.hostname = config.get('hostname', device.hostname)
        device.interfaces = config.get('interfaces', device.interfaces)
        device.routing_table = config.get('routing_table', device.routing_table)
        if 'credentials' in config:
            device.credentials.update(config['credentials'])
        device.last_backup = datetime.now()

        self._log_config_change(device_id, 'remote_update')
        return True

    # ------------------------------------------------------------------
    # Saving configuration to a file
    # ------------------------------------------------------------------
    def save_config_to_file(self, device_id, filename):
        if device_id not in self.devices:
            return False

        config = self._build_config_snapshot(device_id)
        try:
            with open(filename, 'wb') as f:
                pickle.dump(config, f)
            self._log_audit(f'Saved config for {device_id} to {filename}')
            return True
        except Exception as e:
            self._log_audit(f'Failed to save config: {e}')
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

    # ------------------------------------------------------------------
    # Logging and history
    # ------------------------------------------------------------------
    def _log_config_change(self, device_id, action):
        device_state = str(self.devices[device_id].__dict__)
        entry = {
            'timestamp': datetime.now(),
            'device': device_id,
            'action': action,
            'hash': hashlib.sha256(device_state.encode()).hexdigest(),
        }
        self.config_history.append(entry)

    def _log_audit(self, message):
        entry = {'timestamp': datetime.now(), 'message': message}
        self.audit_log.append(entry)

    def get_audit_log(self, limit=10):
        return self.audit_log[-limit:]

    def get_config_history(self, device_id, limit=5):
        device_entries = [
            entry for entry in self.config_history
            if entry['device'] == device_id
        ]
        return device_entries[-limit:]


# ----------------------------------------------------------------------
# Command-line interface
# ----------------------------------------------------------------------
def _handle_load_config(manager):
    host = input('Enter host: ')
    port = int(input('Enter port: '))
    if manager.load_config_from_network(host, port):
        print('Configuration loaded successfully')
    else:
        print('Failed to load configuration')


def _handle_save_config(manager):
    device_id = input('Enter device ID: ')
    filename = input('Enter filename: ')
    if manager.save_config_to_file(device_id, filename):
        print('Configuration saved successfully')
    else:
        print('Failed to save configuration')


def _handle_view_audit_log(manager):
    for entry in manager.get_audit_log():
        print(f"{entry['timestamp']}: {entry['message']}")


def main():
    manager = NetworkManager()
    print('Network Configuration Manager started')

    handlers = {
        '1': _handle_load_config,
        '2': _handle_save_config,
        '3': _handle_view_audit_log,
    }

    while True:
        for line in MENU_TEXT:
            print(line)
        choice = input('Select option: ')

        if choice in handlers:
            handlers[choice](manager)
        elif choice == '4':
            sys.exit(0)
        else:
            print('Invalid option')


if __name__ == '__main__':
    main()
