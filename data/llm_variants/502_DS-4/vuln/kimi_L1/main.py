"""A simple TCP-based distributed task worker.

Clients submit pickled tasks with the ``SUBMIT`` command and poll for the
outcome with ``GET_RESULT``. Tasks are executed sequentially in a background
thread and their results are kept in memory.

Note: task payloads are deserialized with pickle, which is only safe with
fully trusted clients.
"""

import socket
import pickle
import sys
import hashlib
import threading
import time
from datetime import datetime

# Protocol commands (client -> server).
SUBMIT_COMMAND = b'SUBMIT'
GET_RESULT_COMMAND = b'GET_RESULT'

# Protocol responses (server -> client).
TASK_ACCEPTED_RESPONSE = b'TASK_ACCEPTED'
TASK_REJECTED_RESPONSE = b'TASK_REJECTED'
RESULT_RESPONSE_PREFIX = b'RESULT:'
RESULT_NOT_READY_RESPONSE = b'RESULT_NOT_READY'
INVALID_COMMAND_RESPONSE = b'INVALID_COMMAND'

# Keys every task dictionary must define.
REQUIRED_TASK_KEYS = ('task_id', 'function', 'args', 'kwargs')

# Socket and worker-loop settings.
RECV_BUFFER_SIZE = 4096
LISTEN_BACKLOG = 5
WORKER_POLL_INTERVAL_SECONDS = 0.1


class TaskWorker:
    """Queues pickled tasks, executes them and stores their results."""

    def __init__(self):
        self.task_queue = []
        self.results = {}
        self.worker_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()
        self.running = False

    def _execute_task(self, task):
        """Execute a single task and build its result dictionary."""
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
        """Execute queued tasks one at a time while the worker is running."""
        while self.running:
            if self.task_queue:
                task = self.task_queue.pop(0)
                result = self._execute_task(task)
                self.results[task['task_id']] = result
            time.sleep(WORKER_POLL_INTERVAL_SECONDS)

    def add_task(self, task_data):
        """Unpickle, validate and enqueue a task; return True if accepted."""
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
    """Serves a TaskWorker over TCP using a simple command protocol."""

    def __init__(self, host='0.0.0.0', port=5555):
        self.host = host
        self.port = port
        self.worker = TaskWorker()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def handle_client(self, conn, addr):
        """Process one client request and then close the connection."""
        try:
            data = conn.recv(RECV_BUFFER_SIZE)
            if not data:
                return
            if data.startswith(SUBMIT_COMMAND):
                self._handle_submit(conn, data)
            elif data.startswith(GET_RESULT_COMMAND):
                self._handle_get_result(conn, data)
            else:
                conn.sendall(INVALID_COMMAND_RESPONSE)
        except Exception as e:
            print(f'Client error: {e}')
        finally:
            conn.close()

    def _handle_submit(self, conn, data):
        """Enqueue the submitted task and report whether it was accepted."""
        task_data = data[len(SUBMIT_COMMAND):]
        if self.worker.add_task(task_data):
            conn.sendall(TASK_ACCEPTED_RESPONSE)
        else:
            conn.sendall(TASK_REJECTED_RESPONSE)

    def _handle_get_result(self, conn, data):
        """Reply with the pickled result for a task, if one is available."""
        task_id = data[len(GET_RESULT_COMMAND):].decode()
        result = self.worker.results.get(task_id)
        if result:
            conn.sendall(RESULT_RESPONSE_PREFIX + pickle.dumps(result))
        else:
            conn.sendall(RESULT_NOT_READY_RESPONSE)

    def start(self):
        """Start the background worker and serve clients until interrupted."""
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
        """Stop the worker loop and close the listening socket."""
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
