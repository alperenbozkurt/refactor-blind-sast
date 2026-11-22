import json
import hashlib
import os
from datetime import datetime
from typing import Any, Callable, Dict, List

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BACKUP_DIR = 'backups'
DEFAULT_STATE = 'off'
DEFAULT_FIRMWARE_VERSION = '1.0.0'
AUDIT_LOG_TAIL_SIZE = 20
TEXT_ENCODING = 'utf-8'

# Audit event types
EVENT_DEVICE_ADDED = 'DEVICE_ADDED'
EVENT_CONFIG_IMPORT_FAILED = 'CONFIG_IMPORT_FAILED'
EVENT_CONFIG_UPDATED = 'CONFIG_UPDATED'
EVENT_BACKUP_CREATED = 'BACKUP_CREATED'
EVENT_BACKUP_FAILED = 'BACKUP_FAILED'
EVENT_SYSTEM_RESTORED = 'SYSTEM_RESTORED'
EVENT_RESTORE_FAILED = 'RESTORE_FAILED'

# Menu choices
MENU_ADD_DEVICE = '1'
MENU_IMPORT_CONFIG = '2'
MENU_CREATE_BACKUP = '3'
MENU_RESTORE_BACKUP = '4'
MENU_VIEW_AUDIT_LOG = '5'
MENU_EXIT = '6'

MENU_TEXT_LINES = (
    '\n1. Add new device',
    '2. Import device config',
    '3. Create backup',
    '4. Restore backup',
    '5. View audit log',
    '6. Exit',
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now()


def _backup_path(filename: str) -> str:
    return f'{BACKUP_DIR}/{filename}'


def _require_type(value: Any, expected_type: type, message: str) -> None:
    if not isinstance(value, expected_type):
        raise ValueError(message)


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

class SmartDevice:

    def __init__(self, device_id: str, device_type: str):
        self.device_id = device_id
        self.device_type = device_type
        self.state = DEFAULT_STATE
        self.last_updated = _now()
        self.config = {}
        self.firmware_version = DEFAULT_FIRMWARE_VERSION

    def _touch(self) -> None:
        self.last_updated = _now()

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
            data.get('last_updated', _now().isoformat())
        )
        device.config = data.get('config', {})
        device.firmware_version = data.get('firmware_version', DEFAULT_FIRMWARE_VERSION)
        return device


class HomeAutomationHub:

    def __init__(self):
        self.devices: Dict[str, SmartDevice] = {}
        self.scenes: Dict[str, List[Dict]] = {}
        self.routines: Dict[str, Dict] = {}
        self.audit_log: List[Dict] = []
        os.makedirs(BACKUP_DIR, exist_ok=True)

    # -- devices -----------------------------------------------------------

    def add_device(self, device_id: str, device_type: str) -> None:
        if device_id not in self.devices:
            self.devices[device_id] = SmartDevice(device_id, device_type)
            self._log_audit(EVENT_DEVICE_ADDED, f'Added {device_type} with ID {device_id}')

    # -- config import -----------------------------------------------------

    def import_device_config(self, config_data: bytes) -> bool:
        try:
            config = json.loads(config_data.decode(TEXT_ENCODING))
            return self._apply_device_config(config)
        except Exception as e:
            self._log_audit(EVENT_CONFIG_IMPORT_FAILED, str(e))
            return False

    def _apply_device_config(self, config: Dict) -> bool:
        _require_type(config, dict, 'Config must be a dictionary')
        device = self._resolve_device(config)
        device_id = config.get('device_id')
        self._apply_state(device, config)
        self._apply_device_settings(device, config)
        self._apply_firmware(device, config)
        self._log_audit(EVENT_CONFIG_UPDATED, f'Updated config for {device_id}')
        return True

    def _resolve_device(self, config: Dict) -> SmartDevice:
        device_id = config.get('device_id')
        if not device_id or device_id not in self.devices:
            raise ValueError('Invalid device ID')
        return self.devices[device_id]

    @staticmethod
    def _apply_state(device: SmartDevice, config: Dict) -> None:
        if 'state' in config:
            _require_type(config['state'], str, 'State must be a string')
            device.update_state(config['state'])

    @staticmethod
    def _apply_device_settings(device: SmartDevice, config: Dict) -> None:
        if 'config' in config:
            _require_type(config['config'], dict, 'Config must be a dictionary')
            device.update_config(config['config'])

    @staticmethod
    def _apply_firmware(device: SmartDevice, config: Dict) -> None:
        if 'firmware' in config:
            _require_type(config['firmware'], str, 'Firmware must be a string')
            device.firmware_version = config['firmware']

    # -- backup / restore --------------------------------------------------

    def _build_backup_data(self) -> Dict:
        return {
            'devices': {did: device.to_dict() for (did, device) in self.devices.items()},
            'scenes': self.scenes,
            'routines': self.routines,
            'timestamp': _now().isoformat(),
        }

    def backup_system(self, filename: str) -> bool:
        try:
            backup_data = self._build_backup_data()
            with open(_backup_path(filename), 'w', encoding=TEXT_ENCODING) as f:
                json.dump(backup_data, f)
            self._log_audit(EVENT_BACKUP_CREATED, filename)
            return True
        except Exception as e:
            self._log_audit(EVENT_BACKUP_FAILED, str(e))
            return False

    def _load_devices_from_backup(self, devices_data: Dict) -> None:
        self.devices.clear()
        for (did, device_data) in devices_data.items():
            _require_type(device_data, dict, 'Invalid device format')
            self.devices[did] = SmartDevice.from_dict(device_data)

    def restore_backup(self, filename: str) -> bool:
        try:
            with open(_backup_path(filename), 'r', encoding=TEXT_ENCODING) as f:
                backup_data = json.load(f)
            _require_type(backup_data, dict, 'Invalid backup format')
            self._load_devices_from_backup(backup_data.get('devices', {}))
            self.scenes = backup_data.get('scenes', {})
            self.routines = backup_data.get('routines', {})
            self._log_audit(EVENT_SYSTEM_RESTORED, filename)
            return True
        except Exception as e:
            self._log_audit(EVENT_RESTORE_FAILED, str(e))
            return False

    # -- audit -------------------------------------------------------------

    def _log_audit(self, event_type: str, details: str) -> None:
        self.audit_log.append({'timestamp': _now(), 'event': event_type, 'details': details})

    def get_audit_log(self) -> List[Dict]:
        return self.audit_log[-AUDIT_LOG_TAIL_SIZE:]


# ---------------------------------------------------------------------------
# Command-line application
# ---------------------------------------------------------------------------

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


def _print_menu() -> None:
    for line in MENU_TEXT_LINES:
        print(line)


def _build_menu_handlers(app: SmartHomeApp) -> Dict[str, Callable[[], None]]:
    return {
        MENU_ADD_DEVICE: app.add_new_device,
        MENU_IMPORT_CONFIG: app.import_device_config,
        MENU_CREATE_BACKUP: app.create_backup,
        MENU_RESTORE_BACKUP: app.restore_backup,
        MENU_VIEW_AUDIT_LOG: app.show_audit_log,
    }


def main():
    app = SmartHomeApp()
    handlers = _build_menu_handlers(app)
    print('Smart Home Automation System')
    while True:
        _print_menu()
        choice = input('Select option: ')
        if choice == MENU_EXIT:
            break
        handler = handlers.get(choice)
        if handler is not None:
            handler()
        else:
            print('Invalid option')


if __name__ == '__main__':
    main()
