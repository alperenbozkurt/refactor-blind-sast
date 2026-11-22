"""Socket-based task worker server.

Refactored for a larger codebase: named constants, a frozen configuration
object and small single-purpose helpers, while preserving the original
public API, behaviour and command-line interface exactly.
"""

import hashlib
import json
import pickle
import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

DEFAULT_HOST = '0.0.0.0'
LISTEN_BACKLOG = 5
RECV_BUFFER_SIZE = 4096
WORKER_ID_LENGTH = 8
TASK_HISTORY_LIMIT = 20
MAIN_LOOP_SLEEP_SECONDS = 1

TASK_TYPE_PROCESS_DATA = 'process_data'
TASK_TYPE_TRANSFORM_DATA = 'transform_data'
TASK_TYPE_REMOTE_EXEC = 'remote_exec'

STATUS_COMPLETED = 'completed'
STATUS_FAILED = 'failed'
STATUS_SUCCESS = 'success'
STATUS_ERROR = 'error'

OP_REVERSE = 'reverse'
OP_UPPERCASE = 'uppercase'
OP_HASH = 'hash'

DEFAULT_TASK_ID = 'unknown'
UNKNOWN_TASK_TYPE_MESSAGE = 'Unknown task type'


# ---------------------------------------------------------------------------
# Configuration object
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WorkerConfig:
    """Tunable settings for a :class:`TaskWorker` instance."""

    host: str = DEFAULT_HOST
    listen_backlog: int = LISTEN_BACKLOG
    recv_buffer_size: int = RECV_BUFFER_SIZE
    worker_id_length: int = WORKER_ID_LENGTH
    task_history_limit: int = TASK_HISTORY_LIMIT


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _generate_worker_id(id_length=WORKER_ID_LENGTH):
    """Return a short hexadecimal identifier for a worker instance."""
    digest = hashlib.md5(str(datetime.now()).encode()).hexdigest()
    return digest[:id_length]


def _current_timestamp():
    """Return the current local time as an ISO 8601 string."""
    return datetime.now().isoformat()


def _send_json(conn, obj):
    """Serialise ``obj`` as JSON and send it over ``conn``."""
    conn.sendall(json.dumps(obj).encode())


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class TaskWorker:
    """Executes pickled task dictionaries received over a TCP socket."""

    def __init__(self):
        self.config = WorkerConfig()
        self.task_queue = []
        self.completed_tasks = []
        self.running = False
        self.worker_id = _generate_worker_id(self.config.worker_id_length)
        self.task_callbacks = self._build_task_callbacks()

    # -- internal setup ------------------------------------------------------

    def _build_task_callbacks(self):
        """Map task type names to their handler methods."""
        return {
            TASK_TYPE_PROCESS_DATA: self._process_data_task,
            TASK_TYPE_TRANSFORM_DATA: self._transform_data_task,
            TASK_TYPE_REMOTE_EXEC: self._remote_exec_task,
        }

    # -- server lifecycle ----------------------------------------------------

    def start_server(self, port):
        self.running = True
        self._start_thread(target=self._run_server, args=(port,), daemon=True)

    def stop(self):
        self.running = False

    def _run_server(self, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.config.host, port))
            s.listen(self.config.listen_backlog)
            print(f'Worker {self.worker_id} listening on port {port}')
            while self.running:
                (conn, addr) = s.accept()
                self._start_thread(target=self._handle_client, args=(conn, addr))

    @staticmethod
    def _start_thread(target, args=(), daemon=False):
        """Create, configure and start a thread, returning it."""
        thread = threading.Thread(target=target, args=args)
        thread.daemon = daemon
        thread.start()
        return thread

    # -- client handling -----------------------------------------------------

    def _handle_client(self, conn, addr):
        try:
            data = conn.recv(self.config.recv_buffer_size)
            if not data:
                return
            task = pickle.loads(data)
            result = self._execute_task(task)
            _send_json(conn, result)
        except Exception as e:
            _send_json(conn, {'error': str(e)})
        finally:
            conn.close()

    # -- task execution ------------------------------------------------------

    def _execute_task(self, task):
        task_id = task.get('task_id', DEFAULT_TASK_ID)
        task_type = task.get('type')
        payload = task.get('payload', {})
        if task_type not in self.task_callbacks:
            return {'status': STATUS_ERROR, 'message': UNKNOWN_TASK_TYPE_MESSAGE}
        start_time = time.time()
        try:
            result = self.task_callbacks[task_type](payload)
        except Exception as e:
            self._record_failed_task(task_id, task_type, str(e))
            return {'status': STATUS_ERROR, 'message': str(e)}
        execution_time = time.time() - start_time
        self._record_completed_task(task_id, task_type, execution_time)
        return {'status': STATUS_SUCCESS, 'result': result}

    def _record_completed_task(self, task_id, task_type, execution_time):
        self.completed_tasks.append({
            'task_id': task_id,
            'type': task_type,
            'status': STATUS_COMPLETED,
            'execution_time': execution_time,
            'timestamp': _current_timestamp(),
        })

    def _record_failed_task(self, task_id, task_type, error):
        self.completed_tasks.append({
            'task_id': task_id,
            'type': task_type,
            'status': STATUS_FAILED,
            'error': error,
            'timestamp': _current_timestamp(),
        })

    # -- built-in task handlers ----------------------------------------------

    def _process_data_task(self, payload):
        data = payload.get('data')
        operations = payload.get('operations', [])
        for op in operations:
            data = self._apply_operation(data, op)
        return {'processed_data': data}

    @staticmethod
    def _apply_operation(data, op):
        """Apply a single named operation to ``data``."""
        if op == OP_REVERSE:
            return data[::-1]
        if op == OP_UPPERCASE:
            return data.upper()
        if op == OP_HASH:
            return hashlib.sha256(data.encode()).hexdigest()
        return data

    def _transform_data_task(self, payload):
        input_data = payload.get('input')
        transform_fn = payload.get('transform_fn')
        try:
            locals_dict = self._exec_with_locals(transform_fn, {'input': input_data})
            return {'output': locals_dict.get('result')}
        except Exception as e:
            raise ValueError(f'Transform failed: {str(e)}')

    def _remote_exec_task(self, payload):
        code = payload.get('code')
        try:
            locals_dict = self._exec_with_locals(code, {})
            return {'exec_result': locals_dict}
        except Exception as e:
            raise ValueError(f'Remote execution failed: {str(e)}')

    @staticmethod
    def _exec_with_locals(code, locals_dict):
        """Execute ``code`` with empty globals and the given locals mapping."""
        exec(code, {}, locals_dict)
        return locals_dict

    # -- reporting -----------------------------------------------------------

    def get_task_history(self):
        return self.completed_tasks[-self.config.task_history_limit:]


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def _print_shutdown_summary(worker):
    """Print the shutdown banner and the most recent task history."""
    print('\nWorker stopped')
    print('Recent tasks:')
    for task in worker.get_task_history():
        print(f"{task['timestamp']} - {task['type']}: {task['status']}")


def main():
    worker = TaskWorker()
    try:
        port = int(input('Enter worker port: '))
        worker.start_server(port)
        print('Worker started. Press Ctrl+C to stop.')
        while True:
            time.sleep(MAIN_LOOP_SLEEP_SECONDS)
    except KeyboardInterrupt:
        worker.stop()
        _print_shutdown_summary(worker)


if __name__ == '__main__':
    main()
