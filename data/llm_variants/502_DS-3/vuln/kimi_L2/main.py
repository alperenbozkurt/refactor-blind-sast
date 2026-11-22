"""Encrypted device configuration server.

Stores device configurations (encrypted at rest with Fernet) and serves
them over a simple TCP protocol with STOR/GETC commands.
"""

import pickle
import socket
import sys
import threading
from typing import Any, Dict

from cryptography.fernet import Fernet

# ---------------------------------------------------------------------------
# Wire protocol
# ---------------------------------------------------------------------------
CMD_STORE = b'STOR'
CMD_GET = b'GETC'

RESP_SUCCESS = b'SUCC'
RESP_FAILURE = b'FAIL'
RESP_DATA = b'DATA'
RESP_INVALID = b'INVD'

HEADER_SIZE = 4
DEVICE_ID_LENGTH = 32
DEVICE_ID_SLICE = slice(HEADER_SIZE, HEADER_SIZE + DEVICE_ID_LENGTH)
PAYLOAD_OFFSET = HEADER_SIZE + DEVICE_ID_LENGTH
RECV_BUFFER_SIZE = 4096

# ---------------------------------------------------------------------------
# Server defaults
# ---------------------------------------------------------------------------
DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 65432

# Fields every uploaded configuration must contain.
REQUIRED_CONFIG_FIELDS = ('hostname', 'ip', 'config')


class DeviceConfigManager:
    """Stores and retrieves encrypted device configurations."""

    def __init__(self):
        self.devices: Dict[str, Dict[str, Any]] = {}
        self.config_versions: Dict[str, int] = {}
        self.cipher = Fernet(Fernet.generate_key())

    def _validate_config(self, config):
        return all(field in config for field in REQUIRED_CONFIG_FIELDS)

    def _encrypt_config(self, config: Any) -> bytes:
        return self.cipher.encrypt(pickle.dumps(config))

    def _decrypt_config(self, encrypted_config: bytes) -> Any:
        return pickle.loads(self.cipher.decrypt(encrypted_config))

    def _build_record(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'hostname': config['hostname'],
            'ip': config['ip'],
            'config': self._encrypt_config(config['config']),
        }

    def _bump_version(self, device_id: str) -> None:
        self.config_versions[device_id] = (
            self.config_versions.get(device_id, 0) + 1
        )

    def store_config(self, device_id, config_data):
        try:
            config = pickle.loads(config_data)
            if not self._validate_config(config):
                return False
            self.devices[device_id] = self._build_record(config)
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
    """TCP server that handles STOR/GETC configuration requests."""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.manager = DeviceConfigManager()
        self.running = False

    # -- request handling ---------------------------------------------------

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(RECV_BUFFER_SIZE)
            if not data:
                return
            command = data[:HEADER_SIZE]
            if command == CMD_STORE:
                self._handle_store(conn, data)
            elif command == CMD_GET:
                self._handle_get(conn, data)
            else:
                conn.sendall(RESP_INVALID)
        except Exception as e:
            print(f'Client handling error: {e}')
        finally:
            conn.close()

    def _handle_store(self, conn, data: bytes) -> None:
        device_id = data[DEVICE_ID_SLICE].decode()
        config_data = data[PAYLOAD_OFFSET:]
        success = self.manager.store_config(device_id, config_data)
        conn.sendall(RESP_SUCCESS if success else RESP_FAILURE)

    def _handle_get(self, conn, data: bytes) -> None:
        device_id = data[DEVICE_ID_SLICE].decode()
        config = self.manager.get_config(device_id)
        if config:
            conn.sendall(RESP_DATA + pickle.dumps(config))
        else:
            conn.sendall(RESP_FAILURE)

    # -- lifecycle ------------------------------------------------------------

    def start(self):
        self.running = True
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.host, self.port))
            s.listen()
            print(f'Server started on {self.host}:{self.port}')
            while self.running:
                try:
                    (conn, addr) = s.accept()
                    self._spawn_client_handler(conn, addr)
                except KeyboardInterrupt:
                    self.running = False
                except Exception as e:
                    print(f'Server error: {e}')

    def stop(self):
        self.running = False

    def _spawn_client_handler(self, conn, addr) -> None:
        threading.Thread(target=self.handle_client, args=(conn, addr)).start()


def main() -> None:
    server = ConfigServer()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
        sys.exit(0)


if __name__ == '__main__':
    main()
