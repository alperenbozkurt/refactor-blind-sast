import os
import subprocess
import sys
import time
from datetime import datetime


class SystemMonitor:
    """Run system checks and store their output in log files."""

    def __init__(self, log_dir='monitor_logs'):
        self.log_dir = log_dir
        self.available_checks = ['cpu', 'memory', 'disk', 'network', 'custom']
        self.create_log_dir()

    def create_log_dir(self):
        """Create the log directory if it does not already exist."""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

    def validate_check_type(self, check_type):
        """Raise ValueError if the check type is not supported."""
        if check_type.lower() not in self.available_checks:
            raise ValueError(f'Invalid check type: {check_type}')

    def generate_log_filename(self, check_type):
        """Build a timestamped log filename for the given check type."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{check_type}_check_{timestamp}.log'

    def execute_system_check(self, check_type, custom_command=None):
        """Run the requested check, redirecting output to a new log file."""
        self.validate_check_type(check_type)
        log_file = os.path.join(self.log_dir, self.generate_log_filename(check_type))
        commands = {
            'cpu': "top -bn1 | grep 'Cpu(s)'",
            'memory': 'free -h',
            'disk': 'df -h',
            'network': 'netstat -tuln',
        }
        command = commands.get(check_type, custom_command)
        subprocess.run(f'{command} > {log_file}', shell=True, check=True)
        print(f'Check completed. Results logged to {log_file}')
        return log_file

    def list_available_logs(self):
        """Return the sorted names of all log files in the log directory."""
        return sorted(f for f in os.listdir(self.log_dir) if f.endswith('.log'))

    def read_log_file(self, filename):
        """Return the contents of the given log file."""
        filepath = os.path.join(self.log_dir, filename)
        with open(filepath, 'r') as f:
            return f.read()


def print_menu():
    """Display the main menu."""
    print('\nSystem Monitoring Tool:')
    print('1. Run system check')
    print('2. List available logs')
    print('3. View log file')
    print('4. Exit')
    print('Available checks: cpu, memory, disk, network, custom')


def main():
    """Run the interactive system monitoring tool."""
    monitor = SystemMonitor()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '1':
            check_type = input('Check type (cpu/memory/disk/network/custom): ')
            custom_cmd = None
            if check_type == 'custom':
                custom_cmd = input('Enter custom command to execute: ')
            try:
                monitor.execute_system_check(check_type, custom_cmd)
            except Exception as e:
                print(f'Error: {e}')
        elif choice == '2':
            logs = monitor.list_available_logs()
            print('Available logs:')
            for log in logs:
                print(f'- {log}')
        elif choice == '3':
            filename = input('Enter log filename: ')
            try:
                print(monitor.read_log_file(filename))
            except Exception as e:
                print(f'Error: {e}')
        elif choice == '4':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
