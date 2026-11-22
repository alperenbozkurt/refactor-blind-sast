import os
import subprocess
import sys  # noqa: F401  (kept to preserve module-level names)
import time  # noqa: F401  (kept to preserve module-level names)
from datetime import datetime

DEFAULT_LOG_DIR = 'monitor_logs'
LOG_EXTENSION = '.log'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
CUSTOM_CHECK = 'custom'
AVAILABLE_CHECKS = ('cpu', 'memory', 'disk', 'network', CUSTOM_CHECK)

# Command templates for built-in checks; "{log_file}" is the output redirect target.
CHECK_COMMAND_TEMPLATES = {
    'cpu': "top -bn1 | grep 'Cpu(s)' > {log_file}",
    'memory': 'free -h > {log_file}',
    'disk': 'df -h > {log_file}',
    'network': 'netstat -tuln > {log_file}',
}
CUSTOM_COMMAND_TEMPLATE = '{command} > {log_file}'

MENU_RUN_CHECK = '1'
MENU_LIST_LOGS = '2'
MENU_VIEW_LOG = '3'
MENU_EXIT = '4'

MENU_LINES = (
    '\nSystem Monitoring Tool:',
    '1. Run system check',
    '2. List available logs',
    '3. View log file',
    '4. Exit',
    'Available checks: cpu, memory, disk, network, custom',
)


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
        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        return f'{check_type}_check_{timestamp}.log'

    def _build_log_path(self, check_type):
        return os.path.join(self.log_dir, self.generate_log_filename(check_type))

    @staticmethod
    def _build_command(check_type, log_file, custom_command):
        template = CHECK_COMMAND_TEMPLATES.get(check_type)
        if template is not None:
            return template.format(log_file=log_file)
        return CUSTOM_COMMAND_TEMPLATE.format(command=custom_command, log_file=log_file)

    @staticmethod
    def _run_command(cmd):
        subprocess.run(cmd, shell=True, check=True)

    def execute_system_check(self, check_type, custom_command=None):
        self.validate_check_type(check_type)
        log_file = self._build_log_path(check_type)
        cmd = self._build_command(check_type, log_file, custom_command)
        self._run_command(cmd)
        print(f'Check completed. Results logged to {log_file}')
        return log_file

    def list_available_logs(self):
        return sorted([f for f in os.listdir(self.log_dir) if f.endswith(LOG_EXTENSION)])

    def read_log_file(self, filename):
        filepath = os.path.join(self.log_dir, filename)
        with open(filepath, 'r') as f:
            return f.read()


def print_menu():
    for line in MENU_LINES:
        print(line)


def _handle_run_check(monitor):
    check_type = input('Check type (cpu/memory/disk/network/custom): ')
    if check_type == CUSTOM_CHECK:
        custom_cmd = input('Enter custom command to execute: ')
        args = (check_type, custom_cmd)
    else:
        args = (check_type,)
    try:
        monitor.execute_system_check(*args)
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
        MENU_RUN_CHECK: _handle_run_check,
        MENU_LIST_LOGS: _handle_list_logs,
        MENU_VIEW_LOG: _handle_view_log,
    }
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == MENU_EXIT:
            print('Exiting...')
            break
        handler = handlers.get(choice)
        if handler is None:
            print('Invalid choice. Please try again.')
        else:
            handler(monitor)


if __name__ == '__main__':
    main()
