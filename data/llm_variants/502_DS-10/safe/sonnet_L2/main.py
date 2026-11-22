import json
import hashlib
import socket
import threading
from datetime import datetime

# --- Constants ---------------------------------------------------------------

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 8080
RECV_BUFFER_SIZE = 4096
LISTEN_BACKLOG = 5

REQUIRED_DEVICE_FIELDS = ['device_id', 'ip_address', 'firmware_version']
REQUIRED_FIRMWARE_METADATA_FIELDS = ['version', 'compatible_versions']

COMMAND_UPDATE_FIRMWARE = 'UPDATE_FIRMWARE'

MSG_REGISTER_DEVICE = 'REGISTER_DEVICE'
MSG_UPLOAD_FIRMWARE = 'UPLOAD_FIRMWARE'
MSG_GET_COMMANDS = 'GET_COMMANDS'

RESP_REGISTRATION_SUCCESS = b'REGISTRATION_SUCCESS'
RESP_REGISTRATION_FAILED = b'REGISTRATION_FAILED'
RESP_FIRMWARE_UPLOAD_SUCCESS = b'FIRMWARE_UPLOAD_SUCCESS'
RESP_FIRMWARE_UPLOAD_FAILED = b'FIRMWARE_UPLOAD_FAILED'
RESP_INVALID_MESSAGE_TYPE = b'INVALID_MESSAGE_TYPE'
RESP_INVALID_MESSAGE_FORMAT = b'INVALID_MESSAGE_FORMAT'


# --- Helper functions --------------------------------------------------------

def _has_all_fields(data, fields):
    """Return True if every field name in `fields` is present in `data`."""
    return all((field in data for field in fields))


def _parse_firmware_metadata(raw_metadata):
    """Parse raw firmware metadata, falling back to an already-decoded dict."""
    try:
        return json.loads(raw_metadata)
    except json.JSONDecodeError:
        if isinstance(raw_metadata, dict):
            return raw_metadata
        raise ValueError('Invalid firmware metadata format')


def _compute_firmware_id(binary):
    return hashlib.sha256(binary).hexdigest()


def _build_update_command(device_id, firmware_id):
    return {
        'device_id': device_id,
        'command': COMMAND_UPDATE_FIRMWARE,
        'firmware_id': firmware_id,
        'timestamp': str(datetime.utcnow()),
    }


# --- Device manager ----------------------------------------------------------

class IoTDeviceManager:

    def __init__(self):
        self.devices = {}
        self.command_queue = []
        self.firmware_cache = {}
        self.running = False

    def _validate_device(self, device_data):
        return _has_all_fields(device_data, REQUIRED_DEVICE_FIELDS)

    def _validate_firmware_metadata(self, metadata):
        if not isinstance(metadata, dict):
            return False
        if not _has_all_fields(metadata, REQUIRED_FIRMWARE_METADATA_FIELDS):
            return False
        if not isinstance(metadata['compatible_versions'], list):
            return False
        return True

    def _cache_firmware(self, firmware_id, binary, metadata):
        self.firmware_cache[firmware_id] = {'binary': binary, 'metadata': metadata}

    def _queue_updates_for_compatible_devices(self, firmware_id, firmware_meta):
        for (device_id, device) in self.devices.items():
            if device['firmware_version'] in firmware_meta['compatible_versions']:
                self.command_queue.append(_build_update_command(device_id, firmware_id))

    def pop_commands_for_device(self, device_id):
        """Remove and return all queued commands for the given device."""
        commands = [cmd for cmd in self.command_queue if cmd['device_id'] == device_id]
        self.command_queue = [cmd for cmd in self.command_queue if cmd['device_id'] != device_id]
        return commands

    def process_firmware_update(self, firmware_data):
        try:
            firmware_meta = _parse_firmware_metadata(firmware_data['metadata'])
            if not self._validate_firmware_metadata(firmware_meta):
                return False
            firmware_id = _compute_firmware_id(firmware_data['binary'])
            self._cache_firmware(firmware_id, firmware_data['binary'], firmware_meta)
            self._queue_updates_for_compatible_devices(firmware_id, firmware_meta)
            return True
        except Exception as e:
            print(f'Firmware processing failed: {e}')
            return False

    def register_device(self, device_data):
        try:
            device = json.loads(device_data)
            if not self._validate_device(device):
                return False
            self.devices[device['device_id']] = device
            return True
        except Exception as e:
            print(f'Device registration failed: {e}')
            return False


# --- Server ------------------------------------------------------------------

class IoTServer:

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.manager = IoTDeviceManager()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._handlers = {
            MSG_REGISTER_DEVICE: self._handle_register_device,
            MSG_UPLOAD_FIRMWARE: self._handle_upload_firmware,
            MSG_GET_COMMANDS: self._handle_get_commands,
        }

    # Message handlers: each returns the bytes to send back to the client.

    def _handle_register_device(self, message):
        success = self.manager.register_device(message['data'])
        return RESP_REGISTRATION_SUCCESS if success else RESP_REGISTRATION_FAILED

    def _handle_upload_firmware(self, message):
        firmware_data = {
            'binary': message['binary'].encode(),
            'metadata': message['metadata'],
        }
        success = self.manager.process_firmware_update(firmware_data)
        return RESP_FIRMWARE_UPLOAD_SUCCESS if success else RESP_FIRMWARE_UPLOAD_FAILED

    def _handle_get_commands(self, message):
        device_id = message['device_id']
        commands = self.manager.pop_commands_for_device(device_id)
        return json.dumps(commands).encode()

    def _dispatch_message(self, message):
        handler = self._handlers.get(message['type'])
        if handler is None:
            return RESP_INVALID_MESSAGE_TYPE
        return handler(message)

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(RECV_BUFFER_SIZE)
            if not data:
                return
            message = json.loads(data.decode())
            conn.sendall(self._dispatch_message(message))
        except json.JSONDecodeError as e:
            print(f'Invalid message format: {e}')
            conn.sendall(RESP_INVALID_MESSAGE_FORMAT)
        except Exception as e:
            print(f'Client handling error: {e}')
        finally:
            conn.close()

    def start(self):
        self.manager.running = True
        self.socket.bind((self.host, self.port))
        self.socket.listen(LISTEN_BACKLOG)
        print(f'IoT Server started on {self.host}:{self.port}')
        while self.manager.running:
            try:
                (conn, addr) = self.socket.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr)).start()
            except KeyboardInterrupt:
                self.manager.running = False
            except Exception as e:
                print(f'Server error: {e}')

    def stop(self):
        self.manager.running = False
        self.socket.close()


if __name__ == '__main__':
    server = IoTServer()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
