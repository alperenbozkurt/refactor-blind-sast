"""Device configuration server.

Stores and retrieves encrypted device configurations over a simple
TCP protocol.
"""

import pickle
import socket
import sys
import threading

from cryptography.fernet import Fernet

# Wire protocol constants.
HEADER_SIZE = 4
DEVICE_ID_SIZE = 32
DEVICE_ID_END = HEADER_SIZE + DEVICE_ID_SIZE
RECV_BUFFER_SIZE = 4096

CMD_STORE = b'STOR'
CMD_GET_CONFIG = b'GETC'

RESP_SUCCESS = b'SUCC'
RESP_FAILURE = b'FAIL'
RESP_DATA = b'DATA'
RESP_INVALID = b'INVD'

REQUIRED_CONFIG_FIELDS = ('hostname', 'ip', 'config')


class DeviceConfigManager:
    """Stores device configurations encrypted at rest and tracks versions."""

    def __init__(self):
        self.devices = {}
        self.config_versions = {}
        self.cipher = Fernet(Fernet.generate_key())

    def _validate_config(self, config):
        return all(field in config for field in REQUIRED_CONFIG_FIELDS)

    def store_config(self, device_id, config_data):
        try:
            config = pickle.loads(config_data)
            if not self._validate_config(config):
                return False
            encrypted_config = self.cipher.encrypt(pickle.dumps(config['config']))
            self.devices[device_id] = {
                'hostname': config['hostname'],
                'ip': config['ip'],
                'config': encrypted_config,
            }
            self.config_versions[device_id] = (
                self.config_versions.get(device_id, 0) + 1
            )
            return True
        except Exception as e:
            print(f'Config storage failed: {e}')
            return False

    def get_config(self, device_id):
        if device_id not in self.devices:
            return None
        try:
            encrypted_config = self.devices[device_id]['config']
            decrypted_config = self.cipher.decrypt(encrypted_config)
            return pickle.loads(decrypted_config)
        except Exception as e:
            print(f'Config retrieval failed: {e}')
            return None


class ConfigServer:
    """TCP server that handles configuration storage and retrieval requests."""

    def __init__(self, host='0.0.0.0', port=65432):
        self.host = host
        self.port = port
        self.manager = DeviceConfigManager()
        self.running = False

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(RECV_BUFFER_SIZE)
            if not data:
                return
            header = data[:HEADER_SIZE]
            if header == CMD_STORE:
                self._handle_store(conn, data)
            elif header == CMD_GET_CONFIG:
                self._handle_get_config(conn, data)
            else:
                conn.sendall(RESP_INVALID)
        except Exception as e:
            print(f'Client handling error: {e}')
        finally:
            conn.close()

    def _handle_store(self, conn, data):
        device_id = data[HEADER_SIZE:DEVICE_ID_END].decode()
        config_data = data[DEVICE_ID_END:]
        success = self.manager.store_config(device_id, config_data)
        conn.sendall(RESP_SUCCESS if success else RESP_FAILURE)

    def _handle_get_config(self, conn, data):
        device_id = data[HEADER_SIZE:DEVICE_ID_END].decode()
        config = self.manager.get_config(device_id)
        if config:
            conn.sendall(RESP_DATA + pickle.dumps(config))
        else:
            conn.sendall(RESP_FAILURE)

    def start(self):
        self.running = True
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen()
            print(f'Server started on {self.host}:{self.port}')
            while self.running:
                try:
                    conn, addr = server_socket.accept()
                    threading.Thread(
                        target=self.handle_client, args=(conn, addr)
                    ).start()
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
