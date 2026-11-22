import pickle
import socket
import threading
import time
import hashlib
import json
from datetime import datetime

# NOTE: This worker unpickles untrusted network input and executes arbitrary
# code ('transform_data', 'remote_exec'). That behaviour is preserved as-is;
# only expose it on trusted networks.

HISTORY_LIMIT = 20
RECV_BUFFER_SIZE = 4096


def _now_iso():
    return datetime.now().isoformat()


class TaskWorker:

    _DATA_OPERATIONS = {
        'reverse': lambda data: data[::-1],
        'uppercase': lambda data: data.upper(),
        'hash': lambda data: hashlib.sha256(data.encode()).hexdigest(),
    }

    def __init__(self):
        self.task_queue = []
        self.completed_tasks = []
        self.running = False
        self.worker_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]
        self.task_callbacks = {
            'process_data': self._process_data_task,
            'transform_data': self._transform_data_task,
            'remote_exec': self._remote_exec_task,
        }

    # ---- server -----------------------------------------------------------

    def start_server(self, port):
        self.running = True
        server_thread = threading.Thread(target=self._run_server, args=(port,))
        server_thread.daemon = True
        server_thread.start()

    def _run_server(self, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('0.0.0.0', port))
            s.listen(5)
            print(f'Worker {self.worker_id} listening on port {port}')
            while self.running:
                conn, addr = s.accept()
                threading.Thread(target=self._handle_client, args=(conn, addr)).start()

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

    # ---- task execution ---------------------------------------------------

    def _execute_task(self, task):
        task_id = task.get('task_id', 'unknown')
        task_type = task.get('type')
        payload = task.get('payload', {})

        if task_type not in self.task_callbacks:
            return {'status': 'error', 'message': 'Unknown task type'}

        start_time = time.time()
        try:
            result = self.task_callbacks[task_type](payload)
            self.completed_tasks.append({
                'task_id': task_id,
                'type': task_type,
                'status': 'completed',
                'execution_time': time.time() - start_time,
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
        for op in payload.get('operations', []):
            operation = self._DATA_OPERATIONS.get(op)
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

    # ---- control / inspection --------------------------------------------

    def stop(self):
        self.running = False

    def get_task_history(self):
        return self.completed_tasks[-HISTORY_LIMIT:]


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
