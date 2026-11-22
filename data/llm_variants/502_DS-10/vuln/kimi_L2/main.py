"""IoT device management server.

Refactored for a larger production codebase: protocol strings and other
magic values are named module-level constants, and the manager/server
logic is decomposed into small, single-purpose helper methods. All
public names, signatures and runtime behaviour are unchanged.
"""

import hashlib
import json
import pickle
import socket
import threading
from datetime import datetime


# ---------------------------------------------------------------------------
# Server configuration
# ---------------------------------------------------------------------------

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 8080
RECV_BUFFER_SIZE = 4096
LISTEN_BACKLOG = 5
ENCODING = 'utf-8'

# ---------------------------------------------------------------------------
# Protocol constants
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

# ---------------------------------------------------------------------------
# Validation schemas
# ---------------------------------------------------------------------------

REQUIRED_DEVICE_FIELDS = ('device_id', 'ip_address', 'firmware_version')
REQUIRED_FIRMWARE_METADATA_FIELDS = ('version', 'compatible_versions')


class IoTDeviceManager:
    """Tracks registered devices, cached firmware and pending commands."""

    def __init__(self):
        self.devices = {}
        self.command_queue = []
        self.firmware_cache = {}
        self.running = False

    # -- validation ------------------------------------------------------

    def _validate_device(self, device_data):
        return all(field in device_data for field in REQUIRED_DEVICE_FIELDS)

    def _validate_firmware_metadata(self, metadata):
        return isinstance(metadata, dict) and all(
            field in metadata for field in REQUIRED_FIRMWARE_METADATA_FIELDS
        )

    # -- device registration ----------------------------------------------

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

    # -- firmware updates ---------------------------------------------------

    def process_firmware_update(self, firmware_data):
        try:
            firmware_meta = pickle.loads(firmware_data['metadata'])
            if not self._validate_firmware_metadata(firmware_meta):
                return False
            firmware_id = self._firmware_id(firmware_data['binary'])
            self._cache_firmware(firmware_id, firmware_data['binary'], firmware_meta)
            self._enqueue_update_commands(firmware_id, firmware_meta)
            return True
        except Exception as e:
            print(f'Firmware processing failed: {e}')
            return False

    @staticmethod
    def _firmware_id(binary):
        return hashlib.sha256(binary).hexdigest()

    def _cache_firmware(self, firmware_id, binary, metadata):
        self.firmware_cache[firmware_id] = {'binary': binary, 'metadata': metadata}

    def _enqueue_update_commands(self, firmware_id, firmware_meta):
        for device_id, device in self.devices.items():
            if device['firmware_version'] in firmware_meta['compatible_versions']:
                self.command_queue.append(
                    self._build_update_command(device_id, firmware_id)
                )

    @staticmethod
    def _build_update_command(device_id, firmware_id):
        return {
            'device_id': device_id,
            'command': COMMAND_UPDATE_FIRMWARE,
            'firmware_id': firmware_id,
            'timestamp': str(datetime.utcnow()),
        }


class IoTServer:
    """TCP server exposing the device manager over a simple JSON protocol."""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.manager = IoTDeviceManager()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # -- connection handling ------------------------------------------------

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(RECV_BUFFER_SIZE)
            if not data:
                return
            message = json.loads(data.decode(ENCODING))
            self._dispatch_message(conn, message)
        except Exception as e:
            print(f'Client handling error: {e}')
        finally:
            conn.close()

    def _dispatch_message(self, conn, message):
        message_type = message['type']
        if message_type == MESSAGE_TYPE_REGISTER_DEVICE:
            self._handle_register_device(conn, message)
        elif message_type == MESSAGE_TYPE_UPLOAD_FIRMWARE:
            self._handle_upload_firmware(conn, message)
        elif message_type == MESSAGE_TYPE_GET_COMMANDS:
            self._handle_get_commands(conn, message)
        else:
            conn.sendall(RESPONSE_INVALID_MESSAGE_TYPE)

    # -- message handlers -----------------------------------------------------

    def _handle_register_device(self, conn, message):
        success = self.manager.register_device(message['data'])
        conn.sendall(
            RESPONSE_REGISTRATION_SUCCESS if success else RESPONSE_REGISTRATION_FAILED
        )

    def _handle_upload_firmware(self, conn, message):
        firmware_data = {
            'binary': message['binary'].encode(ENCODING),
            'metadata': message['metadata'],
        }
        success = self.manager.process_firmware_update(firmware_data)
        conn.sendall(
            RESPONSE_FIRMWARE_UPLOAD_SUCCESS if success else RESPONSE_FIRMWARE_UPLOAD_FAILED
        )

    def _handle_get_commands(self, conn, message):
        device_id = message['device_id']
        commands = [
            cmd for cmd in self.manager.command_queue if cmd['device_id'] == device_id
        ]
        self.manager.command_queue = [
            cmd for cmd in self.manager.command_queue if cmd['device_id'] != device_id
        ]
        conn.sendall(json.dumps(commands).encode(ENCODING))

    # -- lifecycle --------------------------------------------------------------

    def start(self):
        self.manager.running = True
        self.socket.bind((self.host, self.port))
        self.socket.listen(LISTEN_BACKLOG)
        print(f'IoT Server started on {self.host}:{self.port}')
        self._accept_loop()

    def _accept_loop(self):
        while self.manager.running:
            try:
                conn, addr = self.socket.accept()
                self._start_client_thread(conn, addr)
            except KeyboardInterrupt:
                self.manager.running = False
            except Exception as e:
                print(f'Server error: {e}')

    def _start_client_thread(self, conn, addr):
        threading.Thread(target=self.handle_client, args=(conn, addr)).start()

    def stop(self):
        self.manager.running = False
        self.socket.close()


if __name__ == '__main__':
    server = IoTServer()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
