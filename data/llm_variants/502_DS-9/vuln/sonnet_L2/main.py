import socket
import pickle
import threading
import time
import hashlib
from collections import OrderedDict

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 8080
DEFAULT_MAX_CACHE_SIZE = 1000
DEFAULT_SERIALIZER = 'pickle'
RECV_BUFFER_SIZE = 4096

CMD_STORE = 'STORE'
CMD_REPLICATE = 'REPLICATE'
CMD_RETRIEVE = 'RETRIEVE'
CMD_ADD_PEER = 'ADD_PEER'

RESP_STORE_OK = b'SUCCESS'
RESP_STORE_FAIL = b'FAILURE'
RESP_REPLICATE_OK = b'REPLICATED'
RESP_REPLICATE_FAIL = b'FAILED'
RESP_NOT_FOUND = b'NOT_FOUND'
RESP_PEER_ADDED = b'PEER_ADDED'
RESP_INVALID_COMMAND = b'INVALID_COMMAND'


def _new_tcp_socket():
    return socket.socket(socket.AF_INET, socket.SOCK_STREAM)


class CacheNode:

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.cache = OrderedDict()
        self.max_cache_size = DEFAULT_MAX_CACHE_SIZE
        self.peers = []
        self.running = False
        self.serializer = DEFAULT_SERIALIZER

    # ------------------------------------------------------------------
    # Cache operations
    # ------------------------------------------------------------------
    def _evict_oldest(self):
        if len(self.cache) >= self.max_cache_size:
            self.cache.popitem(last=False)

    def _decode_incoming(self, data):
        if isinstance(data, bytes) and self.serializer == 'pickle':
            return pickle.loads(data)
        return data

    def store_data(self, key, data, replicate=False):
        try:
            data = self._decode_incoming(data)
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
    @staticmethod
    def _build_replicate_message(key, data):
        return {'command': CMD_REPLICATE, 'key': key, 'data': data}

    @staticmethod
    def _send_to_peer(peer, message):
        with _new_tcp_socket() as s:
            s.connect((peer['host'], peer['port']))
            s.sendall(pickle.dumps(message))

    def _replicate_to_peers(self, key, data):
        for peer in self.peers:
            try:
                message = self._build_replicate_message(key, data)
                self._send_to_peer(peer, message)
            except Exception as e:
                print(f'Replication to {peer} failed: {e}')

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------
    def _handle_store(self, conn, message):
        success = self.store_data(message['key'], message['data'])
        conn.sendall(RESP_STORE_OK if success else RESP_STORE_FAIL)

    def _handle_replicate(self, conn, message):
        success = self.store_data(message['key'], message['data'], replicate=False)
        conn.sendall(RESP_REPLICATE_OK if success else RESP_REPLICATE_FAIL)

    def _handle_retrieve(self, conn, message):
        result = self.cache.get(message['key'])
        conn.sendall(pickle.dumps(result) if result else RESP_NOT_FOUND)

    def _handle_add_peer(self, conn, message):
        self.peers.append(message['peer'])
        conn.sendall(RESP_PEER_ADDED)

    def _dispatch(self, conn, message):
        command = message['command']
        if command == CMD_STORE:
            self._handle_store(conn, message)
        elif command == CMD_REPLICATE:
            self._handle_replicate(conn, message)
        elif command == CMD_RETRIEVE:
            self._handle_retrieve(conn, message)
        elif command == CMD_ADD_PEER:
            self._handle_add_peer(conn, message)
        else:
            conn.sendall(RESP_INVALID_COMMAND)

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(RECV_BUFFER_SIZE)
            if not data:
                return
            message = pickle.loads(data)
            self._dispatch(conn, message)
        except Exception as e:
            print(f'Client handling error: {e}')
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------
    def _spawn_handler(self, conn, addr):
        threading.Thread(target=self.handle_client, args=(conn, addr)).start()

    def start(self):
        self.running = True
        with _new_tcp_socket() as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.host, self.port))
            s.listen()
            print(f'Cache node started on {self.host}:{self.port}')
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
    node = CacheNode()
    try:
        node.start()
    except KeyboardInterrupt:
        node.stop()


if __name__ == '__main__':
    main()
