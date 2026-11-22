import os
import subprocess
import sys
import time
from datetime import datetime

DEFAULT_LOG_DIR = 'monitor_logs'
AVAILABLE_CHECKS = ('cpu', 'memory', 'disk', 'network')
LOG_EXTENSION = '.log'
LOG_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

CPU_TOP_COMMAND = ['top', '-bn1']
CPU_FILTER_COMMAND = ['grep', 'Cpu(s)']

# Simple checks: the command's stdout is written straight to the log file.
SIMPLE_CHECK_COMMANDS = {
    'memory': ['free', '-h'],
    'disk': ['df', '-h'],
    'network': ['netstat', '-tuln'],
}

MENU_RUN_CHECK = '1'
MENU_LIST_LOGS = '2'
MENU_VIEW_LOG = '3'
MENU_EXIT = '4'


def _run_command(command, stdout, input_text=None):
    """Run a command capturing stderr, in text mode, raising on failure."""
    return subprocess.run(
        command,
        input=input_text,
        stdout=stdout,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )


def _is_safe_log_filename(filename):
    """Return True if the name is a plain log filename (no path separators)."""
    if not filename.endswith(LOG_EXTENSION):
        return False
    return '/' not in filename and '\\' not in filename


class SystemMonitor:

    def __init__(self, log_dir=DEFAULT_LOG_DIR):
        self.log_dir = log_dir
        self.available_checks = list(AVAILABLE_CHECKS)
        self.create_log_dir()

    def create_log_dir(self):
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

    def validate_check_type(self, check_type):
        if check_type.lower() not in self.available_checks:
            raise ValueError(f'Invalid check type: {check_type}')

    def generate_log_filename(self, check_type):
        timestamp = datetime.now().strftime(LOG_TIMESTAMP_FORMAT)
        return f'{check_type}_check_{timestamp}.log'

    def _run_cpu_check(self, log_handle):
        # The first invocation's output is discarded (kept for identical behaviour).
        _run_command(CPU_TOP_COMMAND, subprocess.PIPE)
        top_output = _run_command(CPU_TOP_COMMAND, subprocess.PIPE).stdout
        _run_command(CPU_FILTER_COMMAND, log_handle, input_text=top_output)

    def _run_simple_check(self, command, log_handle):
        _run_command(command, log_handle)

    def _write_check_output(self, check_type, log_file):
        if check_type == 'cpu':
            with open(log_file, 'w') as f:
                self._run_cpu_check(f)
        elif check_type in SIMPLE_CHECK_COMMANDS:
            with open(log_file, 'w') as f:
                self._run_simple_check(SIMPLE_CHECK_COMMANDS[check_type], f)

    def execute_system_check(self, check_type):
        self.validate_check_type(check_type)
        log_file = os.path.join(self.log_dir, self.generate_log_filename(check_type))
        try:
            self._write_check_output(check_type, log_file)
            print(f'Check completed. Results logged to {log_file}')
            return log_file
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Check failed: {e.stderr.strip()}')
        except Exception as e:
            raise RuntimeError(f'Error during system check: {str(e)}')

    def list_available_logs(self):
        return sorted([f for f in os.listdir(self.log_dir) if f.endswith(LOG_EXTENSION)])

    def read_log_file(self, filename):
        if not _is_safe_log_filename(filename):
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
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == MENU_RUN_CHECK:
            _handle_run_check(monitor)
        elif choice == MENU_LIST_LOGS:
            _handle_list_logs(monitor)
        elif choice == MENU_VIEW_LOG:
            _handle_view_log(monitor)
        elif choice == MENU_EXIT:
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
