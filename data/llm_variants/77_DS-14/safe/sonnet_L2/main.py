import os
import subprocess
import sys
import platform
from datetime import datetime

DEFAULT_OUTPUT_DIR = 'diagnostics'
SUPPORTED_COMMANDS = ('ping', 'traceroute', 'nslookup')
FORBIDDEN_TARGET_CHARS = ';&|<>$()'
SAFE_FILENAME_EXTRA_CHARS = '.-_'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
DIAGNOSTIC_EXTENSION = '.txt'

PING_MIN_COUNT = 1
PING_MAX_COUNT = 20
PING_DEFAULT_COUNT = 4
PING_DEFAULT_COUNT_INPUT = str(PING_DEFAULT_COUNT)

WINDOWS_PLATFORM = 'windows'

MENU_RUN = '1'
MENU_LIST = '2'
MENU_VIEW = '3'
MENU_EXIT = '4'


def _is_windows():
    return platform.system().lower() == WINDOWS_PLATFORM


def _clamp_ping_count(count):
    return max(PING_MIN_COUNT, min(int(count), PING_MAX_COUNT))


class NetworkDiagnosticTool:

    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR):
        self.output_dir = output_dir
        self.supported_commands = list(SUPPORTED_COMMANDS)
        self.create_output_dir()

    def create_output_dir(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_command(self, command):
        if command.lower() not in self.supported_commands:
            raise ValueError(f'Unsupported diagnostic command: {command}')

    def validate_target(self, target):
        if not target or any((char in target for char in FORBIDDEN_TARGET_CHARS)):
            raise ValueError('Invalid target specified')

    def generate_filename(self, command, target):
        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        safe_target = ''.join(
            (c for c in target if c.isalnum() or c in SAFE_FILENAME_EXTRA_CHARS)
        )
        return f'{command}_{safe_target}_{timestamp}{DIAGNOSTIC_EXTENSION}'

    @staticmethod
    def _build_ping_args(target, count):
        count = _clamp_ping_count(count)
        count_flag = '-n' if _is_windows() else '-c'
        return ['ping', count_flag, str(count), target]

    @staticmethod
    def _build_traceroute_args(target):
        program = 'tracert' if _is_windows() else 'traceroute'
        return [program, target]

    @staticmethod
    def _build_nslookup_args(target):
        return ['nslookup', target]

    def _build_args(self, command, target, count):
        if command == 'ping':
            return self._build_ping_args(target, count)
        if command == 'traceroute':
            return self._build_traceroute_args(target)
        return self._build_nslookup_args(target)

    @staticmethod
    def _execute_to_file(args, output_file):
        with open(output_file, 'w') as f:
            return subprocess.run(args, stdout=f, stderr=subprocess.PIPE, text=True)

    def run_diagnostic(self, command, target, count=PING_DEFAULT_COUNT):
        self.validate_command(command)
        self.validate_target(target)
        output_file = os.path.join(self.output_dir, self.generate_filename(command, target))
        try:
            args = self._build_args(command, target, count)
            result = self._execute_to_file(args, output_file)
            if result.returncode != 0:
                raise RuntimeError(f'Command failed: {result.stderr.strip()}')
            print(f'Diagnostic results saved to {output_file}')
            return output_file
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Diagnostic failed: {e.stderr.strip()}')
        except Exception as e:
            raise RuntimeError(f'Error during diagnostic: {str(e)}')

    def list_diagnostics(self):
        return sorted(
            [f for f in os.listdir(self.output_dir) if f.endswith(DIAGNOSTIC_EXTENSION)]
        )

    @staticmethod
    def _is_valid_filename(filename):
        return filename.endswith(DIAGNOSTIC_EXTENSION) and '/' not in filename and '\\' not in filename

    def view_diagnostic(self, filename):
        if not self._is_valid_filename(filename):
            raise ValueError('Invalid filename')
        filepath = os.path.join(self.output_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError('Diagnostic file not found')
        with open(filepath, 'r') as f:
            return f.read()


def print_menu():
    print('\nNetwork Diagnostic Tool:')
    print('1. Run diagnostic')
    print('2. List previous diagnostics')
    print('3. View diagnostic results')
    print('4. Exit')
    print('Available commands: ping, traceroute, nslookup')


def _handle_run(diagnostic_tool):
    command = input('Diagnostic command (ping/traceroute/nslookup): ')
    target = input('Target host or domain: ')
    if command == 'ping':
        count = input('Ping count (1-20, default 4): ') or PING_DEFAULT_COUNT_INPUT
    try:
        if command == 'ping':
            diagnostic_tool.run_diagnostic(command, target, count)
        else:
            diagnostic_tool.run_diagnostic(command, target)
    except Exception as e:
        print(f'Error: {e}')


def _handle_list(diagnostic_tool):
    diagnostics = diagnostic_tool.list_diagnostics()
    print('Available diagnostics:')
    for diag in diagnostics:
        print(f'- {diag}')


def _handle_view(diagnostic_tool):
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
        if choice == MENU_RUN:
            _handle_run(diagnostic_tool)
        elif choice == MENU_LIST:
            _handle_list(diagnostic_tool)
        elif choice == MENU_VIEW:
            _handle_view(diagnostic_tool)
        elif choice == MENU_EXIT:
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
