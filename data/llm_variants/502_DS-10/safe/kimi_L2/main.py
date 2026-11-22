"""IoT device management server.

The module is organised around two classes:

* ``IoTDeviceManager`` - in-memory store for devices, firmware binaries and
  the queue of pending per-device commands.
* ``IoTServer`` - TCP/JSON protocol front-end that delegates all state
  changes to an ``IoTDeviceManager`` instance.

Protocol strings, validation rules and network tunables are defined as
named constants so they can be maintained centrally as the codebase grows.
"""

import json
import hashlib
import socket
import threading
from datetime import datetime

# ---------------------------------------------------------------------------
# Validation rules
# ---------------------------------------------------------------------------

DEVICE_REQUIRED_FIELDS = ('device_id', 'ip_address', 'firmware_version')
FIRMWARE_METADATA_REQUIRED_FIELDS = ('version', 'compatible_versions')

# ---------------------------------------------------------------------------
# Protocol definition
# ---------------------------------------------------------------------------

MESSAGE_TYPE_REGISTER_DEVICE = 'REGISTER_DEVICE'
MESSAGE_TYPE_UPLOAD_FIRMWARE = 'UPLOAD_FIRMWARE'
MESSAGE_TYPE_GET_COMMANDS = 'GET_COMMANDS'

COMMAND_UPDATE_FIRMWARE = 'UPDATE_FIRMWARE'

RESPONSE_REGISTRATION_SUCCESS = b'REGISTRATION_SUCCESS'
RESPONSE_REGISTRATION_FAILED = b'REGISTRATION_FAILED'
RESPONSE_FIRMWARE_UPLOAD_SUCCESS = b'FIRMWARE_UPLOAD_SUCCESS'
RESPONSE_FIRMWARE_UPLOAD_FAILED = b'FIRMWARE_UPLOAD_FAILED'
RESPONSE_INVALID_MESSAGE_TYPE = b'INVALID_MESSAGE_TYPE'
RESPONSE_INVALID_MESSAGE_FORMAT = b'INVALID_MESSAGE_FORMAT'

# ---------------------------------------------------------------------------
# Server configuration defaults
# ---------------------------------------------------------------------------

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 8080
RECV_BUFFER_SIZE = 4096
LISTEN_BACKLOG = 5


class IoTDeviceManager:
    """Holds all device, firmware and command-queue state."""

    def __init__(self):
        self.devices = {}
        self.command_queue = []
        self.firmware_cache = {}
        self.running = False

    def _validate_device(self, device_data):
        """Return True when every required device field is present."""
        return all((field in device_data for field in DEVICE_REQUIRED_FIELDS))

    def _validate_firmware_metadata(self, metadata):
        """Return True when the firmware metadata has the expected shape."""
        if not isinstance(metadata, dict):
            return False
        if not all((field in metadata for field in FIRMWARE_METADATA_REQUIRED_FIELDS)):
            return False
        if not isinstance(metadata['compatible_versions'], list):
            return False
        return True

    def _parse_firmware_metadata(self, raw_metadata):
        """Decode the firmware metadata payload into a Python object."""
        try:
            return json.loads(raw_metadata)
        except json.JSONDecodeError:
            if isinstance(raw_metadata, dict):
                return raw_metadata
            raise ValueError('Invalid firmware metadata format')

    def _cache_firmware(self, binary, metadata):
        """Store the firmware binary keyed by its digest; return the digest."""
        firmware_id = hashlib.sha256(binary).hexdigest()
        self.firmware_cache[firmware_id] = {'binary': binary, 'metadata': metadata}
        return firmware_id

    def _build_update_command(self, device_id, firmware_id):
        """Create a single UPDATE_FIRMWARE command queue entry."""
        return {
            'device_id': device_id,
            'command': COMMAND_UPDATE_FIRMWARE,
            'firmware_id': firmware_id,
            'timestamp': str(datetime.utcnow()),
        }

    def _queue_update_commands(self, firmware_id, firmware_meta):
        """Enqueue an update command for every compatible device."""
        for (device_id, device) in self.devices.items():
            if device['firmware_version'] in firmware_meta['compatible_versions']:
                self.command_queue.append(self._build_update_command(device_id, firmware_id))

    def process_firmware_update(self, firmware_data):
        """Validate, cache and distribute a newly uploaded firmware."""
        try:
            firmware_meta = self._parse_firmware_metadata(firmware_data['metadata'])
            if not self._validate_firmware_metadata(firmware_meta):
                return False
            firmware_id = self._cache_firmware(firmware_data['binary'], firmware_meta)
            self._queue_update_commands(firmware_id, firmware_meta)
            return True
        except Exception as e:
            print(f'Firmware processing failed: {e}')
            return False

    def register_device(self, device_data):
        """Decode, validate and store a device registration payload."""
        try:
            device = json.loads(device_data)
            if not self._validate_device(device):
                return False
            self.devices[device['device_id']] = device
            return True
        except Exception as e:
            print(f'Device registration failed: {e}')
            return False


class IoTServer:
    """TCP server exposing the device manager over a small JSON protocol."""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.manager = IoTDeviceManager()
        self.socket = self._create_socket()

    def _create_socket(self):
        """Create and configure the listening TCP socket."""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return server_socket

    def _extract_device_commands(self, device_id):
        """Return and remove all queued commands for the given device."""
        commands = [cmd for cmd in self.manager.command_queue if cmd['device_id'] == device_id]
        self.manager.command_queue = [cmd for cmd in self.manager.command_queue if cmd['device_id'] != device_id]
        return commands

    def _handle_register_device(self, conn, message):
        success = self.manager.register_device(message['data'])
        conn.sendall(RESPONSE_REGISTRATION_SUCCESS if success else RESPONSE_REGISTRATION_FAILED)

    def _handle_upload_firmware(self, conn, message):
        firmware_data = {'binary': message['binary'].encode(), 'metadata': message['metadata']}
        success = self.manager.process_firmware_update(firmware_data)
        conn.sendall(RESPONSE_FIRMWARE_UPLOAD_SUCCESS if success else RESPONSE_FIRMWARE_UPLOAD_FAILED)

    def _handle_get_commands(self, conn, message):
        commands = self._extract_device_commands(message['device_id'])
        conn.sendall(json.dumps(commands).encode())

    def _dispatch_message(self, conn, message):
        """Route a decoded message to the handler for its type."""
        handlers = {
            MESSAGE_TYPE_REGISTER_DEVICE: self._handle_register_device,
            MESSAGE_TYPE_UPLOAD_FIRMWARE: self._handle_upload_firmware,
            MESSAGE_TYPE_GET_COMMANDS: self._handle_get_commands,
        }
        handler = handlers.get(message['type'])
        if handler is None:
            conn.sendall(RESPONSE_INVALID_MESSAGE_TYPE)
            return
        handler(conn, message)

    def handle_client(self, conn, addr):
        """Serve a single request/response cycle on the client connection."""
        try:
            data = conn.recv(RECV_BUFFER_SIZE)
            if not data:
                return
            message = json.loads(data.decode())
            self._dispatch_message(conn, message)
        except json.JSONDecodeError as e:
            print(f'Invalid message format: {e}')
            conn.sendall(RESPONSE_INVALID_MESSAGE_FORMAT)
        except Exception as e:
            print(f'Client handling error: {e}')
        finally:
            conn.close()

    def _spawn_client_thread(self, conn, addr):
        """Handle a freshly accepted connection on its own thread."""
        threading.Thread(target=self.handle_client, args=(conn, addr)).start()

    def start(self):
        """Bind the socket and serve connections until stopped."""
        self.manager.running = True
        self.socket.bind((self.host, self.port))
        self.socket.listen(LISTEN_BACKLOG)
        print(f'IoT Server started on {self.host}:{self.port}')
        while self.manager.running:
            try:
                (conn, addr) = self.socket.accept()
                self._spawn_client_thread(conn, addr)
            except KeyboardInterrupt:
                self.manager.running = False
            except Exception as e:
                print(f'Server error: {e}')

    def stop(self):
        """Stop the accept loop and release the listening socket."""
        self.manager.running = False
        self.socket.close()


if __name__ == '__main__':
    server = IoTServer()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
