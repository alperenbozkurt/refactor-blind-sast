import socket
import json
import threading
import time
import hashlib
from collections import OrderedDict
import base64

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 8080
DEFAULT_MAX_CACHE_SIZE = 1000
DEFAULT_SERIALIZER = 'json'
SERIALIZER_JSON = 'json'
ENCODING = 'utf-8'
RECV_BUFFER_SIZE = 4096

# Commands
CMD_STORE = 'STORE'
CMD_REPLICATE = 'REPLICATE'
CMD_RETRIEVE = 'RETRIEVE'
CMD_ADD_PEER = 'ADD_PEER'

# Responses
RESP_SUCCESS = b'SUCCESS'
RESP_FAILURE = b'FAILURE'
RESP_REPLICATED = b'REPLICATED'
RESP_FAILED = b'FAILED'
RESP_NOT_FOUND = b'NOT_FOUND'
RESP_PEER_ADDED = b'PEER_ADDED'
RESP_INVALID_PEER_INFO = b'INVALID_PEER_INFO'
RESP_INVALID_COMMAND = b'INVALID_COMMAND'
RESP_INVALID_MESSAGE_FORMAT = b'INVALID_MESSAGE_FORMAT'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _is_valid_peer(peer):
    """Return True if the peer description contains host and port."""
    return isinstance(peer, dict) and 'host' in peer and ('port' in peer)


def _choose_response(success, ok_response, fail_response):
    return ok_response if success else fail_response


class CacheNode:

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.cache = OrderedDict()
        self.max_cache_size = DEFAULT_MAX_CACHE_SIZE
        self.peers = []
        self.running = False
        self.serializer = DEFAULT_SERIALIZER

    # -- cache management ---------------------------------------------------
    def _evict_oldest(self):
        if len(self.cache) >= self.max_cache_size:
            self.cache.popitem(last=False)

    # -- serialization ------------------------------------------------------
    def _serialize_data(self, data):
        if self.serializer == SERIALIZER_JSON:
            return json.dumps(data).encode(ENCODING)
        else:
            raise ValueError('Unsupported serializer')

    def _deserialize_data(self, data_bytes):
        if self.serializer == SERIALIZER_JSON:
            return json.loads(data_bytes.decode(ENCODING))
        else:
            raise ValueError('Unsupported serializer')

    # -- storage / replication ---------------------------------------------
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

    def _replicate_to_peer(self, peer, key, data):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((peer['host'], peer['port']))
            message = {'command': CMD_REPLICATE, 'key': key, 'data': data}
            s.sendall(self._serialize_data(message))

    def _replicate_to_peers(self, key, data):
        for peer in self.peers:
            try:
                self._replicate_to_peer(peer, key, data)
            except Exception as e:
                print(f'Replication to {peer} failed: {e}')

    # -- command handlers ---------------------------------------------------
    def _handle_store(self, conn, message):
        success = self.store_data(message['key'], message['data'])
        conn.sendall(_choose_response(success, RESP_SUCCESS, RESP_FAILURE))

    def _handle_replicate(self, conn, message):
        success = self.store_data(message['key'], message['data'], replicate=False)
        conn.sendall(_choose_response(success, RESP_REPLICATED, RESP_FAILED))

    def _handle_retrieve(self, conn, message):
        result = self.cache.get(message['key'])
        if result is not None:
            conn.sendall(self._serialize_data(result))
        else:
            conn.sendall(RESP_NOT_FOUND)

    def _handle_add_peer(self, conn, message):
        if _is_valid_peer(message['peer']):
            self.peers.append(message['peer'])
            conn.sendall(RESP_PEER_ADDED)
        else:
            conn.sendall(RESP_INVALID_PEER_INFO)

    def _get_command_handler(self, command):
        handlers = {
            CMD_STORE: self._handle_store,
            CMD_REPLICATE: self._handle_replicate,
            CMD_RETRIEVE: self._handle_retrieve,
            CMD_ADD_PEER: self._handle_add_peer,
        }
        if not isinstance(command, str):
            return None
        return handlers.get(command)

    def _dispatch(self, conn, message):
        handler = self._get_command_handler(message['command'])
        if handler is None:
            conn.sendall(RESP_INVALID_COMMAND)
        else:
            handler(conn, message)

    # -- connection handling ------------------------------------------------
    def handle_client(self, conn, addr):
        try:
            data = conn.recv(RECV_BUFFER_SIZE)
            if not data:
                return
            message = self._deserialize_data(data)
            self._dispatch(conn, message)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f'Invalid message format: {e}')
            conn.sendall(RESP_INVALID_MESSAGE_FORMAT)
        except Exception as e:
            print(f'Client handling error: {e}')
        finally:
            conn.close()

    # -- server lifecycle ---------------------------------------------------
    def start(self):
        self.running = True
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.host, self.port))
            s.listen()
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


def _main():
    node = CacheNode()
    try:
        node.start()
    except KeyboardInterrupt:
        node.stop()


if __name__ == '__main__':
    _main()
