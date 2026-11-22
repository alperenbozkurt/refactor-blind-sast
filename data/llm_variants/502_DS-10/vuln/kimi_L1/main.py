"""TCP server for managing IoT devices and distributing firmware updates."""

import hashlib
import json
import pickle
import socket
import threading
from datetime import datetime


class IoTDeviceManager:
    """Tracks registered devices, cached firmware, and pending commands."""

    REQUIRED_DEVICE_FIELDS = ('device_id', 'ip_address', 'firmware_version')
    REQUIRED_METADATA_FIELDS = ('version', 'compatible_versions')

    def __init__(self):
        self.devices = {}
        self.command_queue = []
        self.firmware_cache = {}
        self.running = False

    def register_device(self, device_data):
        """Register a device from a JSON payload.

        Returns True on success, False on any parsing or validation error.
        """
        try:
            device = json.loads(device_data)
            if not self._validate_device(device):
                return False
            self.devices[device['device_id']] = device
            return True
        except Exception as exc:
            print(f'Device registration failed: {exc}')
            return False

    def process_firmware_update(self, firmware_data):
        """Validate, cache, and distribute a firmware image.

        Queues an UPDATE_FIRMWARE command for every registered device whose
        firmware version is listed as compatible. Returns True on success.
        """
        try:
            firmware_meta = pickle.loads(firmware_data['metadata'])
            if not self._validate_firmware_metadata(firmware_meta):
                return False

            firmware_id = hashlib.sha256(firmware_data['binary']).hexdigest()
            self.firmware_cache[firmware_id] = {
                'binary': firmware_data['binary'],
                'metadata': firmware_meta,
            }

            for device_id, device in self.devices.items():
                if device['firmware_version'] in firmware_meta['compatible_versions']:
                    self.command_queue.append({
                        'device_id': device_id,
                        'command': 'UPDATE_FIRMWARE',
                        'firmware_id': firmware_id,
                        'timestamp': str(datetime.utcnow()),
                    })
            return True
        except Exception as exc:
            print(f'Firmware processing failed: {exc}')
            return False

    def _validate_device(self, device_data):
        """Return True when every required device field is present."""
        return all(field in device_data for field in self.REQUIRED_DEVICE_FIELDS)

    def _validate_firmware_metadata(self, metadata):
        """Return True when the metadata contains the required fields."""
        if not isinstance(metadata, dict):
            return False
        return all(field in metadata for field in self.REQUIRED_METADATA_FIELDS)


class IoTServer:
    """Serves the IoT device management protocol over TCP."""

    RECV_BUFFER_SIZE = 4096
    LISTEN_BACKLOG = 5

    def __init__(self, host='0.0.0.0', port=8080):
        self.host = host
        self.port = port
        self.manager = IoTDeviceManager()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def handle_client(self, conn, addr):
        """Process a single client request, then close the connection."""
        try:
            data = conn.recv(self.RECV_BUFFER_SIZE)
            if not data:
                return
            message = json.loads(data.decode())
            message_type = message['type']

            if message_type == 'REGISTER_DEVICE':
                success = self.manager.register_device(message['data'])
                conn.sendall(
                    b'REGISTRATION_SUCCESS' if success else b'REGISTRATION_FAILED'
                )
            elif message_type == 'UPLOAD_FIRMWARE':
                firmware_data = {
                    'binary': message['binary'].encode(),
                    'metadata': message['metadata'],
                }
                success = self.manager.process_firmware_update(firmware_data)
                conn.sendall(
                    b'FIRMWARE_UPLOAD_SUCCESS' if success else b'FIRMWARE_UPLOAD_FAILED'
                )
            elif message_type == 'GET_COMMANDS':
                commands = self._pop_device_commands(message['device_id'])
                conn.sendall(json.dumps(commands).encode())
            else:
                conn.sendall(b'INVALID_MESSAGE_TYPE')
        except Exception as exc:
            print(f'Client handling error: {exc}')
        finally:
            conn.close()

    def _pop_device_commands(self, device_id):
        """Remove and return all queued commands for the given device."""
        commands = [
            cmd for cmd in self.manager.command_queue
            if cmd['device_id'] == device_id
        ]
        self.manager.command_queue = [
            cmd for cmd in self.manager.command_queue
            if cmd['device_id'] != device_id
        ]
        return commands

    def start(self):
        """Bind the listening socket and serve clients until stopped."""
        self.manager.running = True
        self.socket.bind((self.host, self.port))
        self.socket.listen(self.LISTEN_BACKLOG)
        print(f'IoT Server started on {self.host}:{self.port}')
        while self.manager.running:
            try:
                conn, addr = self.socket.accept()
                threading.Thread(
                    target=self.handle_client,
                    args=(conn, addr),
                ).start()
            except KeyboardInterrupt:
                self.manager.running = False
            except Exception as exc:
                print(f'Server error: {exc}')

    def stop(self):
        """Stop the accept loop and close the listening socket."""
        self.manager.running = False
        self.socket.close()


if __name__ == '__main__':
    server = IoTServer()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
