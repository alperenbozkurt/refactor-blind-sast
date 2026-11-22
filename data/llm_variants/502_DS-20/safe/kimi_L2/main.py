import json
import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DEFAULT_DEVICE_STATE = 'off'
DEFAULT_FIRMWARE_VERSION = '1.0.0'
BACKUP_DIR = 'backups'
AUDIT_LOG_LIMIT = 20

# Audit event types
EVENT_DEVICE_ADDED = 'DEVICE_ADDED'
EVENT_CONFIG_IMPORT_FAILED = 'CONFIG_IMPORT_FAILED'
EVENT_CONFIG_UPDATED = 'CONFIG_UPDATED'
EVENT_BACKUP_CREATED = 'BACKUP_CREATED'
EVENT_BACKUP_FAILED = 'BACKUP_FAILED'
EVENT_SYSTEM_RESTORED = 'SYSTEM_RESTORED'
EVENT_RESTORE_FAILED = 'RESTORE_FAILED'

# Validation error messages
ERROR_CONFIG_MUST_BE_DICT = 'Config must be a dictionary'
ERROR_INVALID_DEVICE_ID = 'Invalid device ID'
ERROR_STATE_MUST_BE_STR = 'State must be a string'
ERROR_FIRMWARE_MUST_BE_STR = 'Firmware must be a string'
ERROR_INVALID_BACKUP_FORMAT = 'Invalid backup format'
ERROR_INVALID_DEVICE_FORMAT = 'Invalid device format'

# CLI text
APP_TITLE = 'Smart Home Automation System'
MENU_OPTIONS = (
    '1. Add new device',
    '2. Import device config',
    '3. Create backup',
    '4. Restore backup',
    '5. View audit log',
    '6. Exit',
)
EXIT_OPTION = '6'
PROMPT_SELECT_OPTION = 'Select option: '
MESSAGE_INVALID_OPTION = 'Invalid option'


@dataclass(frozen=True)
class HubConfig:
    """Configuration values for the HomeAutomationHub."""

    backup_dir: str = BACKUP_DIR
    audit_log_limit: int = AUDIT_LOG_LIMIT


DEFAULT_HUB_CONFIG = HubConfig()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Return the current timestamp in ISO 8601 format."""
    return datetime.now().isoformat()


def _make_audit_entry(event_type: str, details: str) -> Dict:
    """Build a single audit log entry."""
    return {'timestamp': datetime.now(), 'event': event_type, 'details': details}


def _print_menu() -> None:
    """Print the main menu, including the leading blank line."""
    print()
    for option in MENU_OPTIONS:
        print(option)


class SmartDevice:

    def __init__(self, device_id: str, device_type: str):
        self.device_id = device_id
        self.device_type = device_type
        self.state = DEFAULT_DEVICE_STATE
        self.last_updated = datetime.now()
        self.config = {}
        self.firmware_version = DEFAULT_FIRMWARE_VERSION

    def update_state(self, new_state: str) -> None:
        self.state = new_state
        self._touch()

    def update_config(self, config: Dict) -> None:
        self.config.update(config)
        self._touch()

    def _touch(self) -> None:
        self.last_updated = datetime.now()

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
        device.state = data.get('state', DEFAULT_DEVICE_STATE)
        device.last_updated = datetime.fromisoformat(data.get('last_updated', _now_iso()))
        device.config = data.get('config', {})
        device.firmware_version = data.get('firmware_version', DEFAULT_FIRMWARE_VERSION)
        return device


class HomeAutomationHub:

    def __init__(self):
        self._config = DEFAULT_HUB_CONFIG
        self.devices: Dict[str, SmartDevice] = {}
        self.scenes: Dict[str, List[Dict]] = {}
        self.routines: Dict[str, Dict] = {}
        self.audit_log: List[Dict] = []
        os.makedirs(self._config.backup_dir, exist_ok=True)

    def add_device(self, device_id: str, device_type: str) -> None:
        if device_id in self.devices:
            return
        self.devices[device_id] = SmartDevice(device_id, device_type)
        self._log_audit(EVENT_DEVICE_ADDED, f'Added {device_type} with ID {device_id}')

    def import_device_config(self, config_data: bytes) -> bool:
        try:
            config = json.loads(config_data.decode('utf-8'))
            return self._apply_device_config(config)
        except Exception as e:
            self._log_audit(EVENT_CONFIG_IMPORT_FAILED, str(e))
            return False

    def _apply_device_config(self, config: Dict) -> bool:
        device_id, device = self._resolve_device(config)
        self._apply_device_state(device, config)
        self._apply_device_settings(device, config)
        self._apply_device_firmware(device, config)
        self._log_audit(EVENT_CONFIG_UPDATED, f'Updated config for {device_id}')
        return True

    def _resolve_device(self, config: Dict) -> Tuple[str, SmartDevice]:
        if not isinstance(config, dict):
            raise ValueError(ERROR_CONFIG_MUST_BE_DICT)
        device_id = config.get('device_id')
        if not device_id or device_id not in self.devices:
            raise ValueError(ERROR_INVALID_DEVICE_ID)
        return device_id, self.devices[device_id]

    @staticmethod
    def _apply_device_state(device: SmartDevice, config: Dict) -> None:
        if 'state' not in config:
            return
        state = config['state']
        if not isinstance(state, str):
            raise ValueError(ERROR_STATE_MUST_BE_STR)
        device.update_state(state)

    @staticmethod
    def _apply_device_settings(device: SmartDevice, config: Dict) -> None:
        if 'config' not in config:
            return
        settings = config['config']
        if not isinstance(settings, dict):
            raise ValueError(ERROR_CONFIG_MUST_BE_DICT)
        device.update_config(settings)

    @staticmethod
    def _apply_device_firmware(device: SmartDevice, config: Dict) -> None:
        if 'firmware' not in config:
            return
        firmware = config['firmware']
        if not isinstance(firmware, str):
            raise ValueError(ERROR_FIRMWARE_MUST_BE_STR)
        device.firmware_version = firmware

    def backup_system(self, filename: str) -> bool:
        try:
            backup_data = self._build_backup_data()
            with open(self._backup_path(filename), 'w', encoding='utf-8') as f:
                json.dump(backup_data, f)
            self._log_audit(EVENT_BACKUP_CREATED, filename)
            return True
        except Exception as e:
            self._log_audit(EVENT_BACKUP_FAILED, str(e))
            return False

    def _build_backup_data(self) -> Dict:
        return {
            'devices': {did: device.to_dict() for (did, device) in self.devices.items()},
            'scenes': self.scenes,
            'routines': self.routines,
            'timestamp': _now_iso(),
        }

    def _backup_path(self, filename: str) -> str:
        return f'{self._config.backup_dir}/{filename}'

    def restore_backup(self, filename: str) -> bool:
        try:
            backup_data = self._read_backup(filename)
            self._restore_devices(backup_data.get('devices', {}))
            self.scenes = backup_data.get('scenes', {})
            self.routines = backup_data.get('routines', {})
            self._log_audit(EVENT_SYSTEM_RESTORED, filename)
            return True
        except Exception as e:
            self._log_audit(EVENT_RESTORE_FAILED, str(e))
            return False

    def _read_backup(self, filename: str) -> Dict:
        with open(self._backup_path(filename), 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        if not isinstance(backup_data, dict):
            raise ValueError(ERROR_INVALID_BACKUP_FORMAT)
        return backup_data

    def _restore_devices(self, devices_data: Dict) -> None:
        self.devices.clear()
        for (did, device_data) in devices_data.items():
            if not isinstance(device_data, dict):
                raise ValueError(ERROR_INVALID_DEVICE_FORMAT)
            self.devices[did] = SmartDevice.from_dict(device_data)

    def _log_audit(self, event_type: str, details: str) -> None:
        self.audit_log.append(_make_audit_entry(event_type, details))

    def get_audit_log(self) -> List[Dict]:
        return self.audit_log[-self._config.audit_log_limit:]


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
    print(APP_TITLE)
    actions = {
        '1': app.add_new_device,
        '2': app.import_device_config,
        '3': app.create_backup,
        '4': app.restore_backup,
        '5': app.show_audit_log,
    }
    while True:
        _print_menu()
        choice = input(PROMPT_SELECT_OPTION)
        if choice == EXIT_OPTION:
            break
        action = actions.get(choice)
        if action is None:
            print(MESSAGE_INVALID_OPTION)
        else:
            action()


if __name__ == '__main__':
    main()
