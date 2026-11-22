import hashlib
import json
import pickle
import socket
import threading
import time
from datetime import datetime

HOST = '0.0.0.0'
LISTEN_BACKLOG = 5
RECV_BUFFER_SIZE = 4096
WORKER_ID_LENGTH = 8
TASK_HISTORY_LIMIT = 20


class TaskWorker:
    """A worker node that receives tasks over TCP and executes them."""

    def __init__(self):
        self.task_queue = []
        self.completed_tasks = []
        self.running = False
        self.worker_id = hashlib.md5(
            str(datetime.now()).encode()
        ).hexdigest()[:WORKER_ID_LENGTH]
        self.task_callbacks = {
            'process_data': self._process_data_task,
            'transform_data': self._transform_data_task,
            'remote_exec': self._remote_exec_task,
        }

    def start_server(self, port):
        self.running = True
        server_thread = threading.Thread(target=self._run_server, args=(port,))
        server_thread.daemon = True
        server_thread.start()

    def _run_server(self, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((HOST, port))
            server_socket.listen(LISTEN_BACKLOG)
            print(f'Worker {self.worker_id} listening on port {port}')
            while self.running:
                conn, addr = server_socket.accept()
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
            conn.sendall(json.dumps(result).encode())
        except Exception as e:
            conn.sendall(json.dumps({'error': str(e)}).encode())
        finally:
            conn.close()

    def _execute_task(self, task):
        task_id = task.get('task_id', 'unknown')
        task_type = task.get('type')
        payload = task.get('payload', {})

        callback = self.task_callbacks.get(task_type)
        if callback is None:
            return {'status': 'error', 'message': 'Unknown task type'}

        start_time = time.time()
        try:
            result = callback(payload)
        except Exception as e:
            self._record_task(task_id, task_type, 'failed', error=str(e))
            return {'status': 'error', 'message': str(e)}

        execution_time = time.time() - start_time
        self._record_task(
            task_id, task_type, 'completed', execution_time=execution_time
        )
        return {'status': 'success', 'result': result}

    def _record_task(self, task_id, task_type, status, **details):
        task_record = {
            'task_id': task_id,
            'type': task_type,
            'status': status,
            **details,
            'timestamp': datetime.now().isoformat(),
        }
        self.completed_tasks.append(task_record)

    def _process_data_task(self, payload):
        data = payload.get('data')
        operations = payload.get('operations', [])
        for op in operations:
            if op == 'reverse':
                data = data[::-1]
            elif op == 'uppercase':
                data = data.upper()
            elif op == 'hash':
                data = hashlib.sha256(data.encode()).hexdigest()
        return {'processed_data': data}

    def _transform_data_task(self, payload):
        input_data = payload.get('input')
        transform_fn = payload.get('transform_fn')
        try:
            locals_dict = {'input': input_data}
            exec(transform_fn, {}, locals_dict)
            return {'output': locals_dict.get('result')}
        except Exception as e:
            raise ValueError(f'Transform failed: {e}')

    def _remote_exec_task(self, payload):
        code = payload.get('code')
        try:
            locals_dict = {}
            exec(code, {}, locals_dict)
            return {'exec_result': locals_dict}
        except Exception as e:
            raise ValueError(f'Remote execution failed: {e}')

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
