"""A simple distributed cache node with peer replication and a CLI."""

import hashlib
import json
import socket
import threading
import time
import zlib
from collections import defaultdict
from datetime import datetime

BUFFER_SIZE = 4096
PEER_TIMEOUT_SECONDS = 5
DEFAULT_HOST = '127.0.0.1'
MIN_PORT = 1024
MAX_PORT = 65535


class CacheNode:
    """A single cache node storing key/value pairs and replicating to peers."""

    def __init__(self, node_id):
        self.node_id = node_id
        self.data_store = defaultdict(dict)
        self.peers = {}
        self.lock = threading.Lock()
        self.running = False
        self.replication_factor = 2

    def start(self, host, port):
        self.running = True
        server_thread = threading.Thread(
            target=self._run_server, args=(host, port), daemon=True
        )
        server_thread.start()
        print(f'Cache node {self.node_id} started on {host}:{port}')

    def stop(self):
        self.running = False

    def add_peer(self, peer_id, host, port):
        if not isinstance(peer_id, str) or not peer_id:
            raise ValueError('Invalid peer ID')
        if not isinstance(host, str) or not host:
            raise ValueError('Invalid host')
        if not isinstance(port, int) or not 0 < port <= 65535:
            raise ValueError('Invalid port')
        self.peers[peer_id] = (host, port)

    def get_stats(self):
        with self.lock:
            return {
                'node_id': self.node_id,
                'item_count': len(self.data_store),
                'peer_count': len(self.peers),
                'status': 'running' if self.running else 'stopped',
            }

    def _run_server(self, host, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((host, port))
            server_socket.listen()
            while self.running:
                try:
                    conn, addr = server_socket.accept()
                    threading.Thread(
                        target=self._handle_connection, args=(conn, addr)
                    ).start()
                except Exception as e:
                    if self.running:
                        print(f'Connection error: {e}')

    def _handle_connection(self, conn, addr):
        try:
            raw_data = conn.recv(BUFFER_SIZE)
            if not raw_data:
                return
            try:
                request = json.loads(raw_data.decode('utf-8'))
                response = self._process_request(request)
                self._send_json(conn, response)
            except json.JSONDecodeError:
                self._send_json(conn, {'error': 'Invalid request format'})
        except Exception as e:
            self._send_json(conn, {'error': str(e)})
        finally:
            conn.close()

    @staticmethod
    def _send_json(conn, payload):
        conn.sendall(json.dumps(payload).encode('utf-8'))

    def _process_request(self, request):
        if not isinstance(request, dict):
            raise ValueError('Request must be a dictionary')
        action = request.get('action')
        key = request.get('key')
        value = request.get('value')
        options = request.get('options', {})
        if not isinstance(options, dict):
            raise ValueError('Options must be a dictionary')
        with self.lock:
            if action == 'set':
                return self._handle_set(key, value, options)
            if action == 'get':
                return self._handle_get(key)
            if action == 'delete':
                return self._handle_delete(key, options)
            return {'status': 'error', 'message': 'Invalid action'}

    def _handle_set(self, key, value, options):
        self._validate_key(key)
        if options.get('compressed', False):
            value = self._decompress_value(value)
        if not isinstance(value, str):
            raise ValueError('Value must be a string')
        self.data_store[key] = self._build_entry(value)
        self._replicate('set', key, value, options)
        return {'status': 'ok'}

    def _handle_get(self, key):
        self._validate_key(key)
        if key not in self.data_store:
            return {'status': 'not_found'}
        entry = self.data_store[key]
        return {
            'status': 'ok',
            'value': entry['value'],
            'metadata': {'timestamp': entry['timestamp'], 'version': entry['version']},
        }

    def _handle_delete(self, key, options):
        self._validate_key(key)
        if key not in self.data_store:
            return {'status': 'not_found'}
        del self.data_store[key]
        self._replicate('delete', key, None, options)
        return {'status': 'ok'}

    @staticmethod
    def _validate_key(key):
        if not key or not isinstance(key, str):
            raise ValueError('Invalid key')

    @staticmethod
    def _decompress_value(value):
        try:
            return zlib.decompress(value.encode('latin1')).decode('utf-8')
        except Exception as e:
            raise ValueError(f'Decompression failed: {e}')

    @staticmethod
    def _build_entry(value):
        return {
            'value': value,
            'timestamp': datetime.now().isoformat(),
            'version': hashlib.md5(value.encode('utf-8')).hexdigest(),
        }

    def _replicate(self, action, key, value, options):
        for peer_id, peer_addr in list(self.peers.items()):
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
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as peer_socket:
            peer_socket.settimeout(PEER_TIMEOUT_SECONDS)
            peer_socket.connect(peer_addr)
            peer_socket.sendall(json.dumps(data).encode('utf-8'))
            response = peer_socket.recv(BUFFER_SIZE)
            return json.loads(response.decode('utf-8'))


def _prompt_node_settings():
    node_id = input('Enter node ID: ').strip()
    if not node_id:
        print('Error: Node ID cannot be empty')
        return None
    host = input(f'Enter host to bind to [{DEFAULT_HOST}]: ').strip() or DEFAULT_HOST
    try:
        port = int(input('Enter port: ').strip())
        if not MIN_PORT <= port <= MAX_PORT:
            raise ValueError(f'Port must be between {MIN_PORT} and {MAX_PORT}')
    except ValueError as e:
        print(f'Error: {e}')
        return None
    return node_id, host, port


def _handle_addpeer_command(node, cmd):
    try:
        (_, peer_id, peer_host, peer_port) = cmd.split()
        node.add_peer(peer_id, peer_host, int(peer_port))
        print(f'Added peer {peer_id} at {peer_host}:{peer_port}')
    except ValueError as e:
        print(f'Error: {e}')


def _run_command_loop(node):
    try:
        while True:
            cmd = input('> ').strip().lower()
            if cmd == 'peers':
                print('Connected peers:', node.peers)
            elif cmd.startswith('addpeer'):
                _handle_addpeer_command(node, cmd)
            elif cmd == 'stats':
                print(node.get_stats())
            elif cmd == 'stop':
                node.stop()
                break
            else:
                print('Unknown command')
    except KeyboardInterrupt:
        node.stop()
    finally:
        print('Node stopped')


def main():
    settings = _prompt_node_settings()
    if settings is None:
        return
    node_id, host, port = settings
    node = CacheNode(node_id)
    node.start(host, port)
    _run_command_loop(node)


if __name__ == '__main__':
    main()
