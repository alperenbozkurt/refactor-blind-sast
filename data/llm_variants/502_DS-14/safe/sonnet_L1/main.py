import socket
import threading
import time
import hashlib
import json
from datetime import datetime
import ast

HOST = '127.0.0.1'
LISTEN_BACKLOG = 5
RECV_BUFFER_SIZE = 4096
MIN_PORT = 1024
MAX_PORT = 65535
HISTORY_LIMIT = 20


class TaskWorker:

    def __init__(self):
        self.task_queue = []
        self.completed_tasks = []
        self.running = False
        self.worker_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]
        self.task_callbacks = {
            'process_data': self._process_data_task,
            'transform_data': self._transform_data_task,
        }
        self.allowed_transforms = {
            'double': lambda x: x * 2,
            'square': lambda x: x ** 2,
            'increment': lambda x: x + 1,
        }
        self.allowed_operations = {
            'reverse': lambda d: d[::-1],
            'uppercase': lambda d: d.upper(),
            'hash': lambda d: hashlib.sha256(d.encode()).hexdigest(),
        }

    # ------------------------------------------------------------------
    # Server handling
    # ------------------------------------------------------------------

    def start_server(self, port):
        self.running = True
        server_thread = threading.Thread(target=self._run_server, args=(port,))
        server_thread.daemon = True
        server_thread.start()

    def _run_server(self, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((HOST, port))
            server_socket.listen(LISTEN_BACKLOG)
            print(f'Worker {self.worker_id} listening on port {port}')
            while self.running:
                try:
                    (conn, addr) = server_socket.accept()
                    client_thread = threading.Thread(
                        target=self._handle_client, args=(conn, addr)
                    )
                    client_thread.start()
                except Exception as e:
                    print(f'Connection error: {e}')

    @staticmethod
    def _send_json(conn, payload):
        conn.sendall(json.dumps(payload).encode())

    def _handle_client(self, conn, addr):
        try:
            data = conn.recv(RECV_BUFFER_SIZE)
            if not data:
                return
            try:
                task = json.loads(data.decode('utf-8'))
                result = self._execute_task(task)
                self._send_json(conn, result)
            except json.JSONDecodeError:
                self._send_json(conn, {'error': 'Invalid task format'})
        except Exception as e:
            self._send_json(conn, {'error': str(e)})
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    def _execute_task(self, task):
        if not isinstance(task, dict):
            raise ValueError('Task must be a dictionary')

        task_id = task.get('task_id', 'unknown')
        task_type = task.get('type')
        payload = task.get('payload', {})

        if not isinstance(payload, dict):
            raise ValueError('Payload must be a dictionary')
        if task_type not in self.task_callbacks:
            return {'status': 'error', 'message': 'Unknown task type'}

        start_time = time.time()
        try:
            result = self.task_callbacks[task_type](payload)
            execution_time = time.time() - start_time
            self._record_success(task_id, task_type, execution_time)
            return {'status': 'success', 'result': result}
        except Exception as e:
            self._record_failure(task_id, task_type, e)
            return {'status': 'error', 'message': str(e)}

    def _record_success(self, task_id, task_type, execution_time):
        self.completed_tasks.append({
            'task_id': task_id,
            'type': task_type,
            'status': 'completed',
            'execution_time': execution_time,
            'timestamp': datetime.now().isoformat(),
        })

    def _record_failure(self, task_id, task_type, error):
        self.completed_tasks.append({
            'task_id': task_id,
            'type': task_type,
            'status': 'failed',
            'error': str(error),
            'timestamp': datetime.now().isoformat(),
        })

    def _process_data_task(self, payload):
        if 'data' not in payload or not isinstance(payload['data'], str):
            raise ValueError('Invalid data payload')

        data = payload['data']
        operations = payload.get('operations', [])
        if not isinstance(operations, list):
            raise ValueError('Operations must be a list')

        for operation in operations:
            if operation not in self.allowed_operations:
                raise ValueError(f'Invalid operation: {operation}')
            data = self.allowed_operations[operation](data)

        return {'processed_data': data}

    def _transform_data_task(self, payload):
        if 'input' not in payload:
            raise ValueError('Missing input data')
        if 'transform' not in payload or payload['transform'] not in self.allowed_transforms:
            raise ValueError('Invalid or missing transform')

        input_data = payload['input']
        transform = payload['transform']
        try:
            result = self.allowed_transforms[transform](input_data)
            return {'output': result}
        except Exception as e:
            raise ValueError(f'Transform failed: {str(e)}')

    # ------------------------------------------------------------------
    # Control and inspection
    # ------------------------------------------------------------------

    def stop(self):
        self.running = False

    def get_task_history(self):
        return self.completed_tasks[-HISTORY_LIMIT:]


def main():
    worker = TaskWorker()
    try:
        port = int(input(f'Enter worker port ({MIN_PORT}-{MAX_PORT}): '))
        if not MIN_PORT <= port <= MAX_PORT:
            raise ValueError(f'Port must be between {MIN_PORT} and {MAX_PORT}')
        worker.start_server(port)
        print('Worker started. Press Ctrl+C to stop.')
        while True:
            time.sleep(1)
    except ValueError as e:
        print(f'Error: {e}')
    except KeyboardInterrupt:
        worker.stop()
        print('\nWorker stopped')
        print('Recent tasks:')
        for task in worker.get_task_history():
            print(f"{task['timestamp']} - {task['type']}: {task['status']}")


if __name__ == '__main__':
    main()
