import os
import subprocess
import sys
import time
from datetime import datetime


class SystemMonitor:
    # Command prefixes for the built-in checks; output is redirected to a log file.
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

    def build_command(self, check_type, custom_command, log_file):
        """Build the shell command that writes the check output to log_file."""
        command = self.CHECK_COMMANDS.get(check_type)
        if command is None:
            command = f'{custom_command}'
        return f'{command} > {log_file}'

    def execute_system_check(self, check_type, custom_command=None):
        self.validate_check_type(check_type)
        log_file = os.path.join(self.log_dir, self.generate_log_filename(check_type))
        cmd = self.build_command(check_type, custom_command, log_file)
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


def handle_run_check(monitor):
    check_type = input('Check type (cpu/memory/disk/network/custom): ')
    custom_cmd = None
    if check_type == 'custom':
        custom_cmd = input('Enter custom command to execute: ')
    try:
        if custom_cmd is None:
            monitor.execute_system_check(check_type)
        else:
            monitor.execute_system_check(check_type, custom_cmd)
    except Exception as e:
        print(f'Error: {e}')


def handle_list_logs(monitor):
    logs = monitor.list_available_logs()
    print('Available logs:')
    for log in logs:
        print(f'- {log}')


def handle_view_log(monitor):
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
            handle_run_check(monitor)
        elif choice == '2':
            handle_list_logs(monitor)
        elif choice == '3':
            handle_view_log(monitor)
        elif choice == '4':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
