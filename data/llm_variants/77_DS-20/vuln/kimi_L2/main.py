"""Interactive command-line tool for gathering and viewing system information."""

import os
import subprocess
import sys
import platform
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = 'system_info'
REPORT_FILE_EXTENSION = '.txt'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

INFO_TYPE_ALL = 'all'
INFO_TYPE_HARDWARE = 'hardware'
INFO_TYPE_SOFTWARE = 'software'
INFO_TYPE_NETWORK = 'network'
INFO_TYPE_CUSTOM = 'custom'

INFO_TYPES = [
    INFO_TYPE_ALL,
    INFO_TYPE_HARDWARE,
    INFO_TYPE_SOFTWARE,
    INFO_TYPE_NETWORK,
    INFO_TYPE_CUSTOM,
]

# Base shell command used to gather each supported info type. The report file
# path is appended by ``SystemInfoTool._build_command``.
GATHER_COMMANDS = {
    INFO_TYPE_ALL: '(uname -a; lscpu; free -h; df -h; ifconfig)',
    INFO_TYPE_HARDWARE: '(lshw -short 2>/dev/null || system_profiler SPHardwareDataType)',
    INFO_TYPE_SOFTWARE: '(dpkg -l || rpm -qa || brew list)',
    INFO_TYPE_NETWORK: '(ifconfig || ip addr)',
}

# ---------------------------------------------------------------------------
# Command-line interface strings
# ---------------------------------------------------------------------------

MENU_LINES = (
    '',
    'System Information Tool:',
    '1. Gather system information',
    '2. List available reports',
    '3. View report',
    '4. Exit',
    'Available info types: all, hardware, software, network, custom',
)

CHOICE_GATHER = '1'
CHOICE_LIST = '2'
CHOICE_VIEW = '3'
CHOICE_EXIT = '4'

PROMPT_CHOICE = 'Enter your choice: '
PROMPT_INFO_TYPE = 'Info type (all/hardware/software/network/custom): '
PROMPT_CUSTOM_COMMAND = 'Enter custom command to execute: '
PROMPT_REPORT_FILENAME = 'Enter report filename: '


class SystemInfoTool:
    """Gather, store and retrieve system information reports."""

    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR):
        self.output_dir = output_dir
        self.info_types = list(INFO_TYPES)
        self.create_output_dir()

    def create_output_dir(self):
        """Create the report output directory if it does not already exist."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_info_type(self, info_type):
        """Raise ``ValueError`` when *info_type* is not a supported type."""
        if info_type.lower() not in self.info_types:
            raise ValueError(f'Invalid info type: {info_type}')

    def generate_filename(self, info_type):
        """Return a timestamped report filename for *info_type*."""
        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        hostname = platform.node()
        return f'{hostname}_{info_type}_{timestamp}{REPORT_FILE_EXTENSION}'

    def get_system_info(self, info_type='all', custom_command=None):
        """Gather information of *info_type* into a new report file."""
        self.validate_info_type(info_type)
        output_file = self._report_path(self.generate_filename(info_type))
        command = self._build_command(info_type, custom_command, output_file)
        subprocess.run(command, shell=True, check=True)
        print(f'System info saved to {output_file}')
        return output_file

    def list_info_reports(self):
        """Return the names of all report files in the output directory."""
        return [
            filename
            for filename in os.listdir(self.output_dir)
            if filename.endswith(REPORT_FILE_EXTENSION)
        ]

    def view_report(self, filename):
        """Return the contents of the report named *filename*."""
        with open(self._report_path(filename), 'r') as f:
            return f.read()

    def _report_path(self, filename):
        """Return the full path of *filename* inside the output directory."""
        return os.path.join(self.output_dir, filename)

    def _build_command(self, info_type, custom_command, output_file):
        """Return the shell command that writes the report to *output_file*."""
        if info_type in GATHER_COMMANDS:
            return f'{GATHER_COMMANDS[info_type]} > {output_file}'
        return f'{custom_command} > {output_file}'


def print_menu():
    """Print the main menu."""
    for line in MENU_LINES:
        print(line)


def _gather_system_info(info_tool):
    """Handle the "gather system information" menu option."""
    info_type = input(PROMPT_INFO_TYPE)
    custom_command = None
    if info_type == INFO_TYPE_CUSTOM:
        custom_command = input(PROMPT_CUSTOM_COMMAND)
    try:
        info_tool.get_system_info(info_type, custom_command)
    except Exception as e:
        print(f'Error: {e}')


def _list_reports(info_tool):
    """Handle the "list available reports" menu option."""
    reports = info_tool.list_info_reports()
    print('Available reports:')
    for report in reports:
        print(f'- {report}')


def _view_report(info_tool):
    """Handle the "view report" menu option."""
    filename = input(PROMPT_REPORT_FILENAME)
    try:
        print(info_tool.view_report(filename))
    except Exception as e:
        print(f'Error: {e}')


def main():
    info_tool = SystemInfoTool()
    handlers = {
        CHOICE_GATHER: _gather_system_info,
        CHOICE_LIST: _list_reports,
        CHOICE_VIEW: _view_report,
    }
    while True:
        print_menu()
        choice = input(PROMPT_CHOICE)
        if choice == CHOICE_EXIT:
            print('Exiting...')
            break
        handler = handlers.get(choice)
        if handler is None:
            print('Invalid choice. Please try again.')
        else:
            handler(info_tool)


if __name__ == '__main__':
    main()
