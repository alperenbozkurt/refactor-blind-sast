import os
import subprocess
import sys
import time
from datetime import datetime


class SystemMonitor:
    """Run system-monitoring commands and store their output in log files."""

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
        """Create the log directory if it does not already exist."""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

    def validate_check_type(self, check_type):
        """Raise ValueError if the given check type is not supported."""
        if check_type.lower() not in self.available_checks:
            raise ValueError(f'Invalid check type: {check_type}')

    def generate_log_filename(self, check_type):
        """Build a timestamped log filename for the given check type."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{check_type}_check_{timestamp}.log'

    def execute_system_check(self, check_type, custom_command=None):
        """Run the requested check and redirect its output to a log file."""
        self.validate_check_type(check_type)
        log_file = os.path.join(self.log_dir, self.generate_log_filename(check_type))
        base_command = self.CHECK_COMMANDS.get(check_type, custom_command)
        subprocess.run(f'{base_command} > {log_file}', shell=True, check=True)
        print(f'Check completed. Results logged to {log_file}')
        return log_file

    def list_available_logs(self):
        """Return the sorted names of all log files in the log directory."""
        return sorted(f for f in os.listdir(self.log_dir) if f.endswith('.log'))

    def read_log_file(self, filename):
        """Return the contents of the given log file from the log directory."""
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


def _run_system_check(monitor):
    check_type = input('Check type (cpu/memory/disk/network/custom): ')
    custom_command = None
    if check_type == 'custom':
        custom_command = input('Enter custom command to execute: ')
    try:
        monitor.execute_system_check(check_type, custom_command)
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
    menu_actions = {
        '1': _run_system_check,
        '2': _list_available_logs,
        '3': _view_log_file,
    }
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '4':
            print('Exiting...')
            break
        action = menu_actions.get(choice)
        if action is None:
            print('Invalid choice. Please try again.')
        else:
            action(monitor)


if __name__ == '__main__':
    main()
