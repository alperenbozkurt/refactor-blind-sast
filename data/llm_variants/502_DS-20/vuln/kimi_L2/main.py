import pickle
import json
import hashlib
import os
from datetime import datetime
from typing import Dict, List

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

BACKUP_DIRECTORY = 'backups'
DEFAULT_DEVICE_STATE = 'off'
DEFAULT_FIRMWARE_VERSION = '1.0.0'
AUDIT_LOG_LIMIT = 20

# Audit event types.
EVENT_DEVICE_ADDED = 'DEVICE_ADDED'
EVENT_CONFIG_IMPORT_FAILED = 'CONFIG_IMPORT_FAILED'
EVENT_CONFIG_UPDATED = 'CONFIG_UPDATED'
EVENT_BACKUP_CREATED = 'BACKUP_CREATED'
EVENT_BACKUP_FAILED = 'BACKUP_FAILED'
EVENT_SYSTEM_RESTORED = 'SYSTEM_RESTORED'
EVENT_RESTORE_FAILED = 'RESTORE_FAILED'

# Device configuration payload keys.
KEY_DEVICE_ID = 'device_id'
KEY_STATE = 'state'
KEY_CONFIG = 'config'
KEY_FIRMWARE = 'firmware'
KEY_DEVICE_TYPE = 'device_type'

# Backup payload keys.
BACKUP_KEY_DEVICES = 'devices'
BACKUP_KEY_SCENES = 'scenes'
BACKUP_KEY_ROUTINES = 'routines'
BACKUP_KEY_TIMESTAMP = 'timestamp'

# Interactive CLI definition.
MENU_OPTIONS = (
    '1. Add new device',
    '2. Import device config',
    '3. Create backup',
    '4. Restore backup',
    '5. View audit log',
    '6. Exit',
)
EXIT_CHOICE = '6'


def _backup_path(filename: str) -> str:
    """Build the full path for a file inside the backup directory."""
    return f'{BACKUP_DIRECTORY}/{filename}'


def _print_menu() -> None:
    """Print the main menu of the interactive CLI."""
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
        """Refresh the last-updated timestamp."""
        self.last_updated = datetime.now()


class HomeAutomationHub:

    def __init__(self):
        self.devices: Dict[str, SmartDevice] = {}
        self.scenes: Dict[str, List[Dict]] = {}
        self.routines: Dict[str, Dict] = {}
        self.audit_log: List[Dict] = []
        os.makedirs(BACKUP_DIRECTORY, exist_ok=True)

    def add_device(self, device_id: str, device_type: str) -> None:
        if device_id not in self.devices:
            self.devices[device_id] = SmartDevice(device_id, device_type)
            self._log_audit(EVENT_DEVICE_ADDED, f'Added {device_type} with ID {device_id}')

    def import_device_config(self, config_data: bytes) -> bool:
        try:
            config = pickle.loads(config_data)
            return self._apply_device_config(config)
        except Exception as e:
            self._log_audit(EVENT_CONFIG_IMPORT_FAILED, str(e))
            return False

    def _apply_device_config(self, config: Dict) -> bool:
        device_id = config.get(KEY_DEVICE_ID)
        device = self._require_device(device_id)
        if KEY_STATE in config:
            device.update_state(config[KEY_STATE])
        if KEY_CONFIG in config:
            device.update_config(config[KEY_CONFIG])
        if KEY_FIRMWARE in config:
            device.firmware_version = config[KEY_FIRMWARE]
        self._log_audit(EVENT_CONFIG_UPDATED, f'Updated config for {device_id}')
        return True

    def _require_device(self, device_id: str) -> SmartDevice:
        """Return the device with the given ID or raise a ValueError."""
        if not device_id or device_id not in self.devices:
            raise ValueError('Invalid device ID')
        return self.devices[device_id]

    def backup_system(self, filename: str) -> bool:
        try:
            self._write_backup_file(filename, self._build_backup_data())
            self._log_audit(EVENT_BACKUP_CREATED, filename)
            return True
        except Exception as e:
            self._log_audit(EVENT_BACKUP_FAILED, str(e))
            return False

    def _build_backup_data(self) -> Dict:
        """Assemble a serialisable snapshot of the current system state."""
        return {
            BACKUP_KEY_DEVICES: {did: device.__dict__ for (did, device) in self.devices.items()},
            BACKUP_KEY_SCENES: self.scenes,
            BACKUP_KEY_ROUTINES: self.routines,
            BACKUP_KEY_TIMESTAMP: datetime.now().isoformat(),
        }

    @staticmethod
    def _write_backup_file(filename: str, backup_data: Dict) -> None:
        with open(_backup_path(filename), 'wb') as f:
            pickle.dump(backup_data, f)

    def restore_backup(self, filename: str) -> bool:
        try:
            backup_data = self._read_backup_file(filename)
            self._restore_devices(backup_data[BACKUP_KEY_DEVICES])
            self.scenes = backup_data.get(BACKUP_KEY_SCENES, {})
            self.routines = backup_data.get(BACKUP_KEY_ROUTINES, {})
            self._log_audit(EVENT_SYSTEM_RESTORED, filename)
            return True
        except Exception as e:
            self._log_audit(EVENT_RESTORE_FAILED, str(e))
            return False

    @staticmethod
    def _read_backup_file(filename: str) -> Dict:
        with open(_backup_path(filename), 'rb') as f:
            return pickle.load(f)

    def _restore_devices(self, devices_data: Dict) -> None:
        self.devices.clear()
        for (did, device_data) in devices_data.items():
            self.devices[did] = self._rebuild_device(did, device_data)

    @staticmethod
    def _rebuild_device(device_id: str, device_data: Dict) -> SmartDevice:
        device = SmartDevice(device_id, device_data[KEY_DEVICE_TYPE])
        device.__dict__.update(device_data)
        return device

    def _log_audit(self, event_type: str, details: str) -> None:
        self.audit_log.append({'timestamp': datetime.now(), 'event': event_type, 'details': details})

    def get_audit_log(self) -> List[Dict]:
        return self.audit_log[-AUDIT_LOG_LIMIT:]


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
        with open(config_file, 'rb') as f:
            if self.hub.import_device_config(f.read()):
                print('Device config imported successfully')
            else:
                print('Failed to import device config')

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
            print(self._format_audit_entry(entry))

    @staticmethod
    def _format_audit_entry(entry: Dict) -> str:
        return f"{entry['timestamp']} - {entry['event']}: {entry['details']}"


def main():
    app = SmartHomeApp()
    print('Smart Home Automation System')
    actions = {
        '1': app.add_new_device,
        '2': app.import_device_config,
        '3': app.create_backup,
        '4': app.restore_backup,
        '5': app.show_audit_log,
    }
    while True:
        _print_menu()
        choice = input('Select option: ')
        if choice == EXIT_CHOICE:
            break
        action = actions.get(choice)
        if action is None:
            print('Invalid option')
        else:
            action()


if __name__ == '__main__':
    main()
