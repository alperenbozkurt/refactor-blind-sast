"""Distributed task worker server.

Receives pickled tasks over a simple TCP protocol, executes them in a
background worker loop and serves the results back to clients.
"""

import hashlib
import pickle
import socket
import sys
import threading
import time
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 5555

BUFFER_SIZE = 4096
LISTEN_BACKLOG = 5
POLL_INTERVAL_SECONDS = 0.1

# Protocol commands.
COMMAND_SUBMIT = b'SUBMIT'
COMMAND_GET_RESULT = b'GET_RESULT'

# Protocol responses.
RESPONSE_TASK_ACCEPTED = b'TASK_ACCEPTED'
RESPONSE_TASK_REJECTED = b'TASK_REJECTED'
RESPONSE_RESULT_PREFIX = b'RESULT:'
RESPONSE_RESULT_NOT_READY = b'RESULT_NOT_READY'
RESPONSE_INVALID_COMMAND = b'INVALID_COMMAND'

REQUIRED_TASK_KEYS = ('task_id', 'function', 'args', 'kwargs')


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _deserialize(payload):
    """Unpickle a payload received from a client."""
    return pickle.loads(payload)


def _serialize(payload):
    """Pickle a payload to send to a client."""
    return pickle.dumps(payload)


def _generate_worker_id():
    """Return a unique identifier for a worker instance."""
    return hashlib.md5(str(datetime.now()).encode()).hexdigest()


class TaskWorker:
    """Executes queued tasks in a background loop."""

    def __init__(self):
        self.task_queue = []
        self.results = {}
        self.worker_id = _generate_worker_id()
        self.running = False

    # -- task execution ----------------------------------------------------

    def _execute_task(self, task):
        try:
            result = self._call_task_function(task)
            return self._success_result(task, result)
        except Exception as e:
            return self._failure_result(task, str(e))

    @staticmethod
    def _call_task_function(task):
        func = _deserialize(task['function'])
        args = _deserialize(task['args'])
        kwargs = _deserialize(task['kwargs'])
        return func(*args, **kwargs)

    def _success_result(self, task, result):
        return {
            'task_id': task['task_id'],
            'result': result,
            'worker_id': self.worker_id,
            'success': True,
        }

    def _failure_result(self, task, error):
        return {
            'task_id': task['task_id'],
            'error': error,
            'worker_id': self.worker_id,
            'success': False,
        }

    # -- queue processing --------------------------------------------------

    def process_tasks(self):
        while self.running:
            self._process_next_task()
            time.sleep(POLL_INTERVAL_SECONDS)

    def _process_next_task(self):
        if self.task_queue:
            task = self.task_queue.pop(0)
            result = self._execute_task(task)
            self.results[task['task_id']] = result

    def add_task(self, task_data):
        try:
            task = _deserialize(task_data)
            if not self._is_valid_task(task):
                return False
            self.task_queue.append(task)
            return True
        except Exception as e:
            print(f'Failed to add task: {e}')
            return False

    @staticmethod
    def _is_valid_task(task):
        return all((key in task for key in REQUIRED_TASK_KEYS))


class WorkerServer:
    """TCP server exposing a :class:`TaskWorker` to remote clients."""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.worker = TaskWorker()
        self.socket = self._create_socket()

    @staticmethod
    def _create_socket():
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return server_socket

    # -- request handling --------------------------------------------------

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(BUFFER_SIZE)
            if not data:
                return
            conn.sendall(self._dispatch(data))
        except Exception as e:
            print(f'Client error: {e}')
        finally:
            conn.close()

    def _dispatch(self, data):
        if data.startswith(COMMAND_SUBMIT):
            return self._handle_submit(data[len(COMMAND_SUBMIT):])
        if data.startswith(COMMAND_GET_RESULT):
            return self._handle_get_result(data[len(COMMAND_GET_RESULT):])
        return RESPONSE_INVALID_COMMAND

    def _handle_submit(self, task_data):
        if self.worker.add_task(task_data):
            return RESPONSE_TASK_ACCEPTED
        return RESPONSE_TASK_REJECTED

    def _handle_get_result(self, raw_task_id):
        task_id = raw_task_id.decode()
        result = self.worker.results.get(task_id)
        if result:
            return RESPONSE_RESULT_PREFIX + _serialize(result)
        return RESPONSE_RESULT_NOT_READY

    # -- lifecycle ---------------------------------------------------------

    def start(self):
        self.worker.running = True
        threading.Thread(target=self.worker.process_tasks).start()
        self.socket.bind((self.host, self.port))
        self.socket.listen(LISTEN_BACKLOG)
        print(f'Worker {self.worker.worker_id} listening on {self.host}:{self.port}')
        try:
            while True:
                (conn, addr) = self.socket.accept()
                self._spawn_client_thread(conn, addr)
        except KeyboardInterrupt:
            self.stop()

    def _spawn_client_thread(self, conn, addr):
        threading.Thread(target=self.handle_client, args=(conn, addr)).start()

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
