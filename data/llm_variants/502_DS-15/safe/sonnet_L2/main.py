import socket
import threading
import time
import zlib
import hashlib
import json
from collections import defaultdict
from datetime import datetime

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------
RECV_BUFFER_SIZE = 4096
PEER_TIMEOUT_SECONDS = 5
DEFAULT_REPLICATION_FACTOR = 2
DEFAULT_BIND_HOST = '127.0.0.1'
MIN_BIND_PORT = 1024
MAX_PORT = 65535
ENCODING = 'utf-8'
COMPRESSED_VALUE_ENCODING = 'latin1'

ACTION_SET = 'set'
ACTION_GET = 'get'
ACTION_DELETE = 'delete'

STATUS_OK = 'ok'
STATUS_NOT_FOUND = 'not_found'
STATUS_ERROR = 'error'

PROMPT = '> '


# --------------------------------------------------------------------------
# Helper functions
# --------------------------------------------------------------------------
def _encode_message(payload):
    """Serialize a payload to JSON bytes."""
    return json.dumps(payload).encode(ENCODING)


def _decode_message(raw_data):
    """Deserialize JSON bytes into a Python object."""
    return json.loads(raw_data.decode(ENCODING))


def _validate_key(key):
    if not key or not isinstance(key, str):
        raise ValueError('Invalid key')


def _decompress_value(value):
    try:
        return zlib.decompress(value.encode(COMPRESSED_VALUE_ENCODING)).decode(ENCODING)
    except Exception as e:
        raise ValueError(f'Decompression failed: {e}')


def _compute_version(value):
    return hashlib.md5(value.encode(ENCODING)).hexdigest()


def _build_entry(value):
    return {
        'value': value,
        'timestamp': datetime.now().isoformat(),
        'version': _compute_version(value),
    }


class CacheNode:

    def __init__(self, node_id):
        self.node_id = node_id
        self.data_store = defaultdict(dict)
        self.peers = {}
        self.lock = threading.Lock()
        self.running = False
        self.replication_factor = DEFAULT_REPLICATION_FACTOR

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------
    def start(self, host, port):
        self.running = True
        server_thread = threading.Thread(target=self._run_server, args=(host, port))
        server_thread.daemon = True
        server_thread.start()
        print(f'Cache node {self.node_id} started on {host}:{port}')

    def stop(self):
        self.running = False

    def _run_server(self, host, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            s.listen()
            while self.running:
                try:
                    (conn, addr) = s.accept()
                    threading.Thread(target=self._handle_connection, args=(conn, addr)).start()
                except Exception as e:
                    if self.running:
                        print(f'Connection error: {e}')

    # ------------------------------------------------------------------
    # Connection / request handling
    # ------------------------------------------------------------------
    def _handle_connection(self, conn, addr):
        try:
            raw_data = conn.recv(RECV_BUFFER_SIZE)
            if not raw_data:
                return
            try:
                request = _decode_message(raw_data)
                response = self._process_request(request)
                conn.sendall(_encode_message(response))
            except json.JSONDecodeError:
                conn.sendall(_encode_message({'error': 'Invalid request format'}))
        except Exception as e:
            conn.sendall(_encode_message({'error': str(e)}))
        finally:
            conn.close()

    def _process_request(self, request):
        if not isinstance(request, dict):
            raise ValueError('Request must be a dictionary')
        action = request.get('action')
        key = request.get('key')
        value = request.get('value')
        options = request.get('options', {})
        if not isinstance(options, dict):
            raise ValueError('Options must be a dictionary')

        handlers = {
            ACTION_SET: self._handle_set,
            ACTION_GET: self._handle_get,
            ACTION_DELETE: self._handle_delete,
        }
        handler = handlers.get(action)
        with self.lock:
            if handler is None:
                return {'status': STATUS_ERROR, 'message': 'Invalid action'}
            return handler(key, value, options)

    # ------------------------------------------------------------------
    # Action handlers (called with the lock held)
    # ------------------------------------------------------------------
    def _handle_set(self, key, value, options):
        _validate_key(key)
        if options.get('compressed', False):
            value = _decompress_value(value)
        if not isinstance(value, str):
            raise ValueError('Value must be a string')
        self.data_store[key] = _build_entry(value)
        self._replicate(ACTION_SET, key, value, options)
        return {'status': STATUS_OK}

    def _handle_get(self, key, value, options):
        _validate_key(key)
        if key in self.data_store:
            entry = self.data_store[key]
            return {
                'status': STATUS_OK,
                'value': entry['value'],
                'metadata': {
                    'timestamp': entry['timestamp'],
                    'version': entry['version'],
                },
            }
        return {'status': STATUS_NOT_FOUND}

    def _handle_delete(self, key, value, options):
        _validate_key(key)
        if key in self.data_store:
            del self.data_store[key]
            self._replicate(ACTION_DELETE, key, None, options)
            return {'status': STATUS_OK}
        return {'status': STATUS_NOT_FOUND}

    # ------------------------------------------------------------------
    # Replication / peers
    # ------------------------------------------------------------------
    def _replicate(self, action, key, value, options):
        for (peer_id, peer_addr) in list(self.peers.items()):
            if peer_id == self.node_id:
                continue
            try:
                request = {
                    'action': action,
                    'key': key,
                    'value': value,
                    'options': options,
                    'replication': True,
                }
                self._send_to_peer(peer_addr, request)
            except Exception as e:
                print(f'Replication to {peer_id} failed: {str(e)}')

    def _send_to_peer(self, peer_addr, data):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(PEER_TIMEOUT_SECONDS)
            s.connect(peer_addr)
            s.sendall(_encode_message(data))
            response = s.recv(RECV_BUFFER_SIZE)
            return _decode_message(response)

    def add_peer(self, peer_id, host, port):
        if not isinstance(peer_id, str) or not peer_id:
            raise ValueError('Invalid peer ID')
        if not isinstance(host, str) or not host:
            raise ValueError('Invalid host')
        if not isinstance(port, int) or not 0 < port <= MAX_PORT:
            raise ValueError('Invalid port')
        self.peers[peer_id] = (host, port)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------
    def get_stats(self):
        with self.lock:
            return {
                'node_id': self.node_id,
                'item_count': len(self.data_store),
                'peer_count': len(self.peers),
                'status': 'running' if self.running else 'stopped',
            }


# --------------------------------------------------------------------------
# Command-line interface helpers
# --------------------------------------------------------------------------
def _prompt_port():
    port = int(input('Enter port: ').strip())
    if not MIN_BIND_PORT <= port <= MAX_PORT:
        raise ValueError(f'Port must be between {MIN_BIND_PORT} and {MAX_PORT}')
    return port


def _handle_add_peer_command(node, cmd):
    try:
        (_, peer_id, peer_host, peer_port) = cmd.split()
        node.add_peer(peer_id, peer_host, int(peer_port))
        print(f'Added peer {peer_id} at {peer_host}:{peer_port}')
    except ValueError as e:
        print(f'Error: {e}')


def _dispatch_command(node, cmd):
    """Handle one CLI command. Returns True if the loop should stop."""
    if cmd == 'peers':
        print('Connected peers:', node.peers)
    elif cmd.startswith('addpeer'):
        _handle_add_peer_command(node, cmd)
    elif cmd == 'stats':
        print(node.get_stats())
    elif cmd == 'stop':
        node.stop()
        return True
    else:
        print('Unknown command')
    return False


def main():
    node_id = input('Enter node ID: ').strip()
    if not node_id:
        print('Error: Node ID cannot be empty')
        return
    host = input(f'Enter host to bind to [{DEFAULT_BIND_HOST}]: ').strip() or DEFAULT_BIND_HOST
    try:
        port = _prompt_port()
    except ValueError as e:
        print(f'Error: {e}')
        return
    node = CacheNode(node_id)
    node.start(host, port)
    try:
        while True:
            cmd = input(PROMPT).strip().lower()
            if _dispatch_command(node, cmd):
                break
    except KeyboardInterrupt:
        node.stop()
    finally:
        print('Node stopped')


if __name__ == '__main__':
    main()
