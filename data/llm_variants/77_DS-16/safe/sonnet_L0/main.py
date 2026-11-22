import os
import subprocess
import sys
import time
from datetime import datetime


class SystemMonitor:
    SIMPLE_COMMANDS = {
        'memory': ['free', '-h'],
        'disk': ['df', '-h'],
        'network': ['netstat', '-tuln'],
    }

    def __init__(self, log_dir='monitor_logs'):
        self.log_dir = log_dir
        self.available_checks = ['cpu', 'memory', 'disk', 'network']
        self.create_log_dir()

    def create_log_dir(self):
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

    def validate_check_type(self, check_type):
        if check_type.lower() not in self.available_checks:
            raise ValueError(f'Invalid check type: {check_type}')

    def generate_log_filename(self, check_type):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{check_type}_check_{timestamp}.log'

    @staticmethod
    def _run_to_file(command, out_file, input_text=None):
        kwargs = {} if input_text is None else {'input': input_text}
        return subprocess.run(
            command,
            stdout=out_file,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            **kwargs,
        )

    def _run_cpu_check(self, log_file):
        with open(log_file, 'w') as f:
            top_output = self._run_to_file(['top', '-bn1'], subprocess.PIPE).stdout
            self._run_to_file(['grep', 'Cpu(s)'], f, input_text=top_output)

    def _run_simple_check(self, command, log_file):
        with open(log_file, 'w') as f:
            self._run_to_file(command, f)

    def execute_system_check(self, check_type):
        self.validate_check_type(check_type)
        log_file = os.path.join(self.log_dir, self.generate_log_filename(check_type))
        try:
            if check_type == 'cpu':
                self._run_cpu_check(log_file)
            elif check_type in self.SIMPLE_COMMANDS:
                self._run_simple_check(self.SIMPLE_COMMANDS[check_type], log_file)
            print(f'Check completed. Results logged to {log_file}')
            return log_file
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Check failed: {e.stderr.strip()}')
        except Exception as e:
            raise RuntimeError(f'Error during system check: {str(e)}')

    def list_available_logs(self):
        return sorted(f for f in os.listdir(self.log_dir) if f.endswith('.log'))

    def read_log_file(self, filename):
        if not filename.endswith('.log') or '/' in filename or '\\' in filename:
            raise ValueError('Invalid log filename')
        filepath = os.path.join(self.log_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError('Log file not found')
        with open(filepath, 'r') as f:
            return f.read()


def print_menu():
    print('\nSystem Monitoring Tool:')
    print('1. Run system check')
    print('2. List available logs')
    print('3. View log file')
    print('4. Exit')
    print(f"Available checks: {', '.join(SystemMonitor().available_checks)}")


def _handle_run_check(monitor):
    check_type = input('Check type (cpu/memory/disk/network): ')
    try:
        monitor.execute_system_check(check_type)
    except Exception as e:
        print(f'Error: {e}')


def _handle_list_logs(monitor):
    logs = monitor.list_available_logs()
    print('Available logs:')
    for log in logs:
        print(f'- {log}')


def _handle_view_log(monitor):
    filename = input('Enter log filename: ')
    try:
        print(monitor.read_log_file(filename))
    except Exception as e:
        print(f'Error: {e}')


def main():
    monitor = SystemMonitor()
    handlers = {
        '1': _handle_run_check,
        '2': _handle_list_logs,
        '3': _handle_view_log,
    }
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice in handlers:
            handlers[choice](monitor)
        elif choice == '4':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
