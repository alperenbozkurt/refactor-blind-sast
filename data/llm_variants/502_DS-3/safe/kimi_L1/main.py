import json
import socket
import sys
import threading

from cryptography.fernet import Fernet

# Protocol commands (client -> server)
CMD_STORE = b'STOR'
CMD_GET = b'GETC'

# Protocol responses (server -> client)
RESP_SUCCESS = b'SUCC'
RESP_FAILURE = b'FAIL'
RESP_DATA = b'DATA'
RESP_INVALID = b'INVD'

# Wire format and connection settings
HEADER_LENGTH = 4
DEVICE_ID_LENGTH = 32
RECV_BUFFER_SIZE = 4096

REQUIRED_CONFIG_FIELDS = ('hostname', 'ip', 'config')


class DeviceConfigManager:
    """Stores and retrieves encrypted device configurations."""

    def __init__(self):
        self.devices = {}
        self.config_versions = {}
        self.cipher = Fernet(Fernet.generate_key())

    def _validate_config(self, config):
        return all(field in config for field in REQUIRED_CONFIG_FIELDS)

    def store_config(self, device_id, config_data):
        try:
            config = json.loads(config_data.decode('utf-8'))
            if not self._validate_config(config):
                return False
            encrypted_config = self.cipher.encrypt(
                json.dumps(config['config']).encode('utf-8')
            )
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
            decrypted = self.cipher.decrypt(self.devices[device_id]['config'])
            return json.loads(decrypted.decode('utf-8'))
        except Exception as e:
            print(f'Config retrieval failed: {e}')
            return None


class ConfigServer:
    """TCP server that stores and serves encrypted device configurations."""

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
            header = data[:HEADER_LENGTH]
            if header == CMD_STORE:
                self._handle_store(conn, data)
            elif header == CMD_GET:
                self._handle_get(conn, data)
            else:
                conn.sendall(RESP_INVALID)
        except Exception as e:
            print(f'Client handling error: {e}')
        finally:
            conn.close()

    def _handle_store(self, conn, data):
        device_id = self._extract_device_id(data)
        config_data = data[HEADER_LENGTH + DEVICE_ID_LENGTH:]
        success = self.manager.store_config(device_id, config_data)
        conn.sendall(RESP_SUCCESS if success else RESP_FAILURE)

    def _handle_get(self, conn, data):
        device_id = self._extract_device_id(data)
        config = self.manager.get_config(device_id)
        if config:
            conn.sendall(RESP_DATA + json.dumps(config).encode('utf-8'))
        else:
            conn.sendall(RESP_FAILURE)

    @staticmethod
    def _extract_device_id(data):
        return data[HEADER_LENGTH:HEADER_LENGTH + DEVICE_ID_LENGTH].decode()

    def start(self):
        self.running = True
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.host, self.port))
            s.listen()
            print(f'Server started on {self.host}:{self.port}')
            while self.running:
                try:
                    conn, addr = s.accept()
                    threading.Thread(
                        target=self.handle_client, args=(conn, addr)
                    ).start()
                except KeyboardInterrupt:
                    self.running = False
                except Exception as e:
                    print(f'Server error: {e}')

    def stop(self):
        self.running = False


def main():
    server = ConfigServer()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
        sys.exit(0)


if __name__ == '__main__':
    main()
