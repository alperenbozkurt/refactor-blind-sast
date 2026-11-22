import json
import hashlib
import os
from datetime import datetime
from typing import Dict, List

BACKUP_DIR = 'backups'
DEFAULT_STATE = 'off'
DEFAULT_FIRMWARE_VERSION = '1.0.0'
AUDIT_LOG_VIEW_SIZE = 20

MENU_LINES = [
    '1. Add new device',
    '2. Import device config',
    '3. Create backup',
    '4. Restore backup',
    '5. View audit log',
    '6. Exit',
]


class SmartDevice:

    def __init__(self, device_id: str, device_type: str):
        self.device_id = device_id
        self.device_type = device_type
        self.state = DEFAULT_STATE
        self.last_updated = datetime.now()
        self.config = {}
        self.firmware_version = DEFAULT_FIRMWARE_VERSION

    def _touch(self) -> None:
        self.last_updated = datetime.now()

    def update_state(self, new_state: str) -> None:
        self.state = new_state
        self._touch()

    def update_config(self, config: Dict) -> None:
        self.config.update(config)
        self._touch()

    def to_dict(self) -> Dict:
        return {
            'device_id': self.device_id,
            'device_type': self.device_type,
            'state': self.state,
            'last_updated': self.last_updated.isoformat(),
            'config': self.config,
            'firmware_version': self.firmware_version,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'SmartDevice':
        device = cls(data['device_id'], data['device_type'])
        device.state = data.get('state', DEFAULT_STATE)
        device.last_updated = datetime.fromisoformat(
            data.get('last_updated', datetime.now().isoformat())
        )
        device.config = data.get('config', {})
        device.firmware_version = data.get('firmware_version', DEFAULT_FIRMWARE_VERSION)
        return device


def _require_type(value, expected_type, message: str) -> None:
    """Raise ValueError with *message* if value is not of expected_type."""
    if not isinstance(value, expected_type):
        raise ValueError(message)


class HomeAutomationHub:

    def __init__(self):
        self.devices: Dict[str, SmartDevice] = {}
        self.scenes: Dict[str, List[Dict]] = {}
        self.routines: Dict[str, Dict] = {}
        self.audit_log: List[Dict] = []
        os.makedirs(BACKUP_DIR, exist_ok=True)

    # ----- devices -----

    def add_device(self, device_id: str, device_type: str) -> None:
        if device_id not in self.devices:
            self.devices[device_id] = SmartDevice(device_id, device_type)
            self._log_audit('DEVICE_ADDED', f'Added {device_type} with ID {device_id}')

    def import_device_config(self, config_data: bytes) -> bool:
        try:
            config = json.loads(config_data.decode('utf-8'))
            return self._apply_device_config(config)
        except Exception as e:
            self._log_audit('CONFIG_IMPORT_FAILED', str(e))
            return False

    def _apply_device_config(self, config: Dict) -> bool:
        _require_type(config, dict, 'Config must be a dictionary')

        device_id = config.get('device_id')
        if not device_id or device_id not in self.devices:
            raise ValueError('Invalid device ID')
        device = self.devices[device_id]

        if 'state' in config:
            _require_type(config['state'], str, 'State must be a string')
            device.update_state(config['state'])

        if 'config' in config:
            _require_type(config['config'], dict, 'Config must be a dictionary')
            device.update_config(config['config'])

        if 'firmware' in config:
            _require_type(config['firmware'], str, 'Firmware must be a string')
            device.firmware_version = config['firmware']

        self._log_audit('CONFIG_UPDATED', f'Updated config for {device_id}')
        return True

    # ----- backup / restore -----

    @staticmethod
    def _backup_path(filename: str) -> str:
        return f'{BACKUP_DIR}/{filename}'

    def backup_system(self, filename: str) -> bool:
        try:
            backup_data = {
                'devices': {did: device.to_dict() for did, device in self.devices.items()},
                'scenes': self.scenes,
                'routines': self.routines,
                'timestamp': datetime.now().isoformat(),
            }
            with open(self._backup_path(filename), 'w', encoding='utf-8') as f:
                json.dump(backup_data, f)
            self._log_audit('BACKUP_CREATED', filename)
            return True
        except Exception as e:
            self._log_audit('BACKUP_FAILED', str(e))
            return False

    def restore_backup(self, filename: str) -> bool:
        try:
            with open(self._backup_path(filename), 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            _require_type(backup_data, dict, 'Invalid backup format')

            self.devices.clear()
            for did, device_data in backup_data.get('devices', {}).items():
                _require_type(device_data, dict, 'Invalid device format')
                self.devices[did] = SmartDevice.from_dict(device_data)

            self.scenes = backup_data.get('scenes', {})
            self.routines = backup_data.get('routines', {})
            self._log_audit('SYSTEM_RESTORED', filename)
            return True
        except Exception as e:
            self._log_audit('RESTORE_FAILED', str(e))
            return False

    # ----- audit -----

    def _log_audit(self, event_type: str, details: str) -> None:
        self.audit_log.append({
            'timestamp': datetime.now(),
            'event': event_type,
            'details': details,
        })

    def get_audit_log(self) -> List[Dict]:
        return self.audit_log[-AUDIT_LOG_VIEW_SIZE:]


class SmartHomeApp:

    def __init__(self):
        self.hub = HomeAutomationHub()

    def add_new_device(self) -> None:
        device_id = input('Enter device ID: ')
        device_type = input('Enter device type: ')
        self.hub.add_device(device_id, device_type)
        print(f'Added {device_type} device with ID {device_id}')

    def import_device_config(self) -> None:
        config_file = input('Enter config file path: ')
        try:
            with open(config_file, 'rb') as f:
                if self.hub.import_device_config(f.read()):
                    print('Device config imported successfully')
                else:
                    print('Failed to import device config')
        except Exception as e:
            print(f'Error reading config file: {str(e)}')

    def create_backup(self) -> None:
        filename = input('Enter backup filename: ')
        if self.hub.backup_system(filename):
            print('Backup created successfully')
        else:
            print('Failed to create backup')

    def restore_backup(self) -> None:
        filename = input('Enter backup filename: ')
        if self.hub.restore_backup(filename):
            print('System restored successfully')
        else:
            print('Failed to restore backup')

    def show_audit_log(self) -> None:
        print('\nRecent audit events:')
        for entry in self.hub.get_audit_log():
            print(f"{entry['timestamp']} - {entry['event']}: {entry['details']}")


def main():
    app = SmartHomeApp()
    actions = {
        '1': app.add_new_device,
        '2': app.import_device_config,
        '3': app.create_backup,
        '4': app.restore_backup,
        '5': app.show_audit_log,
    }
    exit_choice = '6'

    print('Smart Home Automation System')
    while True:
        print('\n' + '\n'.join(MENU_LINES))
        choice = input('Select option: ')
        if choice == exit_choice:
            break
        action = actions.get(choice)
        if action is None:
            print('Invalid option')
        else:
            action()


if __name__ == '__main__':
    main()
