import pickle
import json
import hashlib
import io
import socket
import threading
from datetime import datetime


class _RestrictedUnpickler(pickle.Unpickler):
    """Unpickler that refuses to resolve any global.

    Plain data (dict, list, str, numbers, ...) loads normally, but
    untrusted input cannot import or call arbitrary objects.
    """

    def find_class(self, module, name):
        raise pickle.UnpicklingError(f'Global {module}.{name} is forbidden')


def _safe_pickle_loads(data):
    return _RestrictedUnpickler(io.BytesIO(data)).load()


class IoTDeviceManager:
    REQUIRED_DEVICE_FIELDS = ('device_id', 'ip_address', 'firmware_version')
    REQUIRED_FIRMWARE_FIELDS = ('version', 'compatible_versions')

    def __init__(self):
        self.devices = {}
        self.command_queue = []
        self.firmware_cache = {}
        self.running = False

    def _validate_device(self, device_data):
        return all(field in device_data for field in self.REQUIRED_DEVICE_FIELDS)

    def _validate_firmware_metadata(self, metadata):
        return isinstance(metadata, dict) and all(
            field in metadata for field in self.REQUIRED_FIRMWARE_FIELDS
        )

    def _queue_firmware_updates(self, firmware_id, firmware_meta):
        compatible = firmware_meta['compatible_versions']
        for device_id, device in self.devices.items():
            if device['firmware_version'] in compatible:
                self.command_queue.append({
                    'device_id': device_id,
                    'command': 'UPDATE_FIRMWARE',
                    'firmware_id': firmware_id,
                    'timestamp': str(datetime.utcnow()),
                })

    def process_firmware_update(self, firmware_data):
        try:
            firmware_meta = _safe_pickle_loads(firmware_data['metadata'])
            if not self._validate_firmware_metadata(firmware_meta):
                return False
            binary = firmware_data['binary']
            firmware_id = hashlib.sha256(binary).hexdigest()
            self.firmware_cache[firmware_id] = {
                'binary': binary,
                'metadata': firmware_meta,
            }
            self._queue_firmware_updates(firmware_id, firmware_meta)
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
        handlers = {
            'REGISTER_DEVICE': self._handle_register_device,
            'UPLOAD_FIRMWARE': self._handle_upload_firmware,
            'GET_COMMANDS': self._handle_get_commands,
        }
        try:
            data = conn.recv(4096)
            if not data:
                return
            message = json.loads(data.decode())
            handler = handlers.get(message['type'])
            if handler is None:
                conn.sendall(b'INVALID_MESSAGE_TYPE')
            else:
                handler(conn, message)
        except Exception as e:
            print(f'Client handling error: {e}')
        finally:
            conn.close()

    def start(self):
        self.manager.running = True
        self.socket.bind((self.host, self.port))
        self.socket.listen(5)
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
