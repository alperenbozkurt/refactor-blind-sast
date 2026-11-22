"""Interactive command-line system monitoring tool.

Runs simple system health checks (CPU, memory, disk, network) and stores
the results in timestamped log files.
"""

import os
import subprocess
import sys
import time
from datetime import datetime

# Commands used for the checks that simply write a command's output to a log.
_CHECK_COMMANDS = {
    'memory': ['free', '-h'],
    'disk': ['df', '-h'],
    'network': ['netstat', '-tuln'],
}

_TOP_COMMAND = ['top', '-bn1']
_CPU_FILTER_COMMAND = ['grep', 'Cpu(s)']


class SystemMonitor:
    """Runs system checks and manages the resulting log files."""

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

    def execute_system_check(self, check_type):
        self.validate_check_type(check_type)
        log_file = os.path.join(self.log_dir, self.generate_log_filename(check_type))
        try:
            if check_type == 'cpu':
                self._log_cpu_usage(log_file)
            elif check_type in _CHECK_COMMANDS:
                self._log_command_output(_CHECK_COMMANDS[check_type], log_file)
            print(f'Check completed. Results logged to {log_file}')
            return log_file
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Check failed: {e.stderr.strip()}')
        except Exception as e:
            raise RuntimeError(f'Error during system check: {str(e)}')

    def list_available_logs(self):
        return sorted(f for f in os.listdir(self.log_dir) if f.endswith('.log'))

    def read_log_file(self, filename):
        self._validate_log_filename(filename)
        filepath = os.path.join(self.log_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError('Log file not found')
        with open(filepath, 'r') as f:
            return f.read()

    def _log_command_output(self, command, log_file):
        """Run a command and write its standard output to the log file."""
        with open(log_file, 'w') as f:
            subprocess.run(command, stdout=f, stderr=subprocess.PIPE,
                           text=True, check=True)

    def _log_cpu_usage(self, log_file):
        """Write the CPU summary line from ``top`` to the log file."""
        with open(log_file, 'w') as f:
            self._capture_top_output()  # Original code ran top twice; output discarded.
            top_output = self._capture_top_output()
            subprocess.run(_CPU_FILTER_COMMAND, input=top_output, stdout=f,
                           stderr=subprocess.PIPE, text=True, check=True)

    def _capture_top_output(self):
        """Run ``top`` once in batch mode and return its standard output."""
        completed = subprocess.run(_TOP_COMMAND, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, check=True)
        return completed.stdout

    @staticmethod
    def _validate_log_filename(filename):
        if not filename.endswith('.log') or '/' in filename or '\\' in filename:
            raise ValueError('Invalid log filename')


def print_menu():
    print('\nSystem Monitoring Tool:')
    print('1. Run system check')
    print('2. List available logs')
    print('3. View log file')
    print('4. Exit')
    print(f"Available checks: {', '.join(SystemMonitor().available_checks)}")


def _run_system_check(monitor):
    check_type = input('Check type (cpu/memory/disk/network): ')
    try:
        monitor.execute_system_check(check_type)
    except Exception as e:
        print(f'Error: {e}')


def _list_available_logs(monitor):
    logs = monitor.list_available_logs()
    print('Available logs:')
    for log in logs:
        print(f'- {log}')


def _view_log_file(monitor):
    filename = input('Enter log filename: ')
    try:
        print(monitor.read_log_file(filename))
    except Exception as e:
        print(f'Error: {e}')


def main():
    monitor = SystemMonitor()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '1':
            _run_system_check(monitor)
        elif choice == '2':
            _list_available_logs(monitor)
        elif choice == '3':
            _view_log_file(monitor)
        elif choice == '4':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
