import socket
import pickle
import threading
import time
import hashlib
from collections import OrderedDict


class CacheNode:
    """A single node of a simple distributed in-memory cache.

    Stores key/value pairs with FIFO eviction once the cache is full and
    can optionally replicate stored values to a static list of peer nodes
    over TCP. Messages are serialized with the serializer named by the
    ``serializer`` attribute.
    """

    def __init__(self, host='0.0.0.0', port=8080):
        self.host = host
        self.port = port
        self.cache = OrderedDict()
        self.max_cache_size = 1000
        self.peers = []
        self.running = False
        self.serializer = 'pickle'

    def _evict_oldest(self):
        """Remove the oldest cache entry when the cache is at capacity."""
        if len(self.cache) >= self.max_cache_size:
            self.cache.popitem(last=False)

    def store_data(self, key, data, replicate=False):
        """Store ``data`` under ``key``, optionally replicating to peers.

        Byte-string payloads are deserialized first when the configured
        serializer is ``'pickle'``. Returns True on success, False on
        failure.
        """
        try:
            if isinstance(data, bytes) and self.serializer == 'pickle':
                data = pickle.loads(data)
            self._evict_oldest()
            self.cache[key] = data
            if replicate:
                serialized = pickle.dumps(data)
                self._replicate_to_peers(key, serialized)
            return True
        except Exception as e:
            print(f'Storage failed: {e}')
            return False

    def _replicate_to_peers(self, key, data):
        """Send a REPLICATE message for ``key`` to every known peer.

        Failures to reach an individual peer are logged and do not stop
        replication to the remaining peers.
        """
        for peer in self.peers:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as peer_socket:
                    peer_socket.connect((peer['host'], peer['port']))
                    message = {'command': 'REPLICATE', 'key': key, 'data': data}
                    peer_socket.sendall(pickle.dumps(message))
            except Exception as e:
                print(f'Replication to {peer} failed: {e}')

    def handle_client(self, conn, addr):
        """Read a single request from ``conn`` and send back the response.

        Supported commands are STORE, REPLICATE, RETRIEVE and ADD_PEER;
        anything else is answered with INVALID_COMMAND. The connection is
        always closed when handling finishes.
        """
        try:
            data = conn.recv(4096)
            if not data:
                return
            message = pickle.loads(data)
            command = message['command']

            if command == 'STORE':
                success = self.store_data(message['key'], message['data'])
                conn.sendall(b'SUCCESS' if success else b'FAILURE')
            elif command == 'REPLICATE':
                success = self.store_data(message['key'], message['data'], replicate=False)
                conn.sendall(b'REPLICATED' if success else b'FAILED')
            elif command == 'RETRIEVE':
                result = self.cache.get(message['key'])
                conn.sendall(pickle.dumps(result) if result else b'NOT_FOUND')
            elif command == 'ADD_PEER':
                self.peers.append(message['peer'])
                conn.sendall(b'PEER_ADDED')
            else:
                conn.sendall(b'INVALID_COMMAND')
        except Exception as e:
            print(f'Client handling error: {e}')
        finally:
            conn.close()

    def start(self):
        """Bind the listening socket and serve clients until stopped.

        Each accepted connection is handled in its own daemon-less thread.
        A keyboard interrupt ends the accept loop gracefully.
        """
        self.running = True
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen()
            print(f'Cache node started on {self.host}:{self.port}')
            while self.running:
                try:
                    (conn, addr) = server_socket.accept()
                    threading.Thread(target=self.handle_client, args=(conn, addr)).start()
                except KeyboardInterrupt:
                    self.running = False
                except Exception as e:
                    print(f'Server error: {e}')

    def stop(self):
        """Signal the accept loop in ``start`` to stop serving."""
        self.running = False


if __name__ == '__main__':
    node = CacheNode()
    try:
        node.start()
    except KeyboardInterrupt:
        node.stop()
