import pickle
import socket
import threading
import time
import zlib
import hashlib
from collections import defaultdict
from datetime import datetime

# ---------------------------------------------------------------------------
# Protocol / networking constants
# ---------------------------------------------------------------------------
BUFFER_SIZE = 4096
DEFAULT_REPLICATION_FACTOR = 2

ACTION_SET = 'set'
ACTION_GET = 'get'
ACTION_DELETE = 'delete'

STATUS_OK = 'ok'
STATUS_NOT_FOUND = 'not_found'
STATUS_ERROR = 'error'
STATUS_RUNNING = 'running'
STATUS_STOPPED = 'stopped'

# ---------------------------------------------------------------------------
# Command-line interface constants
# ---------------------------------------------------------------------------
PROMPT_NODE_ID = 'Enter node ID: '
PROMPT_HOST = 'Enter host to bind to: '
PROMPT_PORT = 'Enter port: '
PROMPT_COMMAND = '> '

COMMAND_PEERS = 'peers'
COMMAND_ADD_PEER = 'addpeer'
COMMAND_STATS = 'stats'
COMMAND_STOP = 'stop'

MESSAGE_UNKNOWN_COMMAND = 'Unknown command'
MESSAGE_NODE_STOPPED = 'Node stopped'


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------
def _encode(message):
    """Serialize a protocol message into bytes for transmission."""
    return pickle.dumps(message)


def _decode(payload):
    """Deserialize bytes received from the wire into a protocol message."""
    return pickle.loads(payload)


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------
def _compute_version(value):
    """Return the content-based version identifier for a stored value."""
    return hashlib.md5(str(value).encode()).hexdigest()


def _build_record(value):
    """Create a storage record for a value with fresh metadata."""
    return {
        'value': value,
        'timestamp': datetime.now(),
        'version': _compute_version(value),
    }


def _error_response(error):
    """Build the response sent back when request handling fails."""
    return {'error': str(error)}


class CacheNode:

    def __init__(self, node_id):
        self.node_id = node_id
        self.data_store = defaultdict(dict)
        self.peers = {}
        self.lock = threading.Lock()
        self.running = False
        self.replication_factor = DEFAULT_REPLICATION_FACTOR

    # -- server lifecycle ----------------------------------------------------

    def start(self, host, port):
        self.running = True
        server_thread = threading.Thread(target=self._run_server, args=(host, port))
        server_thread.daemon = True
        server_thread.start()
        print(f'Cache node {self.node_id} started on {host}:{port}')

    def stop(self):
        self.running = False

    def _run_server(self, host, port):
        with self._open_server_socket(host, port) as server_socket:
            self._accept_loop(server_socket)

    @staticmethod
    def _open_server_socket(host, port):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((host, port))
        server_socket.listen()
        return server_socket

    def _accept_loop(self, server_socket):
        while self.running:
            (conn, addr) = server_socket.accept()
            threading.Thread(target=self._handle_connection, args=(conn, addr)).start()

    # -- connection handling -------------------------------------------------

    def _handle_connection(self, conn, addr):
        try:
            raw_data = conn.recv(BUFFER_SIZE)
            if not raw_data:
                return
            request = _decode(raw_data)
            response = self._process_request(request)
            self._send_message(conn, response)
        except Exception as e:
            self._send_message(conn, _error_response(e))
        finally:
            conn.close()

    @staticmethod
    def _send_message(conn, message):
        conn.sendall(_encode(message))

    # -- request processing --------------------------------------------------

    def _process_request(self, request):
        action = request.get('action')
        key = request.get('key')
        value = request.get('value')
        options = request.get('options', {})
        with self.lock:
            if action == ACTION_SET:
                return self._apply_set(key, value, options)
            elif action == ACTION_GET:
                return self._apply_get(key)
            elif action == ACTION_DELETE:
                return self._apply_delete(key, options)
            return {'status': STATUS_ERROR, 'message': 'Invalid action'}

    def _apply_set(self, key, value, options):
        if options.get('compressed', False):
            value = zlib.decompress(value)
        self.data_store[key] = _build_record(value)
        self._replicate(ACTION_SET, key, value, options)
        return {'status': STATUS_OK}

    def _apply_get(self, key):
        if key in self.data_store:
            record = self.data_store[key]
            return {
                'status': STATUS_OK,
                'value': record['value'],
                'metadata': {'timestamp': record['timestamp'], 'version': record['version']},
            }
        return {'status': STATUS_NOT_FOUND}

    def _apply_delete(self, key, options):
        if key in self.data_store:
            del self.data_store[key]
            self._replicate(ACTION_DELETE, key, None, options)
            return {'status': STATUS_OK}
        return {'status': STATUS_NOT_FOUND}

    # -- replication ----------------------------------------------------------

    def _replicate(self, action, key, value, options):
        for (peer_id, peer_addr) in list(self.peers.items()):
            if peer_id == self.node_id:
                continue
            try:
                request = self._build_replication_request(action, key, value, options)
                self._send_to_peer(peer_addr, request)
            except Exception as e:
                print(f'Replication to {peer_id} failed: {str(e)}')

    @staticmethod
    def _build_replication_request(action, key, value, options):
        return {'action': action, 'key': key, 'value': value, 'options': options, 'replication': True}

    def _send_to_peer(self, peer_addr, data):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(peer_addr)
            s.sendall(_encode(data))
            response = s.recv(BUFFER_SIZE)
            return _decode(response)

    # -- peer management and introspection ------------------------------------

    def add_peer(self, peer_id, host, port):
        self.peers[peer_id] = (host, port)

    def get_stats(self):
        with self.lock:
            return {'node_id': self.node_id, 'item_count': len(self.data_store), 'peer_count': len(self.peers), 'status': STATUS_RUNNING if self.running else STATUS_STOPPED}


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------
def _read_startup_config():
    node_id = input(PROMPT_NODE_ID)
    host = input(PROMPT_HOST)
    port = int(input(PROMPT_PORT))
    return (node_id, host, port)


def _handle_add_peer(node, cmd):
    (_, peer_id, peer_host, peer_port) = cmd.split()
    node.add_peer(peer_id, peer_host, int(peer_port))
    print(f'Added peer {peer_id} at {peer_host}:{peer_port}')


def _run_command_loop(node):
    while True:
        cmd = input(PROMPT_COMMAND).strip().lower()
        if cmd == COMMAND_PEERS:
            print('Connected peers:', node.peers)
        elif cmd.startswith(COMMAND_ADD_PEER):
            _handle_add_peer(node, cmd)
        elif cmd == COMMAND_STATS:
            print(node.get_stats())
        elif cmd == COMMAND_STOP:
            node.stop()
            return
        else:
            print(MESSAGE_UNKNOWN_COMMAND)


def main():
    (node_id, host, port) = _read_startup_config()
    node = CacheNode(node_id)
    node.start(host, port)
    try:
        _run_command_loop(node)
    except KeyboardInterrupt:
        node.stop()
    finally:
        print(MESSAGE_NODE_STOPPED)


if __name__ == '__main__':
    main()
