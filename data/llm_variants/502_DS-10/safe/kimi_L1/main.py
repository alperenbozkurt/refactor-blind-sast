import json
import hashlib
import socket
import threading
from datetime import datetime


class IoTDeviceManager:
    """Manages registered IoT devices, firmware binaries, and the command queue."""

    COMMAND_UPDATE_FIRMWARE = 'UPDATE_FIRMWARE'

    _REQUIRED_DEVICE_FIELDS = ('device_id', 'ip_address', 'firmware_version')
    _REQUIRED_FIRMWARE_FIELDS = ('version', 'compatible_versions')

    def __init__(self):
        self.devices = {}
        self.command_queue = []
        self.firmware_cache = {}
        self.running = False

    def _validate_device(self, device_data):
        return all(field in device_data for field in self._REQUIRED_DEVICE_FIELDS)

    def _parse_firmware_metadata(self, raw_metadata):
        try:
            return json.loads(raw_metadata)
        except json.JSONDecodeError:
            if isinstance(raw_metadata, dict):
                return raw_metadata
            raise ValueError('Invalid firmware metadata format')

    def _validate_firmware_metadata(self, metadata):
        if not isinstance(metadata, dict):
            return False
        if not all(field in metadata for field in self._REQUIRED_FIRMWARE_FIELDS):
            return False
        return isinstance(metadata['compatible_versions'], list)

    def _cache_firmware(self, binary, metadata):
        firmware_id = hashlib.sha256(binary).hexdigest()
        self.firmware_cache[firmware_id] = {'binary': binary, 'metadata': metadata}
        return firmware_id

    def _queue_update_commands(self, firmware_id, firmware_meta):
        for device_id, device in self.devices.items():
            if device['firmware_version'] in firmware_meta['compatible_versions']:
                self.command_queue.append({
                    'device_id': device_id,
                    'command': self.COMMAND_UPDATE_FIRMWARE,
                    'firmware_id': firmware_id,
                    'timestamp': str(datetime.utcnow()),
                })

    def process_firmware_update(self, firmware_data):
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
    """TCP server that routes client messages to the device manager."""

    TYPE_REGISTER_DEVICE = 'REGISTER_DEVICE'
    TYPE_UPLOAD_FIRMWARE = 'UPLOAD_FIRMWARE'
    TYPE_GET_COMMANDS = 'GET_COMMANDS'

    RESP_REGISTRATION_SUCCESS = b'REGISTRATION_SUCCESS'
    RESP_REGISTRATION_FAILED = b'REGISTRATION_FAILED'
    RESP_FIRMWARE_UPLOAD_SUCCESS = b'FIRMWARE_UPLOAD_SUCCESS'
    RESP_FIRMWARE_UPLOAD_FAILED = b'FIRMWARE_UPLOAD_FAILED'
    RESP_INVALID_MESSAGE_TYPE = b'INVALID_MESSAGE_TYPE'
    RESP_INVALID_MESSAGE_FORMAT = b'INVALID_MESSAGE_FORMAT'

    _BUFFER_SIZE = 4096
    _LISTEN_BACKLOG = 5

    def __init__(self, host='0.0.0.0', port=8080):
        self.host = host
        self.port = port
        self.manager = IoTDeviceManager()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def _handle_register_device(self, conn, message):
        success = self.manager.register_device(message['data'])
        response = self.RESP_REGISTRATION_SUCCESS if success else self.RESP_REGISTRATION_FAILED
        conn.sendall(response)

    def _handle_upload_firmware(self, conn, message):
        firmware_data = {
            'binary': message['binary'].encode(),
            'metadata': message['metadata'],
        }
        success = self.manager.process_firmware_update(firmware_data)
        response = self.RESP_FIRMWARE_UPLOAD_SUCCESS if success else self.RESP_FIRMWARE_UPLOAD_FAILED
        conn.sendall(response)

    def _handle_get_commands(self, conn, message):
        device_id = message['device_id']
        commands = [cmd for cmd in self.manager.command_queue if cmd['device_id'] == device_id]
        self.manager.command_queue = [
            cmd for cmd in self.manager.command_queue if cmd['device_id'] != device_id
        ]
        conn.sendall(json.dumps(commands).encode())

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(self._BUFFER_SIZE)
            if not data:
                return
            message = json.loads(data.decode())
            if message['type'] == self.TYPE_REGISTER_DEVICE:
                self._handle_register_device(conn, message)
            elif message['type'] == self.TYPE_UPLOAD_FIRMWARE:
                self._handle_upload_firmware(conn, message)
            elif message['type'] == self.TYPE_GET_COMMANDS:
                self._handle_get_commands(conn, message)
            else:
                conn.sendall(self.RESP_INVALID_MESSAGE_TYPE)
        except json.JSONDecodeError as e:
            print(f'Invalid message format: {e}')
            conn.sendall(self.RESP_INVALID_MESSAGE_FORMAT)
        except Exception as e:
            print(f'Client handling error: {e}')
        finally:
            conn.close()

    def start(self):
        self.manager.running = True
        self.socket.bind((self.host, self.port))
        self.socket.listen(self._LISTEN_BACKLOG)
        print(f'IoT Server started on {self.host}:{self.port}')
        while self.manager.running:
            try:
                conn, addr = self.socket.accept()
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
