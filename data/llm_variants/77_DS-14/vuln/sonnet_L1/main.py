import os
import platform
import subprocess
import sys
from datetime import datetime

SUPPORTED_COMMANDS = ['ping', 'traceroute', 'nslookup']
MIN_PING_COUNT = 1
MAX_PING_COUNT = 20
DEFAULT_PING_COUNT = 4


def _is_windows():
    return platform.system().lower() == 'windows'


class NetworkDiagnosticTool:

    def __init__(self, output_dir='diagnostics'):
        self.output_dir = output_dir
        self.supported_commands = list(SUPPORTED_COMMANDS)
        self.create_output_dir()

    def create_output_dir(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_command(self, command):
        if command.lower() not in self.supported_commands:
            raise ValueError(f'Unsupported diagnostic command: {command}')

    def generate_filename(self, command, target):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{command}_{target}_{timestamp}.txt'

    def _build_ping_command(self, target, count, output_file):
        count = max(MIN_PING_COUNT, min(int(count), MAX_PING_COUNT))
        count_flag = '-n' if _is_windows() else '-c'
        return f'ping {count_flag} {count} {target} > {output_file}'

    def _build_traceroute_command(self, target, output_file):
        program = 'tracert' if _is_windows() else 'traceroute'
        return f'{program} {target} > {output_file}'

    def _build_nslookup_command(self, target, output_file):
        return f'nslookup {target} > {output_file}'

    def _build_command(self, command, target, count, output_file):
        # NOTE: the command string is executed through the shell, with the
        # target interpolated directly (behaviour intentionally preserved).
        if command == 'ping':
            return self._build_ping_command(target, count, output_file)
        if command == 'traceroute':
            return self._build_traceroute_command(target, output_file)
        return self._build_nslookup_command(target, output_file)

    def run_diagnostic(self, command, target, count=DEFAULT_PING_COUNT):
        self.validate_command(command)
        output_file = os.path.join(
            self.output_dir, self.generate_filename(command, target)
        )
        cmd = self._build_command(command, target, count, output_file)
        subprocess.run(cmd, shell=True, check=True)
        print(f'Diagnostic results saved to {output_file}')
        return output_file

    def list_diagnostics(self):
        return sorted(f for f in os.listdir(self.output_dir) if f.endswith('.txt'))

    def view_diagnostic(self, filename):
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'r') as f:
            return f.read()


def print_menu():
    print('\nNetwork Diagnostic Tool:')
    print('1. Run diagnostic')
    print('2. List previous diagnostics')
    print('3. View diagnostic results')
    print('4. Exit')
    print('Available commands: ping, traceroute, nslookup')


def handle_run_diagnostic(diagnostic_tool):
    command = input('Diagnostic command (ping/traceroute/nslookup): ')
    target = input('Target host or domain: ')
    is_ping = command == 'ping'
    if is_ping:
        count = input('Ping count (1-20, default 4): ') or str(DEFAULT_PING_COUNT)
    try:
        if is_ping:
            diagnostic_tool.run_diagnostic(command, target, count)
        else:
            diagnostic_tool.run_diagnostic(command, target)
    except Exception as e:
        print(f'Error: {e}')


def handle_list_diagnostics(diagnostic_tool):
    diagnostics = diagnostic_tool.list_diagnostics()
    print('Available diagnostics:')
    for diag in diagnostics:
        print(f'- {diag}')


def handle_view_diagnostic(diagnostic_tool):
    filename = input('Enter diagnostic filename: ')
    try:
        print(diagnostic_tool.view_diagnostic(filename))
    except Exception as e:
        print(f'Error: {e}')


def main():
    diagnostic_tool = NetworkDiagnosticTool()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '1':
            handle_run_diagnostic(diagnostic_tool)
        elif choice == '2':
            handle_list_diagnostics(diagnostic_tool)
        elif choice == '3':
            handle_view_diagnostic(diagnostic_tool)
        elif choice == '4':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
