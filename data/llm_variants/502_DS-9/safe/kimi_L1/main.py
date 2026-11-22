"""TCP-based cache node with optional peer replication.

This module implements :class:`CacheNode`, a small in-memory key/value
cache that speaks a JSON-over-TCP protocol and can replicate stored
values to a list of peer nodes. Running the module directly starts a
node with default settings.
"""

# Note: ``base64``, ``hashlib`` and ``time`` are currently unused, but are
# kept so that every pre-existing module-level name remains importable.
import base64
import hashlib
import json
import socket
import threading
import time
from collections import OrderedDict

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 8080
DEFAULT_MAX_CACHE_SIZE = 1000
RECV_BUFFER_SIZE = 4096

SERIALIZER_JSON = 'json'

# ---------------------------------------------------------------------------
# Wire protocol
# ---------------------------------------------------------------------------

COMMAND_STORE = 'STORE'
COMMAND_REPLICATE = 'REPLICATE'
COMMAND_RETRIEVE = 'RETRIEVE'
COMMAND_ADD_PEER = 'ADD_PEER'

RESPONSE_SUCCESS = b'SUCCESS'
RESPONSE_FAILURE = b'FAILURE'
RESPONSE_REPLICATED = b'REPLICATED'
RESPONSE_REPLICATION_FAILED = b'FAILED'
RESPONSE_NOT_FOUND = b'NOT_FOUND'
RESPONSE_PEER_ADDED = b'PEER_ADDED'
RESPONSE_INVALID_PEER_INFO = b'INVALID_PEER_INFO'
RESPONSE_INVALID_COMMAND = b'INVALID_COMMAND'
RESPONSE_INVALID_MESSAGE_FORMAT = b'INVALID_MESSAGE_FORMAT'

REQUIRED_PEER_FIELDS = ('host', 'port')


class CacheNode:
    """In-memory cache node that speaks JSON over TCP and replicates to peers."""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.cache = OrderedDict()
        self.max_cache_size = DEFAULT_MAX_CACHE_SIZE
        self.peers = []
        self.running = False
        self.serializer = SERIALIZER_JSON

    # -- cache internals -----------------------------------------------------

    def _evict_oldest(self):
        """Drop the oldest entry when the cache is at capacity."""
        if len(self.cache) >= self.max_cache_size:
            self.cache.popitem(last=False)

    def _serialize_data(self, data):
        if self.serializer != SERIALIZER_JSON:
            raise ValueError('Unsupported serializer')
        return json.dumps(data).encode('utf-8')

    def _deserialize_data(self, data_bytes):
        if self.serializer != SERIALIZER_JSON:
            raise ValueError('Unsupported serializer')
        return json.loads(data_bytes.decode('utf-8'))

    # -- public API ----------------------------------------------------------

    def store_data(self, key, data, replicate=False):
        """Store ``data`` under ``key``; optionally replicate it to peers."""
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

    # -- replication ---------------------------------------------------------

    def _replicate_to_peers(self, key, data):
        for peer in self.peers:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.connect((peer['host'], peer['port']))
                    message = {
                        'command': COMMAND_REPLICATE,
                        'key': key,
                        'data': data,
                    }
                    sock.sendall(self._serialize_data(message))
            except Exception as e:
                print(f'Replication to {peer} failed: {e}')

    # -- client handling -----------------------------------------------------

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(RECV_BUFFER_SIZE)
            if not data:
                return
            message = self._deserialize_data(data)
            conn.sendall(self._execute_command(message))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f'Invalid message format: {e}')
            conn.sendall(RESPONSE_INVALID_MESSAGE_FORMAT)
        except Exception as e:
            print(f'Client handling error: {e}')
        finally:
            conn.close()

    def _execute_command(self, message):
        """Dispatch a decoded request message and return the response bytes."""
        command = message['command']
        if command == COMMAND_STORE:
            return self._handle_store(message)
        if command == COMMAND_REPLICATE:
            return self._handle_replicate(message)
        if command == COMMAND_RETRIEVE:
            return self._handle_retrieve(message)
        if command == COMMAND_ADD_PEER:
            return self._handle_add_peer(message)
        return RESPONSE_INVALID_COMMAND

    def _handle_store(self, message):
        success = self.store_data(message['key'], message['data'])
        return RESPONSE_SUCCESS if success else RESPONSE_FAILURE

    def _handle_replicate(self, message):
        success = self.store_data(message['key'], message['data'], replicate=False)
        return RESPONSE_REPLICATED if success else RESPONSE_REPLICATION_FAILED

    def _handle_retrieve(self, message):
        result = self.cache.get(message['key'])
        if result is None:
            return RESPONSE_NOT_FOUND
        return self._serialize_data(result)

    def _handle_add_peer(self, message):
        peer = message['peer']
        if self._is_valid_peer(peer):
            self.peers.append(peer)
            return RESPONSE_PEER_ADDED
        return RESPONSE_INVALID_PEER_INFO

    @staticmethod
    def _is_valid_peer(peer):
        return isinstance(peer, dict) and all(
            field in peer for field in REQUIRED_PEER_FIELDS
        )

    # -- lifecycle -----------------------------------------------------------

    def start(self):
        self.running = True
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen()
            print(f'Cache node started on {self.host}:{self.port}')
            while self.running:
                try:
                    conn, addr = server_socket.accept()
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
