import pickle
import json
import hashlib
import io
import os
from datetime import datetime
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BACKUP_DIR = 'backups'
AUDIT_LOG_TAIL_SIZE = 20
DEFAULT_DEVICE_STATE = 'off'
DEFAULT_FIRMWARE_VERSION = '1.0.0'

EVENT_DEVICE_ADDED = 'DEVICE_ADDED'
EVENT_CONFIG_IMPORT_FAILED = 'CONFIG_IMPORT_FAILED'
EVENT_CONFIG_UPDATED = 'CONFIG_UPDATED'
EVENT_BACKUP_CREATED = 'BACKUP_CREATED'
EVENT_BACKUP_FAILED = 'BACKUP_FAILED'
EVENT_SYSTEM_RESTORED = 'SYSTEM_RESTORED'
EVENT_RESTORE_FAILED = 'RESTORE_FAILED'

MENU_ADD_DEVICE = '1'
MENU_IMPORT_CONFIG = '2'
MENU_CREATE_BACKUP = '3'
MENU_RESTORE_BACKUP = '4'
MENU_VIEW_AUDIT_LOG = '5'
MENU_EXIT = '6'

MENU_TEXT = (
    '\n1. Add new device',
    '2. Import device config',
    '3. Create backup',
    '4. Restore backup',
    '5. View audit log',
    '6. Exit',
)


# ---------------------------------------------------------------------------
# Safe (de)serialization helpers
# ---------------------------------------------------------------------------

# Globals that may be referenced by pickles we load. Plain containers and
# primitives need no globals; backups additionally contain datetime values.
_NO_GLOBALS: FrozenSet[Tuple[str, str]] = frozenset()
_BACKUP_GLOBALS: FrozenSet[Tuple[str, str]] = frozenset({('datetime', 'datetime')})


class _RestrictedUnpickler(pickle.Unpickler):
    """Unpickler that only resolves an explicit allowlist of globals,
    preventing arbitrary code execution from untrusted pickle data."""

    def __init__(self, file, allowed_globals: FrozenSet[Tuple[str, str]]):
        super().__init__(file)
        self._allowed_globals = allowed_globals

    def find_class(self, module: str, name: str):
        if (module, name) in self._allowed_globals:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f'Forbidden global: {module}.{name}')


def _safe_loads(data: bytes, allowed_globals: FrozenSet[Tuple[str, str]] = _NO_GLOBALS) -> Any:
    return _RestrictedUnpickler(io.BytesIO(data), allowed_globals).load()


def _safe_load(file, allowed_globals: FrozenSet[Tuple[str, str]] = _NO_GLOBALS) -> Any:
    return _RestrictedUnpickler(file, allowed_globals).load()


def _backup_path(filename: str) -> str:
    """Return the path for a backup file, ensuring it stays inside BACKUP_DIR."""
    path = f'{BACKUP_DIR}/{filename}'
    base = os.path.realpath(BACKUP_DIR)
    target = os.path.realpath(path)
    if os.path.commonpath([base, target]) != base:
        raise ValueError('Invalid backup filename')
    return path


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

class SmartDevice:

    def __init__(self, device_id: str, device_type: str):
        self.device_id = device_id
        self.device_type = device_type
        self.state = DEFAULT_DEVICE_STATE
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


class HomeAutomationHub:

    def __init__(self):
        self.devices: Dict[str, SmartDevice] = {}
        self.scenes: Dict[str, List[Dict]] = {}
        self.routines: Dict[str, Dict] = {}
        self.audit_log: List[Dict] = []
        os.makedirs(BACKUP_DIR, exist_ok=True)

    # -- device management -------------------------------------------------

    def add_device(self, device_id: str, device_type: str) -> None:
        if device_id not in self.devices:
            self.devices[device_id] = SmartDevice(device_id, device_type)
            self._log_audit(EVENT_DEVICE_ADDED, f'Added {device_type} with ID {device_id}')

    def import_device_config(self, config_data: bytes) -> bool:
        try:
            config = _safe_loads(config_data)
            return self._apply_device_config(config)
        except Exception as e:
            self._log_audit(EVENT_CONFIG_IMPORT_FAILED, str(e))
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
        self._log_audit(EVENT_CONFIG_UPDATED, f'Updated config for {device_id}')
        return True

    # -- backup / restore --------------------------------------------------

    def _build_backup_data(self) -> Dict[str, Any]:
        return {
            'devices': {did: device.__dict__ for (did, device) in self.devices.items()},
            'scenes': self.scenes,
            'routines': self.routines,
            'timestamp': datetime.now().isoformat(),
        }

    def _restore_devices(self, devices_data: Dict[str, Dict]) -> None:
        self.devices.clear()
        for (did, device_data) in devices_data.items():
            device = SmartDevice(did, device_data['device_type'])
            device.__dict__.update(device_data)
            self.devices[did] = device

    def backup_system(self, filename: str) -> bool:
        try:
            backup_data = self._build_backup_data()
            with open(_backup_path(filename), 'wb') as f:
                pickle.dump(backup_data, f)
            self._log_audit(EVENT_BACKUP_CREATED, filename)
            return True
        except Exception as e:
            self._log_audit(EVENT_BACKUP_FAILED, str(e))
            return False

    def restore_backup(self, filename: str) -> bool:
        try:
            with open(_backup_path(filename), 'rb') as f:
                backup_data = _safe_load(f, _BACKUP_GLOBALS)
            self._restore_devices(backup_data['devices'])
            self.scenes = backup_data.get('scenes', {})
            self.routines = backup_data.get('routines', {})
            self._log_audit(EVENT_SYSTEM_RESTORED, filename)
            return True
        except Exception as e:
            self._log_audit(EVENT_RESTORE_FAILED, str(e))
            return False

    # -- audit -------------------------------------------------------------

    def _log_audit(self, event_type: str, details: str) -> None:
        self.audit_log.append({'timestamp': datetime.now(), 'event': event_type, 'details': details})

    def get_audit_log(self) -> List[Dict]:
        return self.audit_log[-AUDIT_LOG_TAIL_SIZE:]


# ---------------------------------------------------------------------------
# CLI application
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
            print(f"{entry['timestamp']} - {entry['event']}: {entry['details']}")


def _print_menu() -> None:
    for line in MENU_TEXT:
        print(line)


def main():
    app = SmartHomeApp()
    handlers = {
        MENU_ADD_DEVICE: app.add_new_device,
        MENU_IMPORT_CONFIG: app.import_device_config,
        MENU_CREATE_BACKUP: app.create_backup,
        MENU_RESTORE_BACKUP: app.restore_backup,
        MENU_VIEW_AUDIT_LOG: app.show_audit_log,
    }
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
