import os
import subprocess
import sys
import platform
from datetime import datetime


class NetworkDiagnosticTool:

    def __init__(self, output_dir='diagnostics'):
        self.output_dir = output_dir
        self.supported_commands = ['ping', 'traceroute', 'nslookup']
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

    @staticmethod
    def _is_windows():
        return platform.system().lower() == 'windows'

    def _build_command(self, command, target, count):
        """Build the argument list for the requested diagnostic."""
        is_windows = self._is_windows()
        if command == 'ping':
            count = max(1, min(int(count), 20))
            flag = '-n' if is_windows else '-c'
            return ['ping', flag, str(count), target]
        if command == 'traceroute':
            return ['tracert' if is_windows else 'traceroute', target]
        return ['nslookup', target]

    def run_diagnostic(self, command, target, count=4):
        self.validate_command(command)
        output_file = os.path.join(self.output_dir, self.generate_filename(command, target))
        args = self._build_command(command, target, count)
        # Arguments are passed as a list (no shell) so the target cannot inject commands.
        with open(output_file, 'w') as f:
            subprocess.run(args, stdout=f, check=True)
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


def _handle_run(tool):
    command = input('Diagnostic command (ping/traceroute/nslookup): ')
    target = input('Target host or domain: ')
    extra_args = ()
    if command == 'ping':
        extra_args = (input('Ping count (1-20, default 4): ') or '4',)
    try:
        tool.run_diagnostic(command, target, *extra_args)
    except Exception as e:
        print(f'Error: {e}')


def _handle_list(tool):
    print('Available diagnostics:')
    for diag in tool.list_diagnostics():
        print(f'- {diag}')


def _handle_view(tool):
    filename = input('Enter diagnostic filename: ')
    try:
        print(tool.view_diagnostic(filename))
    except Exception as e:
        print(f'Error: {e}')


def main():
    diagnostic_tool = NetworkDiagnosticTool()
    handlers = {
        '1': _handle_run,
        '2': _handle_list,
        '3': _handle_view,
    }
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '4':
            print('Exiting...')
            break
        handler = handlers.get(choice)
        if handler:
            handler(diagnostic_tool)
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
