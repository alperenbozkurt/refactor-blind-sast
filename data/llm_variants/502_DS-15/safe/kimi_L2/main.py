"""Distributed cache node module.

Refactored into smaller helpers, named constants and a configuration
object while preserving the original public API and exact behaviour.
"""

import hashlib
import json
import socket
import threading
import time
import zlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

# ---------------------------------------------------------------------------
# Network / protocol constants
# ---------------------------------------------------------------------------

BUFFER_SIZE = 4096
PEER_TIMEOUT_SECONDS = 5
DEFAULT_REPLICATION_FACTOR = 2
UTF8 = 'utf-8'
LATIN1 = 'latin1'

ACTION_SET = 'set'
ACTION_GET = 'get'
ACTION_DELETE = 'delete'

STATUS_OK = 'ok'
STATUS_NOT_FOUND = 'not_found'
STATUS_ERROR = 'error'
STATUS_RUNNING = 'running'
STATUS_STOPPED = 'stopped'

# ---------------------------------------------------------------------------
# CLI constants
# ---------------------------------------------------------------------------

DEFAULT_BIND_HOST = '127.0.0.1'
MIN_USER_PORT = 1024
MAX_PORT = 65535

CMD_PEERS = 'peers'
CMD_ADD_PEER = 'addpeer'
CMD_STATS = 'stats'
CMD_STOP = 'stop'


@dataclass
class NodeSettings:
    """Startup configuration collected from the command line."""

    node_id: str
    host: str
    port: int


# ---------------------------------------------------------------------------
# (De)serialisation helpers
# ---------------------------------------------------------------------------

def _encode_message(payload):
    """Serialise a payload to UTF-8 encoded JSON bytes."""
    return json.dumps(payload).encode(UTF8)


def _decode_message(raw_data):
    """Deserialise UTF-8 encoded JSON bytes into a Python object."""
    return json.loads(raw_data.decode(UTF8))


def _error_response(message):
    return {'error': message}


# ---------------------------------------------------------------------------
# Validation / construction helpers
# ---------------------------------------------------------------------------

def _validate_key(key):
    if not key or not isinstance(key, str):
        raise ValueError('Invalid key')


def _validate_options(options):
    if not isinstance(options, dict):
        raise ValueError('Options must be a dictionary')


def _validate_peer_id(peer_id):
    if not isinstance(peer_id, str) or not peer_id:
        raise ValueError('Invalid peer ID')


def _validate_host(host):
    if not isinstance(host, str) or not host:
        raise ValueError('Invalid host')


def _validate_port(port):
    if not isinstance(port, int) or not 0 < port <= MAX_PORT:
        raise ValueError('Invalid port')


def _parse_request(request):
    """Extract and validate the fields of an incoming request."""
    if not isinstance(request, dict):
        raise ValueError('Request must be a dictionary')
    options = request.get('options', {})
    _validate_options(options)
    return (request.get('action'), request.get('key'),
            request.get('value'), options)


def _build_entry(value):
    """Create a stored entry with metadata for a value."""
    return {
        'value': value,
        'timestamp': datetime.now().isoformat(),
        'version': hashlib.md5(value.encode(UTF8)).hexdigest(),
    }


def _build_replication_request(action, key, value, options):
    return {
        'action': action,
        'key': key,
        'value': value,
        'options': options,
        'replication': True,
    }


class CacheNode:
    """A single node in a replicated, in-memory key/value cache."""

    def __init__(self, node_id):
        self.node_id = node_id
        self.data_store = defaultdict(dict)
        self.peers = {}
        self.lock = threading.Lock()
        self.running = False
        self.replication_factor = DEFAULT_REPLICATION_FACTOR

    def start(self, host, port):
        self.running = True
        server_thread = threading.Thread(target=self._run_server, args=(host, port))
        server_thread.daemon = True
        server_thread.start()
        print(f'Cache node {self.node_id} started on {host}:{port}')

    # -- server internals ------------------------------------------------

    @staticmethod
    def _create_listening_socket(host, port):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen()
        return server

    def _run_server(self, host, port):
        with self._create_listening_socket(host, port) as server:
            while self.running:
                try:
                    (conn, addr) = server.accept()
                    threading.Thread(target=self._handle_connection, args=(conn, addr)).start()
                except Exception as e:
                    if self.running:
                        print(f'Connection error: {e}')

    def _handle_connection(self, conn, addr):
        try:
            raw_data = conn.recv(BUFFER_SIZE)
            if not raw_data:
                return
            try:
                request = _decode_message(raw_data)
                response = self._process_request(request)
                conn.sendall(_encode_message(response))
            except json.JSONDecodeError:
                conn.sendall(_encode_message(_error_response('Invalid request format')))
        except Exception as e:
            conn.sendall(_encode_message(_error_response(str(e))))
        finally:
            conn.close()

    # -- request handling --------------------------------------------------

    def _process_request(self, request):
        (action, key, value, options) = _parse_request(request)
        with self.lock:
            handler = self._action_handlers().get(action)
            if handler is None:
                return {'status': STATUS_ERROR, 'message': 'Invalid action'}
            return handler(key, value, options)

    def _action_handlers(self):
        return {
            ACTION_SET: self._handle_set,
            ACTION_GET: self._handle_get,
            ACTION_DELETE: self._handle_delete,
        }

    def _handle_set(self, key, value, options):
        _validate_key(key)
        value = self._normalise_value(value, options)
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

    @staticmethod
    def _normalise_value(value, options):
        """Apply requested options (e.g. decompression) and validate."""
        if options.get('compressed', False):
            try:
                value = zlib.decompress(value.encode(LATIN1)).decode(UTF8)
            except Exception as e:
                raise ValueError(f'Decompression failed: {e}')
        if not isinstance(value, str):
            raise ValueError('Value must be a string')
        return value

    # -- replication ---------------------------------------------------------

    def _replicate(self, action, key, value, options):
        for (peer_id, peer_addr) in list(self.peers.items()):
            if peer_id == self.node_id:
                continue
            try:
                request = _build_replication_request(action, key, value, options)
                self._send_to_peer(peer_addr, request)
            except Exception as e:
                print(f'Replication to {peer_id} failed: {str(e)}')

    def _send_to_peer(self, peer_addr, data):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(PEER_TIMEOUT_SECONDS)
            sock.connect(peer_addr)
            sock.sendall(_encode_message(data))
            response = sock.recv(BUFFER_SIZE)
            return _decode_message(response)

    # -- peers / lifecycle / stats -------------------------------------------

    def add_peer(self, peer_id, host, port):
        _validate_peer_id(peer_id)
        _validate_host(host)
        _validate_port(port)
        self.peers[peer_id] = (host, port)

    def stop(self):
        self.running = False

    def get_stats(self):
        with self.lock:
            return {
                'node_id': self.node_id,
                'item_count': len(self.data_store),
                'peer_count': len(self.peers),
                'status': STATUS_RUNNING if self.running else STATUS_STOPPED,
            }


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def _prompt_node_settings():
    """Collect node startup settings; return None on invalid input."""
    node_id = input('Enter node ID: ').strip()
    if not node_id:
        print('Error: Node ID cannot be empty')
        return None
    host = input('Enter host to bind to [127.0.0.1]: ').strip() or DEFAULT_BIND_HOST
    try:
        port = int(input('Enter port: ').strip())
        if not MIN_USER_PORT <= port <= MAX_PORT:
            raise ValueError(f'Port must be between {MIN_USER_PORT} and {MAX_PORT}')
    except ValueError as e:
        print(f'Error: {e}')
        return None
    return NodeSettings(node_id=node_id, host=host, port=port)


def _handle_add_peer_command(node, cmd):
    try:
        (_, peer_id, peer_host, peer_port) = cmd.split()
        node.add_peer(peer_id, peer_host, int(peer_port))
        print(f'Added peer {peer_id} at {peer_host}:{peer_port}')
    except ValueError as e:
        print(f'Error: {e}')


def _run_command_loop(node):
    while True:
        cmd = input('> ').strip().lower()
        if cmd == CMD_PEERS:
            print('Connected peers:', node.peers)
        elif cmd.startswith(CMD_ADD_PEER):
            _handle_add_peer_command(node, cmd)
        elif cmd == CMD_STATS:
            print(node.get_stats())
        elif cmd == CMD_STOP:
            node.stop()
            break
        else:
            print('Unknown command')


def main():
    settings = _prompt_node_settings()
    if settings is None:
        return
    node = CacheNode(settings.node_id)
    node.start(settings.host, settings.port)
    try:
        _run_command_loop(node)
    except KeyboardInterrupt:
        node.stop()
    finally:
        print('Node stopped')


if __name__ == '__main__':
    main()
