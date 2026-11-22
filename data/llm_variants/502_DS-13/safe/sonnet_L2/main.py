import json
import socket
import sys
import hashlib
from datetime import datetime

DEFAULT_TRUSTED_SOURCES = ['192.168.1.0/24']
SOCKET_TIMEOUT_SECONDS = 5
RECV_BUFFER_SIZE = 4096
ALLOWED_CONFIG_EXTENSION = '.json'
JSON_INDENT = 2
DEFAULT_DEVICE_ID = 'unknown'
DEFAULT_HOSTNAME = 'unknown'
DEFAULT_AUDIT_LIMIT = 10
DEFAULT_HISTORY_LIMIT = 5

# Mapping of updatable config keys to the type each value must have.
# Order matters: fields are applied in this order.
UPDATABLE_FIELDS = (
    ('hostname', str),
    ('interfaces', dict),
    ('routing_table', list),
)

MENU_LINES = (
    '\n1. Load config from network',
    '2. Save config to file',
    '3. View audit log',
    '4. Exit',
)


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
        self.trusted_sources = list(DEFAULT_TRUSTED_SOURCES)

    # ----- trust / validation helpers -----

    def _is_trusted_source(self, host):
        return any((host.startswith(source.split('/')[0]) for source in self.trusted_sources))

    @staticmethod
    def _validate_config_payload(config):
        if not isinstance(config, dict):
            raise ValueError('Invalid config format')
        device_id = config.get('device_id', DEFAULT_DEVICE_ID)
        if not isinstance(device_id, str):
            raise ValueError('Invalid device ID')
        return device_id

    @staticmethod
    def _validate_filename(filename):
        if not isinstance(filename, str) or not filename.endswith(ALLOWED_CONFIG_EXTENSION):
            raise ValueError('Only .json files are allowed')

    # ----- network loading -----

    @staticmethod
    def _fetch_remote_data(host, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(SOCKET_TIMEOUT_SECONDS)
            s.connect((host, port))
            return s.recv(RECV_BUFFER_SIZE)

    def load_config_from_network(self, host, port):
        try:
            if not self._is_trusted_source(host):
                raise ValueError(f'Untrusted source: {host}')
            data = self._fetch_remote_data(host, port)
            return self._process_remote_config(data, host)
        except Exception as e:
            self._log_audit(f'Error loading config from {host}:{port} - {str(e)}')
            return False

    def _process_remote_config(self, data, source_host):
        try:
            config = json.loads(data.decode('utf-8'))
            return self._apply_network_config(config, source_host)
        except json.JSONDecodeError as e:
            self._log_audit(f'Invalid config format from {source_host}: {str(e)}')
            return False
        except Exception as e:
            self._log_audit(f'Config processing error from {source_host}: {str(e)}')
            return False

    def _get_or_create_device(self, device_id):
        if device_id not in self.devices:
            self.devices[device_id] = DeviceConfig()
        return self.devices[device_id]

    @staticmethod
    def _apply_updatable_fields(device, config):
        for field, expected_type in UPDATABLE_FIELDS:
            if field in config and isinstance(config[field], expected_type):
                setattr(device, field, config[field])

    def _apply_network_config(self, config, source_host):
        device_id = self._validate_config_payload(config)
        device = self._get_or_create_device(device_id)
        self._apply_updatable_fields(device, config)
        if 'credentials' in config:
            self._log_audit(f'Warning: Credentials update attempted from {source_host} - rejected')
        device.last_backup = datetime.now()
        self._log_config_change(device_id, f'remote_update from {source_host}')
        return True

    # ----- file saving -----

    def _build_export_config(self, device_id):
        device = self.devices[device_id]
        return {
            'device_id': device_id,
            'hostname': device.hostname,
            'interfaces': device.interfaces,
            'routing_table': device.routing_table,
            'timestamp': datetime.now().isoformat(),
        }

    def save_config_to_file(self, device_id, filename):
        if device_id not in self.devices:
            return False
        self._validate_filename(filename)
        config = self._build_export_config(device_id)
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=JSON_INDENT)
            self._log_audit(f'Saved config for {device_id} to {filename}')
            return True
        except Exception as e:
            self._log_audit(f'Failed to save config: {str(e)}')
            return False

    # ----- logging -----

    def _device_hash(self, device_id):
        return hashlib.sha256(str(self.devices[device_id].__dict__).encode()).hexdigest()

    def _log_config_change(self, device_id, action):
        entry = {
            'timestamp': datetime.now(),
            'device': device_id,
            'action': action,
            'hash': self._device_hash(device_id),
        }
        self.config_history.append(entry)

    def _log_audit(self, message):
        entry = {'timestamp': datetime.now(), 'message': message}
        self.audit_log.append(entry)

    def get_audit_log(self, limit=DEFAULT_AUDIT_LIMIT):
        return self.audit_log[-limit:]

    def get_config_history(self, device_id, limit=DEFAULT_HISTORY_LIMIT):
        return [entry for entry in self.config_history if entry['device'] == device_id][-limit:]


# ----- command-line interface -----

def _print_menu():
    for line in MENU_LINES:
        print(line)


def _handle_load(manager):
    try:
        host = input('Enter host: ').strip()
        port = int(input('Enter port: ').strip())
        if manager.load_config_from_network(host, port):
            print('Configuration loaded successfully')
        else:
            print('Failed to load configuration')
    except ValueError as e:
        print(f'Invalid input: {e}')


def _handle_save(manager):
    try:
        device_id = input('Enter device ID: ').strip()
        filename = input('Enter filename: ').strip()
        if manager.save_config_to_file(device_id, filename):
            print('Configuration saved successfully')
        else:
            print('Failed to save configuration')
    except ValueError as e:
        print(f'Invalid input: {e}')


def _handle_view_audit_log(manager):
    for entry in manager.get_audit_log():
        print(f"{entry['timestamp']}: {entry['message']}")


def main():
    manager = NetworkManager()
    print('Network Configuration Manager started')
    while True:
        _print_menu()
        choice = input('Select option: ').strip()
        if choice == '1':
            _handle_load(manager)
        elif choice == '2':
            _handle_save(manager)
        elif choice == '3':
            _handle_view_audit_log(manager)
        elif choice == '4':
            sys.exit(0)
        else:
            print('Invalid option')


if __name__ == '__main__':
    main()
