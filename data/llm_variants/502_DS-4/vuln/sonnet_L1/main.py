import socket
import pickle
import sys
import hashlib
import threading
import time
from datetime import datetime


class TaskWorker:
    """Holds a queue of pickled tasks, executes them and stores the results."""

    REQUIRED_TASK_FIELDS = ('task_id', 'function', 'args', 'kwargs')
    POLL_INTERVAL_SECONDS = 0.1

    def __init__(self):
        self.task_queue = []
        self.results = {}
        self.worker_id = self._generate_worker_id()
        self.running = False

    @staticmethod
    def _generate_worker_id():
        return hashlib.md5(str(datetime.now()).encode()).hexdigest()

    def _build_result(self, task, success, **payload):
        result = {'task_id': task['task_id']}
        result.update(payload)
        result['worker_id'] = self.worker_id
        result['success'] = success
        return result

    def _execute_task(self, task):
        try:
            func = pickle.loads(task['function'])
            args = pickle.loads(task['args'])
            kwargs = pickle.loads(task['kwargs'])
            result = func(*args, **kwargs)
            return self._build_result(task, True, result=result)
        except Exception as e:
            return self._build_result(task, False, error=str(e))

    def process_tasks(self):
        while self.running:
            if self.task_queue:
                task = self.task_queue.pop(0)
                self.results[task['task_id']] = self._execute_task(task)
            time.sleep(self.POLL_INTERVAL_SECONDS)

    def _has_required_fields(self, task):
        return all(field in task for field in self.REQUIRED_TASK_FIELDS)

    def add_task(self, task_data):
        try:
            task = pickle.loads(task_data)
            if not self._has_required_fields(task):
                return False
            self.task_queue.append(task)
            return True
        except Exception as e:
            print(f'Failed to add task: {e}')
            return False


class WorkerServer:
    """TCP server exposing a TaskWorker via simple SUBMIT / GET_RESULT commands."""

    RECV_BUFFER_SIZE = 4096
    LISTEN_BACKLOG = 5
    SUBMIT_COMMAND = b'SUBMIT'
    GET_RESULT_COMMAND = b'GET_RESULT'

    def __init__(self, host='0.0.0.0', port=5555):
        self.host = host
        self.port = port
        self.worker = TaskWorker()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def _handle_submit(self, conn, data):
        task_data = data[len(self.SUBMIT_COMMAND):]
        if self.worker.add_task(task_data):
            conn.sendall(b'TASK_ACCEPTED')
        else:
            conn.sendall(b'TASK_REJECTED')

    def _handle_get_result(self, conn, data):
        task_id = data[len(self.GET_RESULT_COMMAND):].decode()
        result = self.worker.results.get(task_id)
        if result:
            conn.sendall(b'RESULT:' + pickle.dumps(result))
        else:
            conn.sendall(b'RESULT_NOT_READY')

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(self.RECV_BUFFER_SIZE)
            if not data:
                return
            if data.startswith(self.SUBMIT_COMMAND):
                self._handle_submit(conn, data)
            elif data.startswith(self.GET_RESULT_COMMAND):
                self._handle_get_result(conn, data)
            else:
                conn.sendall(b'INVALID_COMMAND')
        except Exception as e:
            print(f'Client error: {e}')
        finally:
            conn.close()

    def start(self):
        self.worker.running = True
        threading.Thread(target=self.worker.process_tasks).start()
        self.socket.bind((self.host, self.port))
        self.socket.listen(self.LISTEN_BACKLOG)
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
