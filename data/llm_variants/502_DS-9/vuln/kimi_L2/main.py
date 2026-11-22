import socket
import pickle
import threading
import time
import hashlib
from collections import OrderedDict

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 8080
DEFAULT_MAX_CACHE_SIZE = 1000
DEFAULT_SERIALIZER = 'pickle'

RECV_BUFFER_SIZE = 4096

# Protocol commands.
COMMAND_STORE = 'STORE'
COMMAND_REPLICATE = 'REPLICATE'
COMMAND_RETRIEVE = 'RETRIEVE'
COMMAND_ADD_PEER = 'ADD_PEER'

# Protocol responses.
RESPONSE_SUCCESS = b'SUCCESS'
RESPONSE_FAILURE = b'FAILURE'
RESPONSE_REPLICATED = b'REPLICATED'
RESPONSE_FAILED = b'FAILED'
RESPONSE_NOT_FOUND = b'NOT_FOUND'
RESPONSE_PEER_ADDED = b'PEER_ADDED'
RESPONSE_INVALID_COMMAND = b'INVALID_COMMAND'


class CacheNode:
    """A single node in a distributed cache.

    Stores key/value pairs in memory with oldest-first eviction, optionally
    replicates writes to peer nodes, and serves a small pickle-based TCP
    protocol.
    """

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.cache = OrderedDict()
        self.max_cache_size = DEFAULT_MAX_CACHE_SIZE
        self.peers = []
        self.running = False
        self.serializer = DEFAULT_SERIALIZER

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def _evict_oldest(self):
        if len(self.cache) >= self.max_cache_size:
            self.cache.popitem(last=False)

    def _deserialize(self, data):
        if isinstance(data, bytes) and self.serializer == 'pickle':
            return pickle.loads(data)
        return data

    def store_data(self, key, data, replicate=False):
        try:
            data = self._deserialize(data)
            self._evict_oldest()
            self.cache[key] = data
            if replicate:
                serialized = pickle.dumps(data)
                self._replicate_to_peers(key, serialized)
            return True
        except Exception as e:
            print(f'Storage failed: {e}')
            return False

    # ------------------------------------------------------------------
    # Replication
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Client request handling
    # ------------------------------------------------------------------

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(RECV_BUFFER_SIZE)
            if not data:
                return
            message = pickle.loads(data)
            conn.sendall(self._dispatch_command(message))
        except Exception as e:
            print(f'Client handling error: {e}')
        finally:
            conn.close()

    def _dispatch_command(self, message):
        handlers = {
            COMMAND_STORE: self._handle_store,
            COMMAND_REPLICATE: self._handle_replicate,
            COMMAND_RETRIEVE: self._handle_retrieve,
            COMMAND_ADD_PEER: self._handle_add_peer,
        }
        handler = handlers.get(message['command'])
        if handler is None:
            return RESPONSE_INVALID_COMMAND
        return handler(message)

    def _handle_store(self, message):
        success = self.store_data(message['key'], message['data'])
        return RESPONSE_SUCCESS if success else RESPONSE_FAILURE

    def _handle_replicate(self, message):
        success = self.store_data(message['key'], message['data'], replicate=False)
        return RESPONSE_REPLICATED if success else RESPONSE_FAILED

    def _handle_retrieve(self, message):
        result = self.cache.get(message['key'])
        return pickle.dumps(result) if result else RESPONSE_NOT_FOUND

    def _handle_add_peer(self, message):
        self.peers.append(message['peer'])
        return RESPONSE_PEER_ADDED

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------

    def start(self):
        self.running = True
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen()
            print(f'Cache node started on {self.host}:{self.port}')
            self._accept_loop(server_socket)

    def _accept_loop(self, server_socket):
        while self.running:
            try:
                (conn, addr) = server_socket.accept()
                self._start_client_thread(conn, addr)
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                print(f'Server error: {e}')

    def _start_client_thread(self, conn, addr):
        threading.Thread(target=self.handle_client, args=(conn, addr)).start()

    def stop(self):
        self.running = False


def main():
    node = CacheNode()
    try:
        node.start()
    except KeyboardInterrupt:
        node.stop()


if __name__ == '__main__':
    main()
