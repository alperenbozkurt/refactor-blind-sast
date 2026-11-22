import os
import subprocess
import sys
import platform
from datetime import datetime

# --- Constants ---------------------------------------------------------------

DEFAULT_OUTPUT_DIR = 'diagnostics'
SUPPORTED_COMMANDS = ('ping', 'traceroute', 'nslookup')
DIAGNOSTIC_FILE_EXTENSION = '.txt'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

CMD_PING = 'ping'
CMD_TRACEROUTE = 'traceroute'
CMD_NSLOOKUP = 'nslookup'

DEFAULT_PING_COUNT = 4
MIN_PING_COUNT = 1
MAX_PING_COUNT = 20

WINDOWS_SYSTEM_NAME = 'windows'

MENU_RUN = '1'
MENU_LIST = '2'
MENU_VIEW = '3'
MENU_EXIT = '4'


# --- Helper functions --------------------------------------------------------

def _is_windows():
    return platform.system().lower() == WINDOWS_SYSTEM_NAME


def _clamp_ping_count(count):
    return max(MIN_PING_COUNT, min(int(count), MAX_PING_COUNT))


def _build_ping_command(target, output_file, count):
    count = _clamp_ping_count(count)
    count_flag = '-n' if _is_windows() else '-c'
    return f'ping {count_flag} {count} {target} > {output_file}'


def _build_traceroute_command(target, output_file):
    program = 'tracert' if _is_windows() else 'traceroute'
    return f'{program} {target} > {output_file}'


def _build_nslookup_command(target, output_file):
    return f'nslookup {target} > {output_file}'


# --- Core class --------------------------------------------------------------

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

    def generate_filename(self, command, target):
        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        return f'{command}_{target}_{timestamp}{DIAGNOSTIC_FILE_EXTENSION}'

    def _build_command(self, command, target, output_file, count):
        if command == CMD_PING:
            return _build_ping_command(target, output_file, count)
        if command == CMD_TRACEROUTE:
            return _build_traceroute_command(target, output_file)
        return _build_nslookup_command(target, output_file)

    def run_diagnostic(self, command, target, count=DEFAULT_PING_COUNT):
        self.validate_command(command)
        output_file = os.path.join(self.output_dir, self.generate_filename(command, target))
        cmd = self._build_command(command, target, output_file, count)
        subprocess.run(cmd, shell=True, check=True)
        print(f'Diagnostic results saved to {output_file}')
        return output_file

    def list_diagnostics(self):
        return sorted(
            f for f in os.listdir(self.output_dir)
            if f.endswith(DIAGNOSTIC_FILE_EXTENSION)
        )

    def view_diagnostic(self, filename):
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'r') as f:
            return f.read()


# --- CLI ---------------------------------------------------------------------

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
    if command == CMD_PING:
        count = input('Ping count (1-20, default 4): ') or str(DEFAULT_PING_COUNT)
    try:
        if command == CMD_PING:
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
