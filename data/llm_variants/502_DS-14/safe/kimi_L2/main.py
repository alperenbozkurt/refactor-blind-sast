"""Concurrent TCP task worker.

A :class:`TaskWorker` listens on a local TCP port, executes JSON-encoded
tasks sent by clients, and keeps a bounded history of the most recent
task outcomes.
"""

import ast
import hashlib
import json
import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime

# ---------------------------------------------------------------------------
# Network / protocol constants
# ---------------------------------------------------------------------------

SERVER_HOST = '127.0.0.1'
LISTEN_BACKLOG = 5
RECV_BUFFER_SIZE = 4096

MIN_PORT = 1024
MAX_PORT = 65535

WORKER_ID_LENGTH = 8
TASK_HISTORY_LIMIT = 20
MAIN_LOOP_SLEEP_SECONDS = 1

# Task types.
TASK_TYPE_PROCESS_DATA = 'process_data'
TASK_TYPE_TRANSFORM_DATA = 'transform_data'

# Task-record and response statuses.
STATUS_COMPLETED = 'completed'
STATUS_FAILED = 'failed'
STATUS_SUCCESS = 'success'
STATUS_ERROR = 'error'

DEFAULT_TASK_ID = 'unknown'


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WorkerConfig:
    """Tunable parameters for a :class:`TaskWorker` instance."""

    host: str = SERVER_HOST
    listen_backlog: int = LISTEN_BACKLOG
    recv_buffer_size: int = RECV_BUFFER_SIZE
    history_limit: int = TASK_HISTORY_LIMIT


# ---------------------------------------------------------------------------
# Data operations and transforms
# ---------------------------------------------------------------------------

def _reverse(data):
    return data[::-1]


def _uppercase(data):
    return data.upper()


def _sha256_hash(data):
    return hashlib.sha256(data.encode()).hexdigest()


DATA_OPERATIONS = {
    'reverse': _reverse,
    'uppercase': _uppercase,
    'hash': _sha256_hash,
}


def _double(value):
    return value * 2


def _square(value):
    return value ** 2


def _increment(value):
    return value + 1


ALLOWED_TRANSFORMS = {
    'double': _double,
    'square': _square,
    'increment': _increment,
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _generate_worker_id():
    """Return a short identifier, unique to this worker instance."""
    return hashlib.md5(str(datetime.now()).encode()).hexdigest()[:WORKER_ID_LENGTH]


def _send_json(conn, message):
    """Serialize *message* to JSON and send it over *conn*."""
    conn.sendall(json.dumps(message).encode())


def _current_timestamp():
    return datetime.now().isoformat()


def _parse_task(task):
    """Validate a raw task and return ``(task_id, task_type, payload)``."""
    if not isinstance(task, dict):
        raise ValueError('Task must be a dictionary')
    task_id = task.get('task_id', DEFAULT_TASK_ID)
    task_type = task.get('type')
    payload = task.get('payload', {})
    if not isinstance(payload, dict):
        raise ValueError('Payload must be a dictionary')
    return task_id, task_type, payload


def _make_task_record(task_id, task_type, status, execution_time=None, error=None):
    """Build a history entry for a finished task."""
    record = {'task_id': task_id, 'type': task_type, 'status': status}
    if execution_time is not None:
        record['execution_time'] = execution_time
    if error is not None:
        record['error'] = error
    record['timestamp'] = _current_timestamp()
    return record


def _apply_data_operation(data, operation):
    """Apply a single named operation to *data*."""
    if operation not in DATA_OPERATIONS:
        raise ValueError(f'Invalid operation: {operation}')
    return DATA_OPERATIONS[operation](data)


def _format_history_entry(task):
    return f"{task['timestamp']} - {task['type']}: {task['status']}"


def _read_port_from_stdin():
    """Prompt for a port number and validate it."""
    port = int(input(f'Enter worker port ({MIN_PORT}-{MAX_PORT}): '))
    if not MIN_PORT <= port <= MAX_PORT:
        raise ValueError(f'Port must be between {MIN_PORT} and {MAX_PORT}')
    return port


def _print_task_history(worker):
    print('Recent tasks:')
    for task in worker.get_task_history():
        print(_format_history_entry(task))


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class TaskWorker:
    """Executes JSON-encoded tasks received over a TCP socket."""

    def __init__(self):
        self.task_queue = []
        self.completed_tasks = []
        self.running = False
        self.worker_id = _generate_worker_id()
        self.task_callbacks = {
            TASK_TYPE_PROCESS_DATA: self._process_data_task,
            TASK_TYPE_TRANSFORM_DATA: self._transform_data_task,
        }
        self.allowed_transforms = dict(ALLOWED_TRANSFORMS)
        self._config = WorkerConfig()

    def start_server(self, port):
        self.running = True
        server_thread = threading.Thread(target=self._run_server, args=(port,))
        server_thread.daemon = True
        server_thread.start()

    def _run_server(self, port):
        config = self._config
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((config.host, port))
            server_socket.listen(config.listen_backlog)
            print(f'Worker {self.worker_id} listening on port {port}')
            while self.running:
                self._accept_connection(server_socket)

    def _accept_connection(self, server_socket):
        try:
            (conn, addr) = server_socket.accept()
            client_thread = threading.Thread(target=self._handle_client, args=(conn, addr))
            client_thread.start()
        except Exception as e:
            print(f'Connection error: {e}')

    def _handle_client(self, conn, addr):
        try:
            data = conn.recv(self._config.recv_buffer_size)
            if not data:
                return
            try:
                task = json.loads(data.decode('utf-8'))
                result = self._execute_task(task)
                _send_json(conn, result)
            except json.JSONDecodeError as e:
                _send_json(conn, {'error': 'Invalid task format'})
        except Exception as e:
            _send_json(conn, {'error': str(e)})
        finally:
            conn.close()

    def _execute_task(self, task):
        (task_id, task_type, payload) = _parse_task(task)
        if task_type not in self.task_callbacks:
            return {'status': STATUS_ERROR, 'message': 'Unknown task type'}
        start_time = time.time()
        try:
            result = self.task_callbacks[task_type](payload)
            execution_time = time.time() - start_time
            self.completed_tasks.append(
                _make_task_record(task_id, task_type, STATUS_COMPLETED,
                                  execution_time=execution_time)
            )
            return {'status': STATUS_SUCCESS, 'result': result}
        except Exception as e:
            self.completed_tasks.append(
                _make_task_record(task_id, task_type, STATUS_FAILED, error=str(e))
            )
            return {'status': STATUS_ERROR, 'message': str(e)}

    def _process_data_task(self, payload):
        if 'data' not in payload or not isinstance(payload['data'], str):
            raise ValueError('Invalid data payload')
        data = payload['data']
        operations = payload.get('operations', [])
        if not isinstance(operations, list):
            raise ValueError('Operations must be a list')
        for op in operations:
            data = _apply_data_operation(data, op)
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

    def stop(self):
        self.running = False

    def get_task_history(self):
        return self.completed_tasks[-self._config.history_limit:]


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def main():
    worker = TaskWorker()
    try:
        port = _read_port_from_stdin()
        worker.start_server(port)
        print('Worker started. Press Ctrl+C to stop.')
        while True:
            time.sleep(MAIN_LOOP_SLEEP_SECONDS)
    except ValueError as e:
        print(f'Error: {e}')
    except KeyboardInterrupt:
        worker.stop()
        print('\nWorker stopped')
        _print_task_history(worker)


if __name__ == '__main__':
    main()
