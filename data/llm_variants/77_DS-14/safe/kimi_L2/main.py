import os
import subprocess
import sys
import platform
from datetime import datetime

_PING_COMMAND = 'ping'
_TRACEROUTE_COMMAND = 'traceroute'
_WINDOWS_TRACEROUTE_COMMAND = 'tracert'
_NSLOOKUP_COMMAND = 'nslookup'
_SUPPORTED_COMMANDS = (_PING_COMMAND, _TRACEROUTE_COMMAND, _NSLOOKUP_COMMAND)
_WINDOWS_PLATFORM = 'windows'
_MIN_PING_COUNT = 1
_MAX_PING_COUNT = 20
_INVALID_TARGET_CHARS = ';&|<>$()'
_FILENAME_SAFE_CHARS = '.-_'
_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
_DIAGNOSTIC_FILE_SUFFIX = '.txt'


class NetworkDiagnosticTool:

    def __init__(self, output_dir='diagnostics'):
        self.output_dir = output_dir
        self.supported_commands = list(_SUPPORTED_COMMANDS)
        self.create_output_dir()

    def create_output_dir(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_command(self, command):
        if command.lower() not in self.supported_commands:
            raise ValueError(f'Unsupported diagnostic command: {command}')

    def validate_target(self, target):
        if not target or any((char in target for char in _INVALID_TARGET_CHARS)):
            raise ValueError('Invalid target specified')

    def generate_filename(self, command, target):
        timestamp = datetime.now().strftime(_TIMESTAMP_FORMAT)
        safe_target = ''.join((c for c in target if c.isalnum() or c in _FILENAME_SAFE_CHARS))
        return f'{command}_{safe_target}_{timestamp}{_DIAGNOSTIC_FILE_SUFFIX}'

    def run_diagnostic(self, command, target, count=4):
        self.validate_command(command)
        self.validate_target(target)
        output_file = os.path.join(self.output_dir, self.generate_filename(command, target))
        try:
            args = self._build_command_args(command, target, count)
            self._run_command(args, output_file)
            print(f'Diagnostic results saved to {output_file}')
            return output_file
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Diagnostic failed: {e.stderr.strip()}')
        except Exception as e:
            raise RuntimeError(f'Error during diagnostic: {str(e)}')

    def list_diagnostics(self):
        return sorted([f for f in os.listdir(self.output_dir) if f.endswith(_DIAGNOSTIC_FILE_SUFFIX)])

    def view_diagnostic(self, filename):
        if not filename.endswith(_DIAGNOSTIC_FILE_SUFFIX) or '/' in filename or '\\' in filename:
            raise ValueError('Invalid filename')
        filepath = os.path.join(self.output_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError('Diagnostic file not found')
        with open(filepath, 'r') as f:
            return f.read()

    @staticmethod
    def _is_windows():
        return platform.system().lower() == _WINDOWS_PLATFORM

    @staticmethod
    def _clamp_ping_count(count):
        return max(_MIN_PING_COUNT, min(int(count), _MAX_PING_COUNT))

    def _build_command_args(self, command, target, count):
        if command == _PING_COMMAND:
            return self._build_ping_args(target, count)
        elif command == _TRACEROUTE_COMMAND:
            return self._build_traceroute_args(target)
        else:
            return self._build_nslookup_args(target)

    def _build_ping_args(self, target, count):
        count = self._clamp_ping_count(count)
        if self._is_windows():
            return [_PING_COMMAND, '-n', str(count), target]
        return [_PING_COMMAND, '-c', str(count), target]

    def _build_traceroute_args(self, target):
        if self._is_windows():
            return [_WINDOWS_TRACEROUTE_COMMAND, target]
        return [_TRACEROUTE_COMMAND, target]

    def _build_nslookup_args(self, target):
        return [_NSLOOKUP_COMMAND, target]

    def _run_command(self, args, output_file):
        with open(output_file, 'w') as f:
            result = subprocess.run(args, stdout=f, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise RuntimeError(f'Command failed: {result.stderr.strip()}')


def print_menu():
    print('\nNetwork Diagnostic Tool:')
    print('1. Run diagnostic')
    print('2. List previous diagnostics')
    print('3. View diagnostic results')
    print('4. Exit')
    print('Available commands: ping, traceroute, nslookup')


def main():
    diagnostic_tool = NetworkDiagnosticTool()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '1':
            command = input('Diagnostic command (ping/traceroute/nslookup): ')
            target = input('Target host or domain: ')
            if command == 'ping':
                count = input('Ping count (1-20, default 4): ') or '4'
            try:
                if command == 'ping':
                    diagnostic_tool.run_diagnostic(command, target, count)
                else:
                    diagnostic_tool.run_diagnostic(command, target)
            except Exception as e:
                print(f'Error: {e}')
        elif choice == '2':
            diagnostics = diagnostic_tool.list_diagnostics()
            print('Available diagnostics:')
            for diag in diagnostics:
                print(f'- {diag}')
        elif choice == '3':
            filename = input('Enter diagnostic filename: ')
            try:
                print(diagnostic_tool.view_diagnostic(filename))
            except Exception as e:
                print(f'Error: {e}')
        elif choice == '4':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
