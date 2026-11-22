import socket
import json
import threading
import time
import hashlib
from collections import OrderedDict
import base64

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 8080
MAX_CACHE_SIZE = 1000
RECV_BUFFER_SIZE = 4096

SERIALIZER_JSON = 'json'

# Supported protocol commands.
COMMAND_STORE = 'STORE'
COMMAND_REPLICATE = 'REPLICATE'
COMMAND_RETRIEVE = 'RETRIEVE'
COMMAND_ADD_PEER = 'ADD_PEER'

# Protocol response payloads.
RESPONSE_SUCCESS = b'SUCCESS'
RESPONSE_FAILURE = b'FAILURE'
RESPONSE_REPLICATED = b'REPLICATED'
RESPONSE_REPLICATE_FAILED = b'FAILED'
RESPONSE_NOT_FOUND = b'NOT_FOUND'
RESPONSE_PEER_ADDED = b'PEER_ADDED'
RESPONSE_INVALID_PEER_INFO = b'INVALID_PEER_INFO'
RESPONSE_INVALID_COMMAND = b'INVALID_COMMAND'
RESPONSE_INVALID_MESSAGE_FORMAT = b'INVALID_MESSAGE_FORMAT'


def _is_valid_peer_info(peer):
    """Return True if *peer* is a mapping containing both host and port."""
    return isinstance(peer, dict) and 'host' in peer and 'port' in peer


class CacheNode:

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.cache = OrderedDict()
        self.max_cache_size = MAX_CACHE_SIZE
        self.peers = []
        self.running = False
        self.serializer = SERIALIZER_JSON

    # ------------------------------------------------------------------
    # Cache maintenance
    # ------------------------------------------------------------------

    def _evict_oldest(self):
        if len(self.cache) >= self.max_cache_size:
            self.cache.popitem(last=False)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def _serialize_data(self, data):
        if self.serializer == SERIALIZER_JSON:
            return json.dumps(data).encode('utf-8')
        else:
            raise ValueError('Unsupported serializer')

    def _deserialize_data(self, data_bytes):
        if self.serializer == SERIALIZER_JSON:
            return json.loads(data_bytes.decode('utf-8'))
        else:
            raise ValueError('Unsupported serializer')

    # ------------------------------------------------------------------
    # Storage and replication
    # ------------------------------------------------------------------

    def store_data(self, key, data, replicate=False):
        try:
            if isinstance(data, bytes):
                data = self._deserialize_data(data)
            self._evict_oldest()
            self.cache[key] = data
            if replicate:
                serialized = self._serialize_data(data)
                self._replicate_to_peers(key, serialized)
            return True
        except Exception as e:
            print(f'Storage failed: {e}')
            return False

    def _replicate_to_peers(self, key, data):
        for peer in self.peers:
            try:
                self._send_replication(peer, key, data)
            except Exception as e:
                print(f'Replication to {peer} failed: {e}')

    def _send_replication(self, peer, key, data):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((peer['host'], peer['port']))
            message = {'command': COMMAND_REPLICATE, 'key': key, 'data': data}
            s.sendall(self._serialize_data(message))

    # ------------------------------------------------------------------
    # Client request handling
    # ------------------------------------------------------------------

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(RECV_BUFFER_SIZE)
            if not data:
                return
            message = self._deserialize_data(data)
            self._dispatch_command(conn, message)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f'Invalid message format: {e}')
            conn.sendall(RESPONSE_INVALID_MESSAGE_FORMAT)
        except Exception as e:
            print(f'Client handling error: {e}')
        finally:
            conn.close()

    def _dispatch_command(self, conn, message):
        if message['command'] == COMMAND_STORE:
            self._handle_store(conn, message)
        elif message['command'] == COMMAND_REPLICATE:
            self._handle_replicate(conn, message)
        elif message['command'] == COMMAND_RETRIEVE:
            self._handle_retrieve(conn, message)
        elif message['command'] == COMMAND_ADD_PEER:
            self._handle_add_peer(conn, message)
        else:
            conn.sendall(RESPONSE_INVALID_COMMAND)

    def _handle_store(self, conn, message):
        success = self.store_data(message['key'], message['data'])
        conn.sendall(RESPONSE_SUCCESS if success else RESPONSE_FAILURE)

    def _handle_replicate(self, conn, message):
        success = self.store_data(message['key'], message['data'], replicate=False)
        conn.sendall(RESPONSE_REPLICATED if success else RESPONSE_REPLICATE_FAILED)

    def _handle_retrieve(self, conn, message):
        result = self.cache.get(message['key'])
        if result is not None:
            conn.sendall(self._serialize_data(result))
        else:
            conn.sendall(RESPONSE_NOT_FOUND)

    def _handle_add_peer(self, conn, message):
        if _is_valid_peer_info(message['peer']):
            self.peers.append(message['peer'])
            conn.sendall(RESPONSE_PEER_ADDED)
        else:
            conn.sendall(RESPONSE_INVALID_PEER_INFO)

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------

    def start(self):
        self.running = True
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.host, self.port))
            s.listen()
            print(f'Cache node started on {self.host}:{self.port}')
            self._accept_loop(s)

    def _accept_loop(self, server_socket):
        while self.running:
            try:
                (conn, addr) = server_socket.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr)).start()
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                print(f'Server error: {e}')

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
