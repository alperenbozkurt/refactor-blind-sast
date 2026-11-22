"""TCP server for encrypted storage and retrieval of device configurations."""

import json
import socket
import sys
import threading

from cryptography.fernet import Fernet

# ---------------------------------------------------------------------------
# Wire protocol constants
# ---------------------------------------------------------------------------
HEADER_SIZE = 4          # bytes: fixed-width command/response header
DEVICE_ID_SIZE = 32      # bytes: fixed-width device identifier
PAYLOAD_OFFSET = HEADER_SIZE + DEVICE_ID_SIZE
RECV_BUFFER_SIZE = 4096

CMD_STORE = b'STOR'
CMD_GET = b'GETC'

RESP_SUCCESS = b'SUCC'
RESP_FAILURE = b'FAIL'
RESP_DATA = b'DATA'
RESP_INVALID = b'INVD'

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------
REQUIRED_CONFIG_FIELDS = ('hostname', 'ip', 'config')
ENCODING = 'utf-8'

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 65432


def _decode_json(raw_bytes):
    """Decode UTF-8 bytes and parse them as JSON."""
    return json.loads(raw_bytes.decode(ENCODING))


def _encode_json(payload):
    """Serialize ``payload`` to JSON and encode it as UTF-8 bytes."""
    return json.dumps(payload).encode(ENCODING)


def _extract_device_id(data):
    """Extract the fixed-width device id from a raw request payload."""
    return data[HEADER_SIZE:PAYLOAD_OFFSET].decode(ENCODING)


class DeviceConfigManager:
    """Stores device configurations encrypted at rest, with version tracking."""

    def __init__(self):
        self.devices = {}
        self.config_versions = {}
        self.cipher = Fernet(Fernet.generate_key())

    def _validate_config(self, config):
        return all((field in config for field in REQUIRED_CONFIG_FIELDS))

    def _encrypt_config(self, config):
        return self.cipher.encrypt(_encode_json(config))

    def _decrypt_config(self, encrypted_config):
        return _decode_json(self.cipher.decrypt(encrypted_config))

    def _bump_version(self, device_id):
        self.config_versions[device_id] = self.config_versions.get(device_id, 0) + 1

    def store_config(self, device_id, config_data):
        try:
            config = _decode_json(config_data)
            if not self._validate_config(config):
                return False
            self.devices[device_id] = {
                'hostname': config['hostname'],
                'ip': config['ip'],
                'config': self._encrypt_config(config['config']),
            }
            self._bump_version(device_id)
            return True
        except Exception as e:
            print(f'Config storage failed: {e}')
            return False

    def get_config(self, device_id):
        if device_id not in self.devices:
            return None
        try:
            return self._decrypt_config(self.devices[device_id]['config'])
        except Exception as e:
            print(f'Config retrieval failed: {e}')
            return None


class ConfigServer:
    """Multi-threaded TCP server exposing the device configuration protocol."""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.manager = DeviceConfigManager()
        self.running = False

    # -- request handlers ----------------------------------------------------

    def _handle_store(self, conn, data):
        device_id = _extract_device_id(data)
        config_data = data[PAYLOAD_OFFSET:]
        success = self.manager.store_config(device_id, config_data)
        conn.sendall(RESP_SUCCESS if success else RESP_FAILURE)

    def _handle_get(self, conn, data):
        device_id = _extract_device_id(data)
        config = self.manager.get_config(device_id)
        if config:
            conn.sendall(RESP_DATA + _encode_json(config))
        else:
            conn.sendall(RESP_FAILURE)

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(RECV_BUFFER_SIZE)
            if not data:
                return
            handler = {
                CMD_STORE: self._handle_store,
                CMD_GET: self._handle_get,
            }.get(data[:HEADER_SIZE])
            if handler is None:
                conn.sendall(RESP_INVALID)
            else:
                handler(conn, data)
        except Exception as e:
            print(f'Client handling error: {e}')
        finally:
            conn.close()

    # -- lifecycle -----------------------------------------------------------

    def _create_server_socket(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen()
        return server_socket

    def _spawn_client_thread(self, conn, addr):
        threading.Thread(target=self.handle_client, args=(conn, addr)).start()

    def start(self):
        self.running = True
        with self._create_server_socket() as server_socket:
            print(f'Server started on {self.host}:{self.port}')
            while self.running:
                try:
                    (conn, addr) = server_socket.accept()
                    self._spawn_client_thread(conn, addr)
                except KeyboardInterrupt:
                    self.running = False
                except Exception as e:
                    print(f'Server error: {e}')

    def stop(self):
        self.running = False


if __name__ == '__main__':
    server = ConfigServer()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
        sys.exit(0)
