import socket
import pickle
import threading
import time
import hashlib
from collections import OrderedDict

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 8080
MAX_CACHE_SIZE = 1000
BUFFER_SIZE = 4096
PICKLE_SERIALIZER = 'pickle'

COMMAND_STORE = 'STORE'
COMMAND_REPLICATE = 'REPLICATE'
COMMAND_RETRIEVE = 'RETRIEVE'
COMMAND_ADD_PEER = 'ADD_PEER'

RESPONSE_SUCCESS = b'SUCCESS'
RESPONSE_FAILURE = b'FAILURE'
RESPONSE_REPLICATED = b'REPLICATED'
RESPONSE_FAILED = b'FAILED'
RESPONSE_NOT_FOUND = b'NOT_FOUND'
RESPONSE_PEER_ADDED = b'PEER_ADDED'
RESPONSE_INVALID_COMMAND = b'INVALID_COMMAND'


class CacheNode:
    """TCP cache node with bounded insertion-ordered storage and peer replication."""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.cache = OrderedDict()
        self.max_cache_size = MAX_CACHE_SIZE
        self.peers = []
        self.running = False
        self.serializer = PICKLE_SERIALIZER

    def _evict_oldest(self):
        if len(self.cache) >= self.max_cache_size:
            self.cache.popitem(last=False)

    def store_data(self, key, data, replicate=False):
        try:
            if isinstance(data, bytes) and self.serializer == PICKLE_SERIALIZER:
                data = pickle.loads(data)
            self._evict_oldest()
            self.cache[key] = data
            if replicate:
                self._replicate_to_peers(key, pickle.dumps(data))
            return True
        except Exception as e:
            print(f'Storage failed: {e}')
            return False

    def _replicate_to_peers(self, key, data):
        message = {'command': COMMAND_REPLICATE, 'key': key, 'data': data}
        for peer in self.peers:
            try:
                self._send_message(peer['host'], peer['port'], message)
            except Exception as e:
                print(f'Replication to {peer} failed: {e}')

    @staticmethod
    def _send_message(host, port, message):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))
            s.sendall(pickle.dumps(message))

    def _handle_store(self, conn, message):
        success = self.store_data(message['key'], message['data'])
        conn.sendall(RESPONSE_SUCCESS if success else RESPONSE_FAILURE)

    def _handle_replicate(self, conn, message):
        success = self.store_data(message['key'], message['data'], replicate=False)
        conn.sendall(RESPONSE_REPLICATED if success else RESPONSE_FAILED)

    def _handle_retrieve(self, conn, message):
        result = self.cache.get(message['key'])
        conn.sendall(pickle.dumps(result) if result else RESPONSE_NOT_FOUND)

    def _handle_add_peer(self, conn, message):
        self.peers.append(message['peer'])
        conn.sendall(RESPONSE_PEER_ADDED)

    def _command_handlers(self):
        return {
            COMMAND_STORE: self._handle_store,
            COMMAND_REPLICATE: self._handle_replicate,
            COMMAND_RETRIEVE: self._handle_retrieve,
            COMMAND_ADD_PEER: self._handle_add_peer,
        }

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(BUFFER_SIZE)
            if not data:
                return
            message = pickle.loads(data)
            handler = self._command_handlers().get(message['command'])
            if handler is None:
                conn.sendall(RESPONSE_INVALID_COMMAND)
            else:
                handler(conn, message)
        except Exception as e:
            print(f'Client handling error: {e}')
        finally:
            conn.close()

    def _create_server_socket(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.host, self.port))
            s.listen()
        except Exception:
            s.close()
            raise
        return s

    def start(self):
        self.running = True
        with self._create_server_socket() as s:
            print(f'Cache node started on {self.host}:{self.port}')
            while self.running:
                try:
                    (conn, addr) = s.accept()
                    threading.Thread(target=self.handle_client, args=(conn, addr)).start()
                except KeyboardInterrupt:
                    self.running = False
                except Exception as e:
                    print(f'Server error: {e}')

    def stop(self):
        self.running = False


if __name__ == '__main__':
    node = CacheNode()
    try:
        node.start()
    except KeyboardInterrupt:
        node.stop()
