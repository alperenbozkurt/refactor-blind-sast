"""Interactive network diagnostic tool.

Runs ping, traceroute, or nslookup against a user-supplied target and
stores the captured output in timestamped text files on disk.
"""

import os
import platform
import subprocess
import sys  # noqa: F401  (kept: 'sys' remains part of this module's namespace)
from datetime import datetime

# Shell metacharacters that must never appear in a diagnostic target.
_FORBIDDEN_TARGET_CHARS = ';&|<>$()'

# Non-alphanumeric characters that are safe to keep in generated filenames.
_SAFE_FILENAME_CHARS = '.-_'

# Allowed range for the number of ping requests per diagnostic run.
_MIN_PING_COUNT = 1
_MAX_PING_COUNT = 20


class NetworkDiagnosticTool:
    """Run network diagnostics and persist their output to text files."""

    def __init__(self, output_dir='diagnostics'):
        self.output_dir = output_dir
        self.supported_commands = ['ping', 'traceroute', 'nslookup']
        self.create_output_dir()

    def create_output_dir(self):
        """Create the output directory if it does not exist yet."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_command(self, command):
        """Raise ValueError unless the command is supported."""
        if command.lower() not in self.supported_commands:
            raise ValueError(f'Unsupported diagnostic command: {command}')

    def validate_target(self, target):
        """Raise ValueError for empty targets or shell metacharacters."""
        contains_forbidden_char = any(
            char in target for char in _FORBIDDEN_TARGET_CHARS
        )
        if not target or contains_forbidden_char:
            raise ValueError('Invalid target specified')

    def generate_filename(self, command, target):
        """Build a timestamped, filesystem-safe output filename."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_target = ''.join(
            char
            for char in target
            if char.isalnum() or char in _SAFE_FILENAME_CHARS
        )
        return f'{command}_{safe_target}_{timestamp}.txt'

    def run_diagnostic(self, command, target, count=4):
        """Run a diagnostic command and save its output to a file."""
        self.validate_command(command)
        self.validate_target(target)
        output_file = os.path.join(
            self.output_dir, self.generate_filename(command, target)
        )
        try:
            args = self._build_args(command, target, count)
            self._execute(args, output_file)
            print(f'Diagnostic results saved to {output_file}')
            return output_file
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Diagnostic failed: {e.stderr.strip()}')
        except Exception as e:
            raise RuntimeError(f'Error during diagnostic: {str(e)}')

    def _build_args(self, command, target, count):
        """Return the platform-specific argument list for the command."""
        if command == 'ping':
            return self._build_ping_args(target, count)
        if command == 'traceroute':
            return self._build_traceroute_args(target)
        return ['nslookup', target]

    def _build_ping_args(self, target, count):
        count = self._clamp_count(count)
        count_flag = '-n' if self._is_windows() else '-c'
        return ['ping', count_flag, str(count), target]

    def _build_traceroute_args(self, target):
        executable = 'tracert' if self._is_windows() else 'traceroute'
        return [executable, target]

    @staticmethod
    def _clamp_count(count):
        """Coerce count to an int clamped to the allowed range."""
        return max(_MIN_PING_COUNT, min(int(count), _MAX_PING_COUNT))

    @staticmethod
    def _is_windows():
        return platform.system().lower() == 'windows'

    def _execute(self, args, output_file):
        """Run the command, streaming stdout into the output file."""
        with open(output_file, 'w') as f:
            result = subprocess.run(
                args, stdout=f, stderr=subprocess.PIPE, text=True
            )
        if result.returncode != 0:
            raise RuntimeError(f'Command failed: {result.stderr.strip()}')

    def list_diagnostics(self):
        """Return the sorted names of all saved diagnostic files."""
        return sorted(
            name
            for name in os.listdir(self.output_dir)
            if name.endswith('.txt')
        )

    def view_diagnostic(self, filename):
        """Return the contents of a previously saved diagnostic file."""
        self._validate_filename(filename)
        filepath = os.path.join(self.output_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError('Diagnostic file not found')
        with open(filepath, 'r') as f:
            return f.read()

    @staticmethod
    def _validate_filename(filename):
        """Reject anything but a plain .txt name inside the output dir."""
        if (
            not filename.endswith('.txt')
            or '/' in filename
            or '\\' in filename
        ):
            raise ValueError('Invalid filename')


def print_menu():
    """Print the main menu."""
    print('\nNetwork Diagnostic Tool:')
    print('1. Run diagnostic')
    print('2. List previous diagnostics')
    print('3. View diagnostic results')
    print('4. Exit')
    print('Available commands: ping, traceroute, nslookup')


def _handle_run_diagnostic(diagnostic_tool):
    """Prompt for parameters and run a diagnostic."""
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


def _handle_list_diagnostics(diagnostic_tool):
    """Print the names of all saved diagnostic files."""
    diagnostics = diagnostic_tool.list_diagnostics()
    print('Available diagnostics:')
    for diag in diagnostics:
        print(f'- {diag}')


def _handle_view_diagnostic(diagnostic_tool):
    """Prompt for a filename and print its contents."""
    filename = input('Enter diagnostic filename: ')
    try:
        print(diagnostic_tool.view_diagnostic(filename))
    except Exception as e:
        print(f'Error: {e}')


def main():
    """Run the interactive command-line menu loop."""
    diagnostic_tool = NetworkDiagnosticTool()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '1':
            _handle_run_diagnostic(diagnostic_tool)
        elif choice == '2':
            _handle_list_diagnostics(diagnostic_tool)
        elif choice == '3':
            _handle_view_diagnostic(diagnostic_tool)
        elif choice == '4':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
