import socket
import json
import sys
import hashlib
import threading
import time
from datetime import datetime
import ast

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 5555
RECV_BUFFER_SIZE = 4096
LISTEN_BACKLOG = 5
QUEUE_POLL_INTERVAL_SECONDS = 0.1
TEXT_ENCODING = 'utf-8'

REQUIRED_TASK_FIELDS = ['task_id', 'function', 'args', 'kwargs']

CMD_SUBMIT = b'SUBMIT'
CMD_GET_RESULT = b'GET_RESULT'

RESP_TASK_ACCEPTED = b'TASK_ACCEPTED'
RESP_TASK_REJECTED = b'TASK_REJECTED'
RESP_RESULT_PREFIX = b'RESULT:'
RESP_RESULT_NOT_READY = b'RESULT_NOT_READY'
RESP_INVALID_COMMAND = b'INVALID_COMMAND'

DEFAULT_ALLOWED_FUNCTIONS = {
    'len': len,
    'sum': sum,
    'max': max,
    'min': min,
    'sorted': sorted,
}


def _generate_worker_id():
    return hashlib.md5(str(datetime.now()).encode()).hexdigest()


def _has_required_fields(task):
    return all((k in task for k in REQUIRED_TASK_FIELDS))


class TaskWorker:

    def __init__(self):
        self.task_queue = []
        self.results = {}
        self.worker_id = _generate_worker_id()
        self.running = False
        self.allowed_functions = dict(DEFAULT_ALLOWED_FUNCTIONS)

    def _success_result(self, task, result):
        return {'task_id': task['task_id'], 'result': result, 'worker_id': self.worker_id, 'success': True}

    def _error_result(self, task, error):
        return {'task_id': task['task_id'], 'error': str(error), 'worker_id': self.worker_id, 'success': False}

    def _resolve_function(self, func_name):
        if func_name not in self.allowed_functions:
            raise ValueError(f'Function {func_name} not allowed')
        return self.allowed_functions[func_name]

    def _execute_task(self, task):
        try:
            func = self._resolve_function(task['function'])
            args = ast.literal_eval(task['args'])
            kwargs = ast.literal_eval(task['kwargs'])
            result = func(*args, **kwargs)
            return self._success_result(task, result)
        except Exception as e:
            return self._error_result(task, e)

    def _process_next_task(self):
        if self.task_queue:
            task = self.task_queue.pop(0)
            result = self._execute_task(task)
            self.results[task['task_id']] = result

    def process_tasks(self):
        while self.running:
            self._process_next_task()
            time.sleep(QUEUE_POLL_INTERVAL_SECONDS)

    def add_task(self, task_data):
        try:
            task = json.loads(task_data.decode(TEXT_ENCODING))
            if not _has_required_fields(task):
                return False
            self.task_queue.append(task)
            return True
        except Exception as e:
            print(f'Failed to add task: {e}')
            return False


class WorkerServer:

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.worker = TaskWorker()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def _handle_submit(self, data):
        task_data = data[len(CMD_SUBMIT):]
        if self.worker.add_task(task_data):
            return RESP_TASK_ACCEPTED
        return RESP_TASK_REJECTED

    def _handle_get_result(self, data):
        task_id = data[len(CMD_GET_RESULT):].decode()
        result = self.worker.results.get(task_id)
        if result:
            return RESP_RESULT_PREFIX + json.dumps(result).encode(TEXT_ENCODING)
        return RESP_RESULT_NOT_READY

    def _dispatch(self, data):
        if data.startswith(CMD_SUBMIT):
            return self._handle_submit(data)
        if data.startswith(CMD_GET_RESULT):
            return self._handle_get_result(data)
        return RESP_INVALID_COMMAND

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(RECV_BUFFER_SIZE)
            if not data:
                return
            conn.sendall(self._dispatch(data))
        except Exception as e:
            print(f'Client error: {e}')
        finally:
            conn.close()

    def start(self):
        self.worker.running = True
        threading.Thread(target=self.worker.process_tasks).start()
        self.socket.bind((self.host, self.port))
        self.socket.listen(LISTEN_BACKLOG)
        print(f'Worker {self.worker.worker_id} listening on {self.host}:{self.port}')
        try:
            while True:
                (conn, addr) = self.socket.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr)).start()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.worker.running = False
        self.socket.close()
        print('Worker stopped')


def main():
    server = WorkerServer()
    try:
        server.start()
    except Exception as e:
        print(f'Server error: {e}')
        server.stop()
        sys.exit(1)


if __name__ == '__main__':
    main()
