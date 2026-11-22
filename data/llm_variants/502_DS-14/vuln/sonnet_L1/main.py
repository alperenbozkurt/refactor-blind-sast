import pickle
import socket
import threading
import time
import hashlib
import json
from datetime import datetime

BIND_HOST = '0.0.0.0'
LISTEN_BACKLOG = 5
RECV_BUFFER_SIZE = 4096
TASK_HISTORY_LIMIT = 20
WORKER_ID_LENGTH = 8


def _now_iso():
    return datetime.now().isoformat()


def _reverse(data):
    return data[::-1]


def _uppercase(data):
    return data.upper()


def _sha256_hex(data):
    return hashlib.sha256(data.encode()).hexdigest()


class TaskWorker:
    """Worker that accepts tasks over a TCP socket and executes them."""

    DATA_OPERATIONS = {
        'reverse': _reverse,
        'uppercase': _uppercase,
        'hash': _sha256_hex,
    }

    def __init__(self):
        self.task_queue = []
        self.completed_tasks = []
        self.running = False
        self.worker_id = self._generate_worker_id()
        self.task_callbacks = {
            'process_data': self._process_data_task,
            'transform_data': self._transform_data_task,
            'remote_exec': self._remote_exec_task,
        }

    @staticmethod
    def _generate_worker_id():
        digest = hashlib.md5(str(datetime.now()).encode()).hexdigest()
        return digest[:WORKER_ID_LENGTH]

    # ------------------------------------------------------------------
    # Server handling
    # ------------------------------------------------------------------

    def start_server(self, port):
        self.running = True
        server_thread = threading.Thread(target=self._run_server, args=(port,))
        server_thread.daemon = True
        server_thread.start()

    def _run_server(self, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((BIND_HOST, port))
            server_socket.listen(LISTEN_BACKLOG)
            print(f'Worker {self.worker_id} listening on port {port}')
            while self.running:
                (conn, addr) = server_socket.accept()
                client_thread = threading.Thread(
                    target=self._handle_client, args=(conn, addr)
                )
                client_thread.start()

    def _handle_client(self, conn, addr):
        try:
            data = conn.recv(RECV_BUFFER_SIZE)
            if not data:
                return
            task = pickle.loads(data)
            result = self._execute_task(task)
            self._send_json(conn, result)
        except Exception as e:
            self._send_json(conn, {'error': str(e)})
        finally:
            conn.close()

    @staticmethod
    def _send_json(conn, payload):
        conn.sendall(json.dumps(payload).encode())

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    def _execute_task(self, task):
        task_id = task.get('task_id', 'unknown')
        task_type = task.get('type')
        payload = task.get('payload', {})

        if task_type not in self.task_callbacks:
            return {'status': 'error', 'message': 'Unknown task type'}

        start_time = time.time()
        try:
            result = self.task_callbacks[task_type](payload)
            execution_time = time.time() - start_time
            self.completed_tasks.append({
                'task_id': task_id,
                'type': task_type,
                'status': 'completed',
                'execution_time': execution_time,
                'timestamp': _now_iso(),
            })
            return {'status': 'success', 'result': result}
        except Exception as e:
            self.completed_tasks.append({
                'task_id': task_id,
                'type': task_type,
                'status': 'failed',
                'error': str(e),
                'timestamp': _now_iso(),
            })
            return {'status': 'error', 'message': str(e)}

    def _process_data_task(self, payload):
        data = payload.get('data')
        operations = payload.get('operations', [])
        for op in operations:
            operation = self.DATA_OPERATIONS.get(op)
            if operation is not None:
                data = operation(data)
        return {'processed_data': data}

    def _transform_data_task(self, payload):
        input_data = payload.get('input')
        transform_fn = payload.get('transform_fn')
        try:
            locals_dict = {'input': input_data}
            exec(transform_fn, {}, locals_dict)
            return {'output': locals_dict.get('result')}
        except Exception as e:
            raise ValueError(f'Transform failed: {str(e)}')

    def _remote_exec_task(self, payload):
        code = payload.get('code')
        try:
            locals_dict = {}
            exec(code, {}, locals_dict)
            return {'exec_result': locals_dict}
        except Exception as e:
            raise ValueError(f'Remote execution failed: {str(e)}')

    # ------------------------------------------------------------------
    # Control and inspection
    # ------------------------------------------------------------------

    def stop(self):
        self.running = False

    def get_task_history(self):
        return self.completed_tasks[-TASK_HISTORY_LIMIT:]


def main():
    worker = TaskWorker()
    try:
        port = int(input('Enter worker port: '))
        worker.start_server(port)
        print('Worker started. Press Ctrl+C to stop.')
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        worker.stop()
        print('\nWorker stopped')
        print('Recent tasks:')
        for task in worker.get_task_history():
            print(f"{task['timestamp']} - {task['type']}: {task['status']}")


if __name__ == '__main__':
    main()
