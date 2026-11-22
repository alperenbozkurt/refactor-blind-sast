import hashlib
import io
import pickle
import socket
import sys
from datetime import datetime

RECV_BUFFER_SIZE = 4096


class _SafeUnpickler(pickle.Unpickler):
    """Unpickler that refuses to load any global, so only plain data
    (dicts, lists, strings, numbers, ...) can be deserialized.
    This prevents arbitrary code execution from untrusted network data."""

    def find_class(self, module, name):
        raise pickle.UnpicklingError(f'Forbidden global: {module}.{name}')


def _safe_loads(data):
    return _SafeUnpickler(io.BytesIO(data)).load()


class DeviceConfig:

    def __init__(self):
        self.hostname = 'unknown'
        self.interfaces = {}
        self.routing_table = []
        self.credentials = {}
        self.last_backup = None


class NetworkManager:

    def __init__(self):
        self.devices = {}
        self.config_history = []
        self.audit_log = []

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
            config = _safe_loads(data)
            return self._apply_network_config(config)
        except Exception as e:
            self._log_audit(f'Config processing error: {e}')
            return False

    def _apply_network_config(self, config):
        device_id = config.get('device_id', 'unknown')
        device = self.devices.setdefault(device_id, DeviceConfig())

        device.hostname = config.get('hostname', device.hostname)
        device.interfaces = config.get('interfaces', device.interfaces)
        device.routing_table = config.get('routing_table', device.routing_table)
        if 'credentials' in config:
            device.credentials.update(config['credentials'])
        device.last_backup = datetime.now()

        self._log_config_change(device_id, 'remote_update')
        return True

    def save_config_to_file(self, device_id, filename):
        device = self.devices.get(device_id)
        if device is None:
            return False

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
        except Exception as e:
            self._log_audit(f'Failed to save config: {e}')
            return False

    def _log_config_change(self, device_id, action):
        state = str(self.devices[device_id].__dict__)
        self.config_history.append({
            'timestamp': datetime.now(),
            'device': device_id,
            'action': action,
            'hash': hashlib.sha256(state.encode()).hexdigest(),
        })

    def _log_audit(self, message):
        self.audit_log.append({'timestamp': datetime.now(), 'message': message})

    def get_audit_log(self, limit=10):
        return self.audit_log[-limit:]

    def get_config_history(self, device_id, limit=5):
        return [
            entry for entry in self.config_history
            if entry['device'] == device_id
        ][-limit:]


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


def _handle_audit(manager):
    for entry in manager.get_audit_log():
        print(f"{entry['timestamp']}: {entry['message']}")


def _handle_exit(manager):
    sys.exit(0)


_MENU_HANDLERS = {
    '1': _handle_load,
    '2': _handle_save,
    '3': _handle_audit,
    '4': _handle_exit,
}


def _print_menu():
    print('\n1. Load config from network')
    print('2. Save config to file')
    print('3. View audit log')
    print('4. Exit')


def main():
    manager = NetworkManager()
    print('Network Configuration Manager started')
    while True:
        _print_menu()
        choice = input('Select option: ')
        handler = _MENU_HANDLERS.get(choice)
        if handler is None:
            print('Invalid option')
        else:
            handler(manager)


if __name__ == '__main__':
    main()
