"""System monitoring tool.

Runs system checks (CPU, memory, disk, network), stores the results in
timestamped log files and provides a simple interactive CLI.

``sys`` and ``time`` are kept as module-level names for compatibility with
the previous version of this module.
"""

import os
import subprocess
import sys
import time
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DEFAULT_LOG_DIR = 'monitor_logs'
LOG_FILE_EXTENSION = '.log'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

CPU_CHECK = 'cpu'
MEMORY_CHECK = 'memory'
DISK_CHECK = 'disk'
NETWORK_CHECK = 'network'
AVAILABLE_CHECKS = (CPU_CHECK, MEMORY_CHECK, DISK_CHECK, NETWORK_CHECK)

CPU_SNAPSHOT_COMMAND = ['top', '-bn1']
CPU_FILTER_COMMAND = ['grep', 'Cpu(s)']

# Checks that consist of running a single command straight into the log file.
CHECK_COMMANDS = {
    MEMORY_CHECK: ['free', '-h'],
    DISK_CHECK: ['df', '-h'],
    NETWORK_CHECK: ['netstat', '-tuln'],
}

CHOICE_RUN_CHECK = '1'
CHOICE_LIST_LOGS = '2'
CHOICE_VIEW_LOG = '3'
CHOICE_EXIT = '4'


class SystemMonitor:
    """Runs system checks and stores their output in timestamped log files."""

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
        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        return f'{check_type}_check_{timestamp}.log'

    def execute_system_check(self, check_type):
        self.validate_check_type(check_type)
        log_file = os.path.join(self.log_dir, self.generate_log_filename(check_type))
        try:
            self._perform_check(check_type, log_file)
            print(f'Check completed. Results logged to {log_file}')
            return log_file
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Check failed: {e.stderr.strip()}')
        except Exception as e:
            raise RuntimeError(f'Error during system check: {str(e)}')

    def list_available_logs(self):
        return sorted(
            f for f in os.listdir(self.log_dir)
            if f.endswith(LOG_FILE_EXTENSION)
        )

    def read_log_file(self, filename):
        if (not filename.endswith(LOG_FILE_EXTENSION)
                or '/' in filename or '\\' in filename):
            raise ValueError('Invalid log filename')
        filepath = os.path.join(self.log_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError('Log file not found')
        with open(filepath, 'r') as f:
            return f.read()

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _perform_check(self, check_type, log_file):
        """Run the requested check, writing its output to ``log_file``."""
        if check_type == CPU_CHECK:
            with open(log_file, 'w') as output_file:
                self._run_cpu_check(output_file)
        elif check_type in CHECK_COMMANDS:
            with open(log_file, 'w') as output_file:
                self._run_command(CHECK_COMMANDS[check_type], output_file)

    def _run_cpu_check(self, output_file):
        subprocess.run(
            CPU_SNAPSHOT_COMMAND,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        ).stdout
        top_output = subprocess.run(
            CPU_SNAPSHOT_COMMAND,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        ).stdout
        subprocess.run(
            CPU_FILTER_COMMAND,
            input=top_output,
            stdout=output_file,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )

    def _run_command(self, command, output_file):
        subprocess.run(
            command,
            stdout=output_file,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )


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
        if choice == CHOICE_RUN_CHECK:
            _handle_run_check(monitor)
        elif choice == CHOICE_LIST_LOGS:
            _handle_list_logs(monitor)
        elif choice == CHOICE_VIEW_LOG:
            _handle_view_log(monitor)
        elif choice == CHOICE_EXIT:
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
