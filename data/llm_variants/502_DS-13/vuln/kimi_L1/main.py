"""Network device configuration manager.

Loads device configurations from a network socket, saves them to disk,
and maintains a configuration history and audit log.
"""

import hashlib
import pickle
import socket
import sys
from datetime import datetime


class DeviceConfig:
    """Configuration and state for a single network device."""

    def __init__(self):
        self.hostname = 'unknown'
        self.interfaces = {}
        self.routing_table = []
        self.credentials = {}
        self.last_backup = None


class NetworkManager:
    """Manages device configurations, config history, and audit logs."""

    def __init__(self):
        self.devices = {}
        self.config_history = []
        self.audit_log = []

    def load_config_from_network(self, host, port):
        """Fetch a pickled configuration from host:port and apply it.

        Returns True on success, False on any failure.
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((host, port))
                data = sock.recv(4096)
                return self._process_remote_config(data)
        except Exception as exc:
            self._log_audit(f'Error loading config from {host}:{port} - {exc}')
            return False

    def _process_remote_config(self, data):
        """Unpickle raw config data and apply it.

        Returns True on success, False on any failure.
        """
        try:
            config = pickle.loads(data)
            return self._apply_network_config(config)
        except Exception as exc:
            self._log_audit(f'Config processing error: {exc}')
            return False

    def _apply_network_config(self, config):
        """Merge a received config into the stored device configuration."""
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

    def save_config_to_file(self, device_id, filename):
        """Pickle the stored configuration for device_id to filename.

        Returns True on success, False on any failure.
        """
        if device_id not in self.devices:
            return False

        device = self.devices[device_id]
        config = {
            'device_id': device_id,
            'hostname': device.hostname,
            'interfaces': device.interfaces,
            'routing_table': device.routing_table,
            'credentials': device.credentials,
            'timestamp': datetime.now().isoformat(),
        }
        try:
            with open(filename, 'wb') as f:
                pickle.dump(config, f)
            self._log_audit(f'Saved config for {device_id} to {filename}')
            return True
        except Exception as exc:
            self._log_audit(f'Failed to save config: {exc}')
            return False

    def _log_config_change(self, device_id, action):
        """Record a config change with a hash of the device's state."""
        entry = {
            'timestamp': datetime.now(),
            'device': device_id,
            'action': action,
            'hash': hashlib.sha256(
                str(self.devices[device_id].__dict__).encode()
            ).hexdigest(),
        }
        self.config_history.append(entry)

    def _log_audit(self, message):
        """Append a timestamped message to the audit log."""
        entry = {'timestamp': datetime.now(), 'message': message}
        self.audit_log.append(entry)

    def get_audit_log(self, limit=10):
        """Return the most recent audit log entries, up to limit."""
        return self.audit_log[-limit:]

    def get_config_history(self, device_id, limit=5):
        """Return the most recent config history entries for a device."""
        entries = [
            entry
            for entry in self.config_history
            if entry['device'] == device_id
        ]
        return entries[-limit:]


def main():
    """Run the interactive network configuration manager CLI."""
    manager = NetworkManager()
    print('Network Configuration Manager started')

    while True:
        print(
            '\n1. Load config from network\n'
            '2. Save config to file\n'
            '3. View audit log\n'
            '4. Exit'
        )
        choice = input('Select option: ')

        if choice == '1':
            host = input('Enter host: ')
            port = int(input('Enter port: '))
            if manager.load_config_from_network(host, port):
                print('Configuration loaded successfully')
            else:
                print('Failed to load configuration')
        elif choice == '2':
            device_id = input('Enter device ID: ')
            filename = input('Enter filename: ')
            if manager.save_config_to_file(device_id, filename):
                print('Configuration saved successfully')
            else:
                print('Failed to save configuration')
        elif choice == '3':
            for entry in manager.get_audit_log():
                print(f"{entry['timestamp']}: {entry['message']}")
        elif choice == '4':
            sys.exit(0)
        else:
            print('Invalid option')


if __name__ == '__main__':
    main()
