import pickle
import socket
import threading
import time
import zlib
import hashlib
from collections import defaultdict
from datetime import datetime


class CacheNode:

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

    def _run_server(self, host, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            s.listen()
            while self.running:
                conn, addr = s.accept()
                threading.Thread(
                    target=self._handle_connection, args=(conn, addr)
                ).start()

    def _handle_connection(self, conn, addr):
        try:
            raw_data = conn.recv(4096)
            if not raw_data:
                return
            request = pickle.loads(raw_data)
            response = self._process_request(request)
            conn.sendall(pickle.dumps(response))
        except Exception as e:
            conn.sendall(pickle.dumps({'error': str(e)}))
        finally:
            conn.close()

    def _process_request(self, request):
        action = request.get('action')
        key = request.get('key')
        value = request.get('value')
        options = request.get('options', {})
        with self.lock:
            if action == 'set':
                return self._set_value(key, value, options)
            elif action == 'get':
                return self._get_value(key)
            elif action == 'delete':
                return self._delete_value(key, options)
            return {'status': 'error', 'message': 'Invalid action'}

    def _set_value(self, key, value, options):
        if options.get('compressed', False):
            value = zlib.decompress(value)
        self.data_store[key] = {
            'value': value,
            'timestamp': datetime.now(),
            'version': hashlib.md5(str(value).encode()).hexdigest(),
        }
        self._replicate('set', key, value, options)
        return {'status': 'ok'}

    def _get_value(self, key):
        if key not in self.data_store:
            return {'status': 'not_found'}
        entry = self.data_store[key]
        return {
            'status': 'ok',
            'value': entry['value'],
            'metadata': {
                'timestamp': entry['timestamp'],
                'version': entry['version'],
            },
        }

    def _delete_value(self, key, options):
        if key not in self.data_store:
            return {'status': 'not_found'}
        del self.data_store[key]
        self._replicate('delete', key, None, options)
        return {'status': 'ok'}

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
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(peer_addr)
            s.sendall(pickle.dumps(data))
            response = s.recv(4096)
            return pickle.loads(response)

    def add_peer(self, peer_id, host, port):
        self.peers[peer_id] = (host, port)

    def stop(self):
        self.running = False

    def get_stats(self):
        with self.lock:
            return {
                'node_id': self.node_id,
                'item_count': len(self.data_store),
                'peer_count': len(self.peers),
                'status': 'running' if self.running else 'stopped',
            }


def main():
    node_id = input('Enter node ID: ')
    host = input('Enter host to bind to: ')
    port = int(input('Enter port: '))
    node = CacheNode(node_id)
    node.start(host, port)
    try:
        while True:
            cmd = input('> ').strip().lower()
            if cmd == 'peers':
                print('Connected peers:', node.peers)
            elif cmd.startswith('addpeer'):
                _, peer_id, peer_host, peer_port = cmd.split()
                node.add_peer(peer_id, peer_host, int(peer_port))
                print(f'Added peer {peer_id} at {peer_host}:{peer_port}')
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


if __name__ == '__main__':
    main()
