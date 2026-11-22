import socket
import threading
import time
import hashlib
import json
from datetime import datetime
import ast

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------
HOST = '127.0.0.1'
LISTEN_BACKLOG = 5
RECV_BUFFER_SIZE = 4096
WORKER_ID_LENGTH = 8
HISTORY_LIMIT = 20
MIN_PORT = 1024
MAX_PORT = 65535
MAIN_LOOP_INTERVAL_SECONDS = 1

TASK_PROCESS_DATA = 'process_data'
TASK_TRANSFORM_DATA = 'transform_data'

STATUS_SUCCESS = 'success'
STATUS_ERROR = 'error'
STATUS_COMPLETED = 'completed'
STATUS_FAILED = 'failed'

ERROR_INVALID_TASK_FORMAT = 'Invalid task format'
ERROR_UNKNOWN_TASK_TYPE = 'Unknown task type'

PORT_PROMPT = f'Enter worker port ({MIN_PORT}-{MAX_PORT}): '
PORT_RANGE_ERROR = f'Port must be between {MIN_PORT} and {MAX_PORT}'

# Transforms available to the "transform_data" task.
DEFAULT_TRANSFORMS = {
    'double': lambda x: x * 2,
    'square': lambda x: x ** 2,
    'increment': lambda x: x + 1,
}

# Operations available to the "process_data" task.
DATA_OPERATIONS = {
    'reverse': lambda d: d[::-1],
    'uppercase': lambda d: d.upper(),
    'hash': lambda d: hashlib.sha256(d.encode()).hexdigest(),
}


# --------------------------------------------------------------------------
# Helper functions
# --------------------------------------------------------------------------
def _now_iso():
    return datetime.now().isoformat()


def _generate_worker_id():
    digest = hashlib.md5(str(datetime.now()).encode()).hexdigest()
    return digest[:WORKER_ID_LENGTH]


def _encode_json(obj):
    return json.dumps(obj).encode()


def _send_json(conn, obj):
    conn.sendall(_encode_json(obj))


def _success_record(task_id, task_type, execution_time):
    return {
        'task_id': task_id,
        'type': task_type,
        'status': STATUS_COMPLETED,
        'execution_time': execution_time,
        'timestamp': _now_iso(),
    }


def _failure_record(task_id, task_type, error):
    return {
        'task_id': task_id,
        'type': task_type,
        'status': STATUS_FAILED,
        'error': str(error),
        'timestamp': _now_iso(),
    }


def _validate_task(task):
    if not isinstance(task, dict):
        raise ValueError('Task must be a dictionary')


def _validate_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError('Payload must be a dictionary')


def _format_task_history_line(task):
    return f"{task['timestamp']} - {task['type']}: {task['status']}"


def _parse_port(raw):
    port = int(raw)
    if not MIN_PORT <= port <= MAX_PORT:
        raise ValueError(PORT_RANGE_ERROR)
    return port


# --------------------------------------------------------------------------
# Worker
# --------------------------------------------------------------------------
class TaskWorker:

    def __init__(self):
        self.task_queue = []
        self.completed_tasks = []
        self.running = False
        self.worker_id = _generate_worker_id()
        self.task_callbacks = {
            TASK_PROCESS_DATA: self._process_data_task,
            TASK_TRANSFORM_DATA: self._transform_data_task,
        }
        self.allowed_transforms = dict(DEFAULT_TRANSFORMS)

    # -- server lifecycle ---------------------------------------------------
    def start_server(self, port):
        self.running = True
        server_thread = threading.Thread(target=self._run_server, args=(port,))
        server_thread.daemon = True
        server_thread.start()

    def _run_server(self, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((HOST, port))
            s.listen(LISTEN_BACKLOG)
            print(f'Worker {self.worker_id} listening on port {port}')
            while self.running:
                try:
                    (conn, addr) = s.accept()
                    client_thread = threading.Thread(
                        target=self._handle_client, args=(conn, addr)
                    )
                    client_thread.start()
                except Exception as e:
                    print(f'Connection error: {e}')

    # -- client handling ----------------------------------------------------
    def _handle_client(self, conn, addr):
        try:
            data = conn.recv(RECV_BUFFER_SIZE)
            if not data:
                return
            try:
                task = json.loads(data.decode('utf-8'))
                result = self._execute_task(task)
                _send_json(conn, result)
            except json.JSONDecodeError as e:
                _send_json(conn, {'error': ERROR_INVALID_TASK_FORMAT})
        except Exception as e:
            _send_json(conn, {'error': str(e)})
        finally:
            conn.close()

    # -- task execution -----------------------------------------------------
    def _execute_task(self, task):
        _validate_task(task)
        task_id = task.get('task_id', 'unknown')
        task_type = task.get('type')
        payload = task.get('payload', {})
        _validate_payload(payload)
        if task_type not in self.task_callbacks:
            return {'status': STATUS_ERROR, 'message': ERROR_UNKNOWN_TASK_TYPE}
        start_time = time.time()
        try:
            result = self.task_callbacks[task_type](payload)
            execution_time = time.time() - start_time
            self.completed_tasks.append(
                _success_record(task_id, task_type, execution_time)
            )
            return {'status': STATUS_SUCCESS, 'result': result}
        except Exception as e:
            self.completed_tasks.append(_failure_record(task_id, task_type, e))
            return {'status': STATUS_ERROR, 'message': str(e)}

    # -- task implementations -----------------------------------------------
    def _process_data_task(self, payload):
        if 'data' not in payload or not isinstance(payload['data'], str):
            raise ValueError('Invalid data payload')
        data = payload['data']
        operations = payload.get('operations', [])
        if not isinstance(operations, list):
            raise ValueError('Operations must be a list')
        for op in operations:
            if op in DATA_OPERATIONS:
                data = DATA_OPERATIONS[op](data)
            else:
                raise ValueError(f'Invalid operation: {op}')
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

    # -- control / inspection -----------------------------------------------
    def stop(self):
        self.running = False

    def get_task_history(self):
        return self.completed_tasks[-HISTORY_LIMIT:]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main():
    worker = TaskWorker()
    try:
        port = _parse_port(input(PORT_PROMPT))
        worker.start_server(port)
        print('Worker started. Press Ctrl+C to stop.')
        while True:
            time.sleep(MAIN_LOOP_INTERVAL_SECONDS)
    except ValueError as e:
        print(f'Error: {e}')
    except KeyboardInterrupt:
        worker.stop()
        print('\nWorker stopped')
        print('Recent tasks:')
        for task in worker.get_task_history():
            print(_format_task_history_line(task))


if __name__ == '__main__':
    main()
