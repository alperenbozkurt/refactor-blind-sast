import socket
import pickle
import sys
import hashlib
import threading
import time
from datetime import datetime

# --- Network configuration -------------------------------------------------
DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 5555
RECV_BUFFER_SIZE = 4096
LISTEN_BACKLOG = 5

# --- Worker configuration --------------------------------------------------
POLL_INTERVAL_SECONDS = 0.1
REQUIRED_TASK_FIELDS = ('task_id', 'function', 'args', 'kwargs')

# --- Protocol definitions --------------------------------------------------
CMD_SUBMIT = b'SUBMIT'
CMD_GET_RESULT = b'GET_RESULT'

RESP_TASK_ACCEPTED = b'TASK_ACCEPTED'
RESP_TASK_REJECTED = b'TASK_REJECTED'
RESP_RESULT_PREFIX = b'RESULT:'
RESP_RESULT_NOT_READY = b'RESULT_NOT_READY'
RESP_INVALID_COMMAND = b'INVALID_COMMAND'

EXIT_CODE_SERVER_ERROR = 1


def _generate_worker_id():
    """Create a unique worker identifier based on the current time."""
    return hashlib.md5(str(datetime.now()).encode()).hexdigest()


def _build_success_result(task_id, result, worker_id):
    return {'task_id': task_id, 'result': result, 'worker_id': worker_id, 'success': True}


def _build_error_result(task_id, error, worker_id):
    return {'task_id': task_id, 'error': str(error), 'worker_id': worker_id, 'success': False}


def _has_required_fields(task):
    return all((k in task for k in REQUIRED_TASK_FIELDS))


class TaskWorker:

    def __init__(self):
        self.task_queue = []
        self.results = {}
        self.worker_id = _generate_worker_id()
        self.running = False

    def _execute_task(self, task):
        try:
            func = pickle.loads(task['function'])
            args = pickle.loads(task['args'])
            kwargs = pickle.loads(task['kwargs'])
            result = func(*args, **kwargs)
            return _build_success_result(task['task_id'], result, self.worker_id)
        except Exception as e:
            return _build_error_result(task['task_id'], e, self.worker_id)

    def _process_next_task(self):
        """Run the next queued task, if any, and store its result."""
        if self.task_queue:
            task = self.task_queue.pop(0)
            result = self._execute_task(task)
            self.results[task['task_id']] = result

    def process_tasks(self):
        while self.running:
            self._process_next_task()
            time.sleep(POLL_INTERVAL_SECONDS)

    def add_task(self, task_data):
        try:
            task = pickle.loads(task_data)
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
        self.socket = self._create_socket()

    @staticmethod
    def _create_socket():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock

    def _handle_submit(self, conn, data):
        task_data = data[len(CMD_SUBMIT):]
        if self.worker.add_task(task_data):
            conn.sendall(RESP_TASK_ACCEPTED)
        else:
            conn.sendall(RESP_TASK_REJECTED)

    def _handle_get_result(self, conn, data):
        task_id = data[len(CMD_GET_RESULT):].decode()
        result = self.worker.results.get(task_id)
        if result:
            conn.sendall(RESP_RESULT_PREFIX + pickle.dumps(result))
        else:
            conn.sendall(RESP_RESULT_NOT_READY)

    def _dispatch(self, conn, data):
        if data.startswith(CMD_SUBMIT):
            self._handle_submit(conn, data)
        elif data.startswith(CMD_GET_RESULT):
            self._handle_get_result(conn, data)
        else:
            conn.sendall(RESP_INVALID_COMMAND)

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(RECV_BUFFER_SIZE)
            if not data:
                return
            self._dispatch(conn, data)
        except Exception as e:
            print(f'Client error: {e}')
        finally:
            conn.close()

    def _spawn_client_thread(self, conn, addr):
        threading.Thread(target=self.handle_client, args=(conn, addr)).start()

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
        sys.exit(EXIT_CODE_SERVER_ERROR)


if __name__ == '__main__':
    main()
