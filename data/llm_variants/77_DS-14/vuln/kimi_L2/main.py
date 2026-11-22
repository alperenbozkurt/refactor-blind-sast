import os
import subprocess
import sys
import platform
from dataclasses import dataclass
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = 'diagnostics'
OUTPUT_FILE_EXTENSION = '.txt'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

COMMAND_PING = 'ping'
COMMAND_TRACEROUTE = 'traceroute'
COMMAND_NSLOOKUP = 'nslookup'
SUPPORTED_COMMANDS = [COMMAND_PING, COMMAND_TRACEROUTE, COMMAND_NSLOOKUP]

WINDOWS_PLATFORM_NAME = 'windows'

MIN_PING_COUNT = 1
MAX_PING_COUNT = 20
DEFAULT_PING_COUNT = 4

MENU_OPTION_RUN = '1'
MENU_OPTION_LIST = '2'
MENU_OPTION_VIEW = '3'
MENU_OPTION_EXIT = '4'


@dataclass(frozen=True)
class PingConfig:
    """Configuration values for ping diagnostics."""

    min_count: int = MIN_PING_COUNT
    max_count: int = MAX_PING_COUNT
    default_count: int = DEFAULT_PING_COUNT


DEFAULT_PING_CONFIG = PingConfig()


# ---------------------------------------------------------------------------
# Platform and shell-command helpers
# ---------------------------------------------------------------------------

def _is_windows():
    """Return True when running on a Windows platform."""
    return platform.system().lower() == WINDOWS_PLATFORM_NAME


def _clamp_ping_count(count, config=DEFAULT_PING_CONFIG):
    """Coerce *count* to an int clamped to the configured ping bounds."""
    return max(config.min_count, min(int(count), config.max_count))


def _build_ping_command(target, output_file, count):
    count = _clamp_ping_count(count)
    count_flag = '-n' if _is_windows() else '-c'
    return f'ping {count_flag} {count} > {output_file}'


def _build_traceroute_command(target, output_file):
    program = 'tracert' if _is_windows() else 'traceroute'
    return f'{program} {target} > {output_file}'


def _build_nslookup_command(target, output_file):
    return f'nslookup {target} > {output_file}'


def _build_shell_command(command, target, output_file, count):
    """Build the shell command string for the requested diagnostic.

    Dispatch is case-sensitive; anything other than 'ping' or 'traceroute'
    falls back to nslookup, matching the historical behaviour.
    """
    if command == COMMAND_PING:
        return _build_ping_command(target, output_file, count)
    if command == COMMAND_TRACEROUTE:
        return _build_traceroute_command(target, output_file)
    return _build_nslookup_command(target, output_file)


# ---------------------------------------------------------------------------
# Diagnostic tool
# ---------------------------------------------------------------------------

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
        return f'{command}_{target}_{timestamp}{OUTPUT_FILE_EXTENSION}'

    def run_diagnostic(self, command, target, count=DEFAULT_PING_COUNT):
        self.validate_command(command)
        output_file = os.path.join(
            self.output_dir, self.generate_filename(command, target)
        )
        cmd = _build_shell_command(command, target, output_file, count)
        subprocess.run(cmd, shell=True, check=True)
        print(f'Diagnostic results saved to {output_file}')
        return output_file

    def list_diagnostics(self):
        return sorted(
            f for f in os.listdir(self.output_dir)
            if f.endswith(OUTPUT_FILE_EXTENSION)
        )

    def view_diagnostic(self, filename):
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'r') as f:
            return f.read()


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def print_menu():
    print('\nNetwork Diagnostic Tool:')
    print('1. Run diagnostic')
    print('2. List previous diagnostics')
    print('3. View diagnostic results')
    print('4. Exit')
    print(f"Available commands: {', '.join(SUPPORTED_COMMANDS)}")


def _prompt_run_diagnostic(diagnostic_tool):
    command = input('Diagnostic command (ping/traceroute/nslookup): ')
    target = input('Target host or domain: ')
    if command == COMMAND_PING:
        count = input(
            f'Ping count ({MIN_PING_COUNT}-{MAX_PING_COUNT}, '
            f'default {DEFAULT_PING_COUNT}): '
        ) or str(DEFAULT_PING_COUNT)
    try:
        if command == COMMAND_PING:
            diagnostic_tool.run_diagnostic(command, target, count)
        else:
            diagnostic_tool.run_diagnostic(command, target)
    except Exception as e:
        print(f'Error: {e}')


def _show_diagnostics_list(diagnostic_tool):
    diagnostics = diagnostic_tool.list_diagnostics()
    print('Available diagnostics:')
    for diag in diagnostics:
        print(f'- {diag}')


def _prompt_view_diagnostic(diagnostic_tool):
    filename = input('Enter diagnostic filename: ')
    try:
        print(diagnostic_tool.view_diagnostic(filename))
    except Exception as e:
        print(f'Error: {e}')


_MENU_HANDLERS = {
    MENU_OPTION_RUN: _prompt_run_diagnostic,
    MENU_OPTION_LIST: _show_diagnostics_list,
    MENU_OPTION_VIEW: _prompt_view_diagnostic,
}


def main():
    diagnostic_tool = NetworkDiagnosticTool()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == MENU_OPTION_EXIT:
            print('Exiting...')
            break
        handler = _MENU_HANDLERS.get(choice)
        if handler is None:
            print('Invalid choice. Please try again.')
        else:
            handler(diagnostic_tool)


if __name__ == '__main__':
    main()
