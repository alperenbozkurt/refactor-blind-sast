import ast
import hashlib
import json
import socket
import sys
import threading
import time
from datetime import datetime

_BUFFER_SIZE = 4096
_LISTEN_BACKLOG = 5
_WORKER_LOOP_DELAY_SECONDS = 0.1

_SUBMIT_COMMAND = b'SUBMIT'
_GET_RESULT_COMMAND = b'GET_RESULT'
_RESULT_PREFIX = b'RESULT:'

_TASK_ACCEPTED = b'TASK_ACCEPTED'
_TASK_REJECTED = b'TASK_REJECTED'
_RESULT_NOT_READY = b'RESULT_NOT_READY'
_INVALID_COMMAND = b'INVALID_COMMAND'

_REQUIRED_TASK_FIELDS = ('task_id', 'function', 'args', 'kwargs')


def _build_allowed_functions():
    return {'len': len, 'sum': sum, 'max': max, 'min': min, 'sorted': sorted}


def _decode_task(task_data):
    return json.loads(task_data.decode('utf-8'))


def _has_required_task_fields(task):
    return all((field in task for field in _REQUIRED_TASK_FIELDS))


def _success_result(task, result, worker_id):
    return {'task_id': task['task_id'], 'result': result, 'worker_id': worker_id, 'success': True}


def _error_result(task, error, worker_id):
    return {'task_id': task['task_id'], 'error': str(error), 'worker_id': worker_id, 'success': False}


class TaskWorker:

    def __init__(self):
        self.task_queue = []
        self.results = {}
        self.worker_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()
        self.running = False
        self.allowed_functions = _build_allowed_functions()

    def _execute_task(self, task):
        try:
            func_name = task['function']
            if func_name not in self.allowed_functions:
                raise ValueError(f'Function {func_name} not allowed')
            func = self.allowed_functions[func_name]
            args = ast.literal_eval(task['args'])
            kwargs = ast.literal_eval(task['kwargs'])
            result = func(*args, **kwargs)
            return _success_result(task, result, self.worker_id)
        except Exception as e:
            return _error_result(task, e, self.worker_id)

    def _process_next_task(self):
        if not self.task_queue:
            return
        task = self.task_queue.pop(0)
        result = self._execute_task(task)
        self.results[task['task_id']] = result

    def process_tasks(self):
        while self.running:
            self._process_next_task()
            time.sleep(_WORKER_LOOP_DELAY_SECONDS)

    def add_task(self, task_data):
        try:
            task = _decode_task(task_data)
            if not _has_required_task_fields(task):
                return False
            self.task_queue.append(task)
            return True
        except Exception as e:
            print(f'Failed to add task: {e}')
            return False


class WorkerServer:

    def __init__(self, host='0.0.0.0', port=5555):
        self.host = host
        self.port = port
        self.worker = TaskWorker()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def _handle_submit(self, conn, task_data):
        if self.worker.add_task(task_data):
            conn.sendall(_TASK_ACCEPTED)
        else:
            conn.sendall(_TASK_REJECTED)

    def _handle_get_result(self, conn, task_id_data):
        task_id = task_id_data.decode()
        result = self.worker.results.get(task_id)
        if result:
            conn.sendall(_RESULT_PREFIX + json.dumps(result).encode('utf-8'))
        else:
            conn.sendall(_RESULT_NOT_READY)

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(_BUFFER_SIZE)
            if not data:
                return
            if data.startswith(_SUBMIT_COMMAND):
                self._handle_submit(conn, data[len(_SUBMIT_COMMAND):])
            elif data.startswith(_GET_RESULT_COMMAND):
                self._handle_get_result(conn, data[len(_GET_RESULT_COMMAND):])
            else:
                conn.sendall(_INVALID_COMMAND)
        except Exception as e:
            print(f'Client error: {e}')
        finally:
            conn.close()

    def _accept_clients(self):
        while True:
            (conn, addr) = self.socket.accept()
            threading.Thread(target=self.handle_client, args=(conn, addr)).start()

    def start(self):
        self.worker.running = True
        threading.Thread(target=self.worker.process_tasks).start()
        self.socket.bind((self.host, self.port))
        self.socket.listen(_LISTEN_BACKLOG)
        print(f'Worker {self.worker.worker_id} listening on {self.host}:{self.port}')
        try:
            self._accept_clients()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.worker.running = False
        self.socket.close()
        print('Worker stopped')


if __name__ == '__main__':
    server = WorkerServer()
    try:
        server.start()
    except Exception as e:
        print(f'Server error: {e}')
        server.stop()
        sys.exit(1)
