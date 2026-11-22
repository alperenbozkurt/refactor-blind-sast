"""TCP worker server that executes whitelisted tasks submitted by clients."""

import ast
import hashlib
import json
import socket
import sys
import threading
import time
from datetime import datetime

# Protocol commands.
CMD_SUBMIT = b'SUBMIT'
CMD_GET_RESULT = b'GET_RESULT'

# Protocol responses.
RESP_TASK_ACCEPTED = b'TASK_ACCEPTED'
RESP_TASK_REJECTED = b'TASK_REJECTED'
RESP_RESULT_PREFIX = b'RESULT:'
RESP_RESULT_NOT_READY = b'RESULT_NOT_READY'
RESP_INVALID_COMMAND = b'INVALID_COMMAND'

REQUIRED_TASK_KEYS = ('task_id', 'function', 'args', 'kwargs')

RECV_BUFFER_SIZE = 4096
LISTEN_BACKLOG = 5
WORKER_POLL_INTERVAL = 0.1


class TaskWorker:

    def __init__(self):
        self.task_queue = []
        self.results = {}
        self.worker_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()
        self.running = False
        self.allowed_functions = {
            'len': len,
            'sum': sum,
            'max': max,
            'min': min,
            'sorted': sorted,
        }

    def _execute_task(self, task):
        try:
            func_name = task['function']
            if func_name not in self.allowed_functions:
                raise ValueError(f'Function {func_name} not allowed')
            func = self.allowed_functions[func_name]
            args = ast.literal_eval(task['args'])
            kwargs = ast.literal_eval(task['kwargs'])
            result = func(*args, **kwargs)
            return {
                'task_id': task['task_id'],
                'result': result,
                'worker_id': self.worker_id,
                'success': True,
            }
        except Exception as e:
            return {
                'task_id': task['task_id'],
                'error': str(e),
                'worker_id': self.worker_id,
                'success': False,
            }

    def process_tasks(self):
        while self.running:
            if self.task_queue:
                task = self.task_queue.pop(0)
                result = self._execute_task(task)
                self.results[task['task_id']] = result
            time.sleep(WORKER_POLL_INTERVAL)

    def add_task(self, task_data):
        try:
            task = json.loads(task_data.decode('utf-8'))
            if not all(k in task for k in REQUIRED_TASK_KEYS):
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

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(RECV_BUFFER_SIZE)
            if not data:
                return
            if data.startswith(CMD_SUBMIT):
                self._handle_submit(conn, data[len(CMD_SUBMIT):])
            elif data.startswith(CMD_GET_RESULT):
                self._handle_get_result(conn, data[len(CMD_GET_RESULT):])
            else:
                conn.sendall(RESP_INVALID_COMMAND)
        except Exception as e:
            print(f'Client error: {e}')
        finally:
            conn.close()

    def _handle_submit(self, conn, task_data):
        if self.worker.add_task(task_data):
            conn.sendall(RESP_TASK_ACCEPTED)
        else:
            conn.sendall(RESP_TASK_REJECTED)

    def _handle_get_result(self, conn, raw_task_id):
        task_id = raw_task_id.decode()
        result = self.worker.results.get(task_id)
        if result:
            conn.sendall(RESP_RESULT_PREFIX + json.dumps(result).encode('utf-8'))
        else:
            conn.sendall(RESP_RESULT_NOT_READY)

    def start(self):
        self.worker.running = True
        threading.Thread(target=self.worker.process_tasks).start()
        self.socket.bind((self.host, self.port))
        self.socket.listen(LISTEN_BACKLOG)
        print(f'Worker {self.worker.worker_id} listening on {self.host}:{self.port}')
        try:
            while True:
                conn, addr = self.socket.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr)).start()
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
