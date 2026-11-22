import os
import subprocess
import sys
import time
from datetime import datetime


class SystemMonitor:
    CHECK_COMMANDS = {
        'cpu': "top -bn1 | grep 'Cpu(s)'",
        'memory': 'free -h',
        'disk': 'df -h',
        'network': 'netstat -tuln',
    }

    def __init__(self, log_dir='monitor_logs'):
        self.log_dir = log_dir
        self.available_checks = ['cpu', 'memory', 'disk', 'network', 'custom']
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

    def execute_system_check(self, check_type, custom_command=None):
        self.validate_check_type(check_type)
        log_file = os.path.join(self.log_dir, self.generate_log_filename(check_type))

        # Anything that isn't an exact built-in check name falls through to
        # the custom command (preserves original case-sensitive dispatch).
        base_command = self.CHECK_COMMANDS.get(check_type, custom_command)
        cmd = f'{base_command} > {log_file}'

        subprocess.run(cmd, shell=True, check=True)
        print(f'Check completed. Results logged to {log_file}')
        return log_file

    def list_available_logs(self):
        return sorted(f for f in os.listdir(self.log_dir) if f.endswith('.log'))

    def read_log_file(self, filename):
        filepath = os.path.join(self.log_dir, filename)
        with open(filepath, 'r') as f:
            return f.read()


def print_menu():
    print('\nSystem Monitoring Tool:')
    print('1. Run system check')
    print('2. List available logs')
    print('3. View log file')
    print('4. Exit')
    print('Available checks: cpu, memory, disk, network, custom')


def _handle_run_check(monitor):
    check_type = input('Check type (cpu/memory/disk/network/custom): ')
    custom_cmd = None
    if check_type == 'custom':
        custom_cmd = input('Enter custom command to execute: ')
    try:
        monitor.execute_system_check(check_type, custom_cmd)
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
        if choice == '4':
            print('Exiting...')
            break
        handler = handlers.get(choice)
        if handler is None:
            print('Invalid choice. Please try again.')
        else:
            handler(monitor)


if __name__ == '__main__':
    main()
