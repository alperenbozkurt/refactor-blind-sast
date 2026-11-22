import socket
import pickle
import sys
import hashlib
import threading
import time
from datetime import datetime

REQUIRED_TASK_KEYS = ('task_id', 'function', 'args', 'kwargs')

CMD_SUBMIT = b'SUBMIT'
CMD_GET_RESULT = b'GET_RESULT'

RESP_ACCEPTED = b'TASK_ACCEPTED'
RESP_REJECTED = b'TASK_REJECTED'
RESP_RESULT_PREFIX = b'RESULT:'
RESP_NOT_READY = b'RESULT_NOT_READY'
RESP_INVALID = b'INVALID_COMMAND'


class TaskWorker:

    def __init__(self):
        self.task_queue = []
        self.results = {}
        self.worker_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()
        self.running = False

    def _execute_task(self, task):
        try:
            func = pickle.loads(task['function'])
            args = pickle.loads(task['args'])
            kwargs = pickle.loads(task['kwargs'])
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
            task = pickle.loads(task_data)
            if not all(key in task for key in REQUIRED_TASK_KEYS):
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

    def _handle_submit(self, data):
        task_data = data[len(CMD_SUBMIT):]
        return RESP_ACCEPTED if self.worker.add_task(task_data) else RESP_REJECTED

    def _handle_get_result(self, data):
        task_id = data[len(CMD_GET_RESULT):].decode()
        result = self.worker.results.get(task_id)
        if result:
            return RESP_RESULT_PREFIX + pickle.dumps(result)
        return RESP_NOT_READY

    def _build_response(self, data):
        if data.startswith(CMD_SUBMIT):
            return self._handle_submit(data)
        if data.startswith(CMD_GET_RESULT):
            return self._handle_get_result(data)
        return RESP_INVALID

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(4096)
            if not data:
                return
            conn.sendall(self._build_response(data))
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
