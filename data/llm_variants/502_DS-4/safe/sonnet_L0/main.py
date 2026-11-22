import ast
import hashlib
import json
import socket
import sys
import threading
import time
from datetime import datetime

REQUIRED_TASK_FIELDS = ['task_id', 'function', 'args', 'kwargs']
SUBMIT_PREFIX = b'SUBMIT'
GET_RESULT_PREFIX = b'GET_RESULT'


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
                self.results[task['task_id']] = self._execute_task(task)
            time.sleep(0.1)

    def add_task(self, task_data):
        try:
            task = json.loads(task_data.decode('utf-8'))
            if not all(k in task for k in REQUIRED_TASK_FIELDS):
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

    def _process_command(self, data):
        if data.startswith(SUBMIT_PREFIX):
            if self.worker.add_task(data[len(SUBMIT_PREFIX):]):
                return b'TASK_ACCEPTED'
            return b'TASK_REJECTED'
        if data.startswith(GET_RESULT_PREFIX):
            task_id = data[len(GET_RESULT_PREFIX):].decode()
            result = self.worker.results.get(task_id)
            if result:
                return b'RESULT:' + json.dumps(result).encode('utf-8')
            return b'RESULT_NOT_READY'
        return b'INVALID_COMMAND'

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(4096)
            if not data:
                return
            conn.sendall(self._process_command(data))
        except Exception as e:
            print(f'Client error: {e}')
        finally:
            conn.close()

    def start(self):
        self.worker.running = True
        threading.Thread(target=self.worker.process_tasks).start()
        self.socket.bind((self.host, self.port))
        self.socket.listen(5)
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
