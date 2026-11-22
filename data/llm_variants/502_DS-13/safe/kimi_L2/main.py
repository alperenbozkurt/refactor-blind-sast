import json
import socket
import sys
import hashlib
from datetime import datetime

DEFAULT_ENCODING = 'utf-8'
JSON_FILE_EXTENSION = '.json'
SOCKET_TIMEOUT_SECONDS = 5
RECV_BUFFER_BYTES = 4096
DEFAULT_TRUSTED_SOURCES = ('192.168.1.0/24',)
AUDIT_LOG_DEFAULT_LIMIT = 10
CONFIG_HISTORY_DEFAULT_LIMIT = 5

OPTION_LOAD_CONFIG = '1'
OPTION_SAVE_CONFIG = '2'
OPTION_VIEW_AUDIT_LOG = '3'
OPTION_EXIT = '4'


class DeviceConfig:

    def __init__(self):
        self.hostname = 'unknown'
        self.interfaces = {}
        self.routing_table = []
        self.credentials = {}
        self.last_backup = None


def _network_source_prefix(source):
    return source.split('/')[0]


def _tail(entries, limit):
    return entries[-limit:]


def _device_state_hash(device):
    return hashlib.sha256(str(device.__dict__).encode(DEFAULT_ENCODING)).hexdigest()


def _config_file_payload(device_id, device):
    return {
        'device_id': device_id,
        'hostname': device.hostname,
        'interfaces': device.interfaces,
        'routing_table': device.routing_table,
        'timestamp': datetime.now().isoformat(),
    }


class NetworkManager:

    def __init__(self):
        self.devices = {}
        self.config_history = []
        self.audit_log = []
        self.trusted_sources = list(DEFAULT_TRUSTED_SOURCES)

    def _is_trusted_source(self, host):
        return any((host.startswith(_network_source_prefix(source)) for source in self.trusted_sources))

    def load_config_from_network(self, host, port):
        try:
            if not self._is_trusted_source(host):
                raise ValueError(f'Untrusted source: {host}')
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(SOCKET_TIMEOUT_SECONDS)
                sock.connect((host, port))
                data = sock.recv(RECV_BUFFER_BYTES)
                return self._process_remote_config(data, host)
        except Exception as e:
            self._log_audit(f'Error loading config from {host}:{port} - {str(e)}')
            return False

    def _process_remote_config(self, data, source_host):
        try:
            config = json.loads(data.decode(DEFAULT_ENCODING))
            return self._apply_network_config(config, source_host)
        except json.JSONDecodeError as e:
            self._log_audit(f'Invalid config format from {source_host}: {str(e)}')
            return False
        except Exception as e:
            self._log_audit(f'Config processing error from {source_host}: {str(e)}')
            return False

    def _apply_network_config(self, config, source_host):
        if not isinstance(config, dict):
            raise ValueError('Invalid config format')
        device_id = config.get('device_id', 'unknown')
        if not isinstance(device_id, str):
            raise ValueError('Invalid device ID')
        if device_id not in self.devices:
            self.devices[device_id] = DeviceConfig()
        device = self.devices[device_id]
        if 'hostname' in config:
            if isinstance(config['hostname'], str):
                device.hostname = config['hostname']
        if 'interfaces' in config:
            if isinstance(config['interfaces'], dict):
                device.interfaces = config['interfaces']
        if 'routing_table' in config:
            if isinstance(config['routing_table'], list):
                device.routing_table = config['routing_table']
        if 'credentials' in config:
            self._log_audit(f'Warning: Credentials update attempted from {source_host} - rejected')
        device.last_backup = datetime.now()
        self._log_config_change(device_id, f'remote_update from {source_host}')
        return True

    def save_config_to_file(self, device_id, filename):
        if device_id not in self.devices:
            return False
        self._validate_config_filename(filename)
        payload = _config_file_payload(device_id, self.devices[device_id])
        return self._write_config_file(payload, filename, device_id)

    def _validate_config_filename(self, filename):
        if not isinstance(filename, str) or not filename.endswith(JSON_FILE_EXTENSION):
            raise ValueError('Only .json files are allowed')

    def _write_config_file(self, payload, filename, device_id):
        try:
            with open(filename, 'w', encoding=DEFAULT_ENCODING) as config_file:
                json.dump(payload, config_file, indent=2)
            self._log_audit(f'Saved config for {device_id} to {filename}')
            return True
        except Exception as e:
            self._log_audit(f'Failed to save config: {str(e)}')
            return False

    def _log_config_change(self, device_id, action):
        entry = {
            'timestamp': datetime.now(),
            'device': device_id,
            'action': action,
            'hash': _device_state_hash(self.devices[device_id]),
        }
        self.config_history.append(entry)

    def _log_audit(self, message):
        entry = {'timestamp': datetime.now(), 'message': message}
        self.audit_log.append(entry)

    def get_audit_log(self, limit=AUDIT_LOG_DEFAULT_LIMIT):
        return _tail(self.audit_log, limit)

    def get_config_history(self, device_id, limit=CONFIG_HISTORY_DEFAULT_LIMIT):
        device_entries = [entry for entry in self.config_history if entry['device'] == device_id]
        return _tail(device_entries, limit)


def _print_menu():
    print('\n1. Load config from network')
    print('2. Save config to file')
    print('3. View audit log')
    print('4. Exit')


def _handle_load_config(manager):
    try:
        host = input('Enter host: ').strip()
        port = int(input('Enter port: ').strip())
        if manager.load_config_from_network(host, port):
            print('Configuration loaded successfully')
        else:
            print('Failed to load configuration')
    except ValueError as e:
        print(f'Invalid input: {e}')


def _handle_save_config(manager):
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
    entries = manager.get_audit_log()
    for entry in entries:
        print(f"{entry['timestamp']}: {entry['message']}")


def main():
    manager = NetworkManager()
    print('Network Configuration Manager started')
    while True:
        _print_menu()
        choice = input('Select option: ').strip()
        if choice == OPTION_LOAD_CONFIG:
            _handle_load_config(manager)
        elif choice == OPTION_SAVE_CONFIG:
            _handle_save_config(manager)
        elif choice == OPTION_VIEW_AUDIT_LOG:
            _handle_view_audit_log(manager)
        elif choice == OPTION_EXIT:
            sys.exit(0)
        else:
            print('Invalid option')


if __name__ == '__main__':
    main()
