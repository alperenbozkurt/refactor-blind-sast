"""Smart home automation system.

Manages smart devices, device configuration imports, system
backup/restore and an audit log, exposed through an interactive
command-line interface.
"""

import hashlib
import json
import os
import pickle
from datetime import datetime
from typing import Dict, List

BACKUP_DIR = 'backups'
AUDIT_LOG_LIMIT = 20

DEFAULT_DEVICE_STATE = 'off'
DEFAULT_FIRMWARE_VERSION = '1.0.0'

MENU_TEXT = (
    '\n1. Add new device\n'
    '2. Import device config\n'
    '3. Create backup\n'
    '4. Restore backup\n'
    '5. View audit log\n'
    '6. Exit'
)


def _backup_path(filename: str) -> str:
    """Return the path of a backup file inside the backup directory."""
    return f'{BACKUP_DIR}/{filename}'


class SmartDevice:
    """A single smart device and its mutable runtime state."""

    def __init__(self, device_id: str, device_type: str):
        self.device_id = device_id
        self.device_type = device_type
        self.state = DEFAULT_DEVICE_STATE
        self.last_updated = datetime.now()
        self.config = {}
        self.firmware_version = DEFAULT_FIRMWARE_VERSION

    def update_state(self, new_state: str) -> None:
        """Update the device state and refresh the modification time."""
        self.state = new_state
        self._touch()

    def update_config(self, config: Dict) -> None:
        """Merge new settings into the device configuration."""
        self.config.update(config)
        self._touch()

    def _touch(self) -> None:
        """Record the time of the most recent modification."""
        self.last_updated = datetime.now()


class HomeAutomationHub:
    """Central hub managing devices, scenes, routines and audit events."""

    def __init__(self):
        self.devices: Dict[str, SmartDevice] = {}
        self.scenes: Dict[str, List[Dict]] = {}
        self.routines: Dict[str, Dict] = {}
        self.audit_log: List[Dict] = []
        os.makedirs(BACKUP_DIR, exist_ok=True)

    def add_device(self, device_id: str, device_type: str) -> None:
        """Register a new device unless its ID is already known."""
        if device_id not in self.devices:
            self.devices[device_id] = SmartDevice(device_id, device_type)
            self._log_audit(
                'DEVICE_ADDED',
                f'Added {device_type} with ID {device_id}',
            )

    def import_device_config(self, config_data: bytes) -> bool:
        """Deserialize pickled config data and apply it to a device."""
        try:
            config = pickle.loads(config_data)
            return self._apply_device_config(config)
        except Exception as e:
            self._log_audit('CONFIG_IMPORT_FAILED', str(e))
            return False

    def _apply_device_config(self, config: Dict) -> bool:
        device_id = config.get('device_id')
        if not device_id or device_id not in self.devices:
            raise ValueError('Invalid device ID')
        device = self.devices[device_id]
        if 'state' in config:
            device.update_state(config['state'])
        if 'config' in config:
            device.update_config(config['config'])
        if 'firmware' in config:
            device.firmware_version = config['firmware']
        self._log_audit('CONFIG_UPDATED', f'Updated config for {device_id}')
        return True

    def backup_system(self, filename: str) -> bool:
        """Serialize the full system state to a backup file."""
        try:
            backup_data = self._build_backup_data()
            with open(_backup_path(filename), 'wb') as f:
                pickle.dump(backup_data, f)
            self._log_audit('BACKUP_CREATED', filename)
            return True
        except Exception as e:
            self._log_audit('BACKUP_FAILED', str(e))
            return False

    def _build_backup_data(self) -> Dict:
        return {
            'devices': {
                did: device.__dict__
                for did, device in self.devices.items()
            },
            'scenes': self.scenes,
            'routines': self.routines,
            'timestamp': datetime.now().isoformat(),
        }

    def restore_backup(self, filename: str) -> bool:
        """Load a backup file and replace the current system state."""
        try:
            with open(_backup_path(filename), 'rb') as f:
                backup_data = pickle.load(f)
            self.devices.clear()
            for did, device_data in backup_data['devices'].items():
                self.devices[did] = self._restore_device(did, device_data)
            self.scenes = backup_data.get('scenes', {})
            self.routines = backup_data.get('routines', {})
            self._log_audit('SYSTEM_RESTORED', filename)
            return True
        except Exception as e:
            self._log_audit('RESTORE_FAILED', str(e))
            return False

    @staticmethod
    def _restore_device(device_id: str, device_data: Dict) -> SmartDevice:
        device = SmartDevice(device_id, device_data['device_type'])
        device.__dict__.update(device_data)
        return device

    def _log_audit(self, event_type: str, details: str) -> None:
        self.audit_log.append({
            'timestamp': datetime.now(),
            'event': event_type,
            'details': details,
        })

    def get_audit_log(self) -> List[Dict]:
        """Return the most recent audit entries (newest last)."""
        return self.audit_log[-AUDIT_LOG_LIMIT:]


class SmartHomeApp:
    """Interactive command-line front end for the automation hub."""

    def __init__(self):
        self.hub = HomeAutomationHub()

    def add_new_device(self) -> None:
        """Prompt for device details and register the device."""
        device_id = input('Enter device ID: ')
        device_type = input('Enter device type: ')
        self.hub.add_device(device_id, device_type)
        print(f'Added {device_type} device with ID {device_id}')

    def import_device_config(self) -> None:
        """Prompt for a file and import the device config it contains."""
        config_file = input('Enter config file path: ')
        with open(config_file, 'rb') as f:
            if self.hub.import_device_config(f.read()):
                print('Device config imported successfully')
            else:
                print('Failed to import device config')

    def create_backup(self) -> None:
        """Prompt for a filename and save the system state to it."""
        filename = input('Enter backup filename: ')
        if self.hub.backup_system(filename):
            print('Backup created successfully')
        else:
            print('Failed to create backup')

    def restore_backup(self) -> None:
        """Prompt for a filename and restore the system state from it."""
        filename = input('Enter backup filename: ')
        if self.hub.restore_backup(filename):
            print('System restored successfully')
        else:
            print('Failed to restore backup')

    def show_audit_log(self) -> None:
        """Print the most recent audit log entries."""
        print('\nRecent audit events:')
        for entry in self.hub.get_audit_log():
            timestamp = entry['timestamp']
            event = entry['event']
            details = entry['details']
            print(f'{timestamp} - {event}: {details}')


def main():
    app = SmartHomeApp()
    actions = {
        '1': app.add_new_device,
        '2': app.import_device_config,
        '3': app.create_backup,
        '4': app.restore_backup,
        '5': app.show_audit_log,
    }
    print('Smart Home Automation System')
    while True:
        print(MENU_TEXT)
        choice = input('Select option: ')
        if choice == '6':
            break
        action = actions.get(choice)
        if action is None:
            print('Invalid option')
        else:
            action()


if __name__ == '__main__':
    main()
