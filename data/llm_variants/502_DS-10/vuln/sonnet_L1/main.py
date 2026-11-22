import pickle
import json
import hashlib
import socket
import threading
from datetime import datetime

REQUIRED_DEVICE_FIELDS = ('device_id', 'ip_address', 'firmware_version')
REQUIRED_FIRMWARE_METADATA_FIELDS = ('version', 'compatible_versions')

RECV_BUFFER_SIZE = 4096
LISTEN_BACKLOG = 5


class IoTDeviceManager:

    def __init__(self):
        self.devices = {}
        self.command_queue = []
        self.firmware_cache = {}
        self.running = False

    def _validate_device(self, device_data):
        return all(field in device_data for field in REQUIRED_DEVICE_FIELDS)

    def _validate_firmware_metadata(self, metadata):
        return isinstance(metadata, dict) and all(
            field in metadata for field in REQUIRED_FIRMWARE_METADATA_FIELDS
        )

    def _queue_firmware_update_commands(self, firmware_id, firmware_meta):
        compatible_versions = firmware_meta['compatible_versions']
        for device_id, device in self.devices.items():
            if device['firmware_version'] in compatible_versions:
                self.command_queue.append({
                    'device_id': device_id,
                    'command': 'UPDATE_FIRMWARE',
                    'firmware_id': firmware_id,
                    'timestamp': str(datetime.utcnow()),
                })

    def process_firmware_update(self, firmware_data):
        try:
            # NOTE: behaviour intentionally preserved (metadata is unpickled as-is).
            firmware_meta = pickle.loads(firmware_data['metadata'])
            if not self._validate_firmware_metadata(firmware_meta):
                return False

            binary = firmware_data['binary']
            firmware_id = hashlib.sha256(binary).hexdigest()
            self.firmware_cache[firmware_id] = {
                'binary': binary,
                'metadata': firmware_meta,
            }
            self._queue_firmware_update_commands(firmware_id, firmware_meta)
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

    def __init__(self, host='0.0.0.0', port=8080):
        self.host = host
        self.port = port
        self.manager = IoTDeviceManager()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def _handle_register_device(self, conn, message):
        success = self.manager.register_device(message['data'])
        conn.sendall(b'REGISTRATION_SUCCESS' if success else b'REGISTRATION_FAILED')

    def _handle_upload_firmware(self, conn, message):
        firmware_data = {
            'binary': message['binary'].encode(),
            'metadata': message['metadata'],
        }
        success = self.manager.process_firmware_update(firmware_data)
        conn.sendall(b'FIRMWARE_UPLOAD_SUCCESS' if success else b'FIRMWARE_UPLOAD_FAILED')

    def _handle_get_commands(self, conn, message):
        device_id = message['device_id']
        queue = self.manager.command_queue
        commands = [cmd for cmd in queue if cmd['device_id'] == device_id]
        self.manager.command_queue = [cmd for cmd in queue if cmd['device_id'] != device_id]
        conn.sendall(json.dumps(commands).encode())

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(RECV_BUFFER_SIZE)
            if not data:
                return
            message = json.loads(data.decode())
            message_type = message['type']

            if message_type == 'REGISTER_DEVICE':
                self._handle_register_device(conn, message)
            elif message_type == 'UPLOAD_FIRMWARE':
                self._handle_upload_firmware(conn, message)
            elif message_type == 'GET_COMMANDS':
                self._handle_get_commands(conn, message)
            else:
                conn.sendall(b'INVALID_MESSAGE_TYPE')
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
