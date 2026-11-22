import socket
import pickle
import sys
import threading
from cryptography.fernet import Fernet

# --- Network defaults -------------------------------------------------------
DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 65432
RECV_BUFFER_SIZE = 4096

# --- Wire protocol ----------------------------------------------------------
HEADER_SIZE = 4
DEVICE_ID_END = 36  # device id occupies bytes [HEADER_SIZE:DEVICE_ID_END]

CMD_STORE = b'STOR'
CMD_GET = b'GETC'

RESP_SUCCESS = b'SUCC'
RESP_FAIL = b'FAIL'
RESP_DATA = b'DATA'
RESP_INVALID = b'INVD'

# --- Config schema ----------------------------------------------------------
REQUIRED_CONFIG_FIELDS = ['hostname', 'ip', 'config']


# NOTE: pickle is used for (de)serialisation to preserve the existing wire
# format. Unpickling data from untrusted peers is unsafe; deploy only on
# trusted networks or migrate the protocol to a safe format.
def _serialize(obj):
    return pickle.dumps(obj)


def _deserialize(data):
    return pickle.loads(data)


def _parse_device_id(data):
    """Extract the device id from a raw request."""
    return data[HEADER_SIZE:DEVICE_ID_END].decode()


class DeviceConfigManager:

    def __init__(self):
        self.devices = {}
        self.config_versions = {}
        self.cipher = Fernet(Fernet.generate_key())

    def _validate_config(self, config):
        return all((field in config for field in REQUIRED_CONFIG_FIELDS))

    def _encrypt_config(self, config_body):
        return self.cipher.encrypt(_serialize(config_body))

    def _decrypt_config(self, encrypted):
        return _deserialize(self.cipher.decrypt(encrypted))

    def _bump_version(self, device_id):
        self.config_versions[device_id] = self.config_versions.get(device_id, 0) + 1

    def store_config(self, device_id, config_data):
        try:
            config = _deserialize(config_data)
            if not self._validate_config(config):
                return False
            encrypted_config = self._encrypt_config(config['config'])
            self.devices[device_id] = {
                'hostname': config['hostname'],
                'ip': config['ip'],
                'config': encrypted_config,
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

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.manager = DeviceConfigManager()
        self.running = False

    def _handle_store(self, conn, data):
        device_id = _parse_device_id(data)
        config_data = data[DEVICE_ID_END:]
        success = self.manager.store_config(device_id, config_data)
        conn.sendall(RESP_SUCCESS if success else RESP_FAIL)

    def _handle_get(self, conn, data):
        device_id = _parse_device_id(data)
        config = self.manager.get_config(device_id)
        if config:
            conn.sendall(RESP_DATA + _serialize(config))
        else:
            conn.sendall(RESP_FAIL)

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(RECV_BUFFER_SIZE)
            if not data:
                return
            header = data[:HEADER_SIZE]
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

    def _spawn_handler(self, conn, addr):
        threading.Thread(target=self.handle_client, args=(conn, addr)).start()

    def _create_listening_socket(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        return s

    def start(self):
        self.running = True
        with self._create_listening_socket() as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.host, self.port))
            s.listen()
            print(f'Server started on {self.host}:{self.port}')
            while self.running:
                try:
                    (conn, addr) = s.accept()
                    self._spawn_handler(conn, addr)
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
