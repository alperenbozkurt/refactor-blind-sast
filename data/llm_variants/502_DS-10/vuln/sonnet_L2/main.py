import io
import pickle
import json
import hashlib
import socket
import threading
from datetime import datetime

# --- Constants ---------------------------------------------------------------

REQUIRED_DEVICE_FIELDS = ('device_id', 'ip_address', 'firmware_version')
REQUIRED_FIRMWARE_METADATA_FIELDS = ('version', 'compatible_versions')

COMMAND_UPDATE_FIRMWARE = 'UPDATE_FIRMWARE'

MSG_REGISTER_DEVICE = 'REGISTER_DEVICE'
MSG_UPLOAD_FIRMWARE = 'UPLOAD_FIRMWARE'
MSG_GET_COMMANDS = 'GET_COMMANDS'

RESP_REGISTRATION_SUCCESS = b'REGISTRATION_SUCCESS'
RESP_REGISTRATION_FAILED = b'REGISTRATION_FAILED'
RESP_FIRMWARE_UPLOAD_SUCCESS = b'FIRMWARE_UPLOAD_SUCCESS'
RESP_FIRMWARE_UPLOAD_FAILED = b'FIRMWARE_UPLOAD_FAILED'
RESP_INVALID_MESSAGE_TYPE = b'INVALID_MESSAGE_TYPE'

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 8080
LISTEN_BACKLOG = 5
RECV_BUFFER_SIZE = 4096


# --- Helpers -----------------------------------------------------------------

class _RestrictedUnpickler(pickle.Unpickler):
    """Unpickler that refuses to resolve any global (no arbitrary code execution).

    Plain data (dicts, lists, strings, numbers, ...) loads normally.
    """

    def find_class(self, module, name):
        raise pickle.UnpicklingError(
            f'global {module}.{name} is forbidden in firmware metadata'
        )


def _load_metadata(raw):
    return _RestrictedUnpickler(io.BytesIO(raw)).load()


def _utc_timestamp():
    return str(datetime.utcnow())


def _build_update_command(device_id, firmware_id):
    return {
        'device_id': device_id,
        'command': COMMAND_UPDATE_FIRMWARE,
        'firmware_id': firmware_id,
        'timestamp': _utc_timestamp(),
    }


# --- Device manager ----------------------------------------------------------

class IoTDeviceManager:

    def __init__(self):
        self.devices = {}
        self.command_queue = []
        self.firmware_cache = {}
        self.running = False

    def _validate_device(self, device_data):
        return all((field in device_data for field in REQUIRED_DEVICE_FIELDS))

    def _validate_firmware_metadata(self, metadata):
        return isinstance(metadata, dict) and all(
            field in metadata for field in REQUIRED_FIRMWARE_METADATA_FIELDS
        )

    def _cache_firmware(self, binary, metadata):
        firmware_id = hashlib.sha256(binary).hexdigest()
        self.firmware_cache[firmware_id] = {'binary': binary, 'metadata': metadata}
        return firmware_id

    def _queue_updates(self, firmware_id, metadata):
        for (device_id, device) in self.devices.items():
            if device['firmware_version'] in metadata['compatible_versions']:
                self.command_queue.append(_build_update_command(device_id, firmware_id))

    def process_firmware_update(self, firmware_data):
        try:
            firmware_meta = _load_metadata(firmware_data['metadata'])
            if not self._validate_firmware_metadata(firmware_meta):
                return False
            firmware_id = self._cache_firmware(firmware_data['binary'], firmware_meta)
            self._queue_updates(firmware_id, firmware_meta)
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

    def pop_commands_for_device(self, device_id):
        commands = [cmd for cmd in self.command_queue if cmd['device_id'] == device_id]
        self.command_queue = [cmd for cmd in self.command_queue if cmd['device_id'] != device_id]
        return commands


# --- Server ------------------------------------------------------------------

class IoTServer:

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.manager = IoTDeviceManager()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Message handlers: each takes (conn, message) and sends a response.

    def _handle_register_device(self, conn, message):
        success = self.manager.register_device(message['data'])
        conn.sendall(RESP_REGISTRATION_SUCCESS if success else RESP_REGISTRATION_FAILED)

    def _handle_upload_firmware(self, conn, message):
        firmware_data = {
            'binary': message['binary'].encode(),
            'metadata': message['metadata'],
        }
        success = self.manager.process_firmware_update(firmware_data)
        conn.sendall(
            RESP_FIRMWARE_UPLOAD_SUCCESS if success else RESP_FIRMWARE_UPLOAD_FAILED
        )

    def _handle_get_commands(self, conn, message):
        commands = self.manager.pop_commands_for_device(message['device_id'])
        conn.sendall(json.dumps(commands).encode())

    def _dispatch(self, conn, message):
        message_type = message['type']
        handlers = (
            (MSG_REGISTER_DEVICE, self._handle_register_device),
            (MSG_UPLOAD_FIRMWARE, self._handle_upload_firmware),
            (MSG_GET_COMMANDS, self._handle_get_commands),
        )
        for (name, handler) in handlers:
            if message_type == name:
                handler(conn, message)
                return
        conn.sendall(RESP_INVALID_MESSAGE_TYPE)

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(RECV_BUFFER_SIZE)
            if not data:
                return
            message = json.loads(data.decode())
            self._dispatch(conn, message)
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


def main():
    server = IoTServer()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()


if __name__ == '__main__':
    main()
