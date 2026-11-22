"""Gather, store and view system-information reports."""

import os
import subprocess
import sys
import platform
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = 'system_info'

INFO_TYPE_ALL = 'all'
INFO_TYPE_HARDWARE = 'hardware'
INFO_TYPE_SOFTWARE = 'software'
INFO_TYPE_NETWORK = 'network'
INFO_TYPES = (INFO_TYPE_ALL, INFO_TYPE_HARDWARE, INFO_TYPE_SOFTWARE, INFO_TYPE_NETWORK)

REPORT_FILE_EXTENSION = '.txt'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

CHOICE_GATHER = '1'
CHOICE_LIST = '2'
CHOICE_VIEW = '3'
CHOICE_EXIT = '4'

PROMPT_CHOICE = 'Enter your choice: '
PROMPT_INFO_TYPE = 'Info type (all/hardware/software/network): '
PROMPT_REPORT_FILENAME = 'Enter report filename: '


class SystemInfoTool:
    """Collect system information into text reports and read them back."""

    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR):
        self.output_dir = output_dir
        self.info_types = list(INFO_TYPES)
        self.create_output_dir()

    def create_output_dir(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_info_type(self, info_type):
        if info_type.lower() not in self.info_types:
            raise ValueError(f'Invalid info type: {info_type}')

    def generate_filename(self, info_type):
        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        hostname = platform.node()
        return f'{hostname}_{info_type}_{timestamp}{REPORT_FILE_EXTENSION}'

    # -- command builders --------------------------------------------------

    @staticmethod
    def _all_commands():
        return [
            ['uname', '-a'],
            ['lscpu'],
            ['free', '-h'],
            ['df', '-h'],
            ['ifconfig'] if platform.system() != 'Windows' else ['ipconfig'],
        ]

    @staticmethod
    def _hardware_commands():
        if platform.system() != 'Darwin':
            return [['lshw', '-short']]
        return [['system_profiler', 'SPHardwareDataType']]

    @staticmethod
    def _software_commands():
        if platform.system() == 'Linux':
            commands = [['dpkg', '-l'] if os.path.exists('/usr/bin/dpkg') else ['rpm', '-qa']]
        elif platform.system() == 'Darwin':
            commands = [['brew', 'list']] if os.path.exists('/usr/local/bin/brew') else []
        return commands

    @staticmethod
    def _network_commands():
        if platform.system() != 'Windows':
            return [['ifconfig']]
        return [['ipconfig']]

    # -- report writing ----------------------------------------------------

    @staticmethod
    def _write_command_output(report_file, cmd, output):
        report_file.write(f"=== {' '.join(cmd)} ===\n")
        report_file.write(output)
        report_file.write('\n\n')

    def get_system_info(self, info_type=INFO_TYPE_ALL):
        self.validate_info_type(info_type)
        output_file = os.path.join(self.output_dir, self.generate_filename(info_type))
        try:
            with open(output_file, 'w') as f:
                if info_type == INFO_TYPE_ALL:
                    commands = self._all_commands()
                elif info_type == INFO_TYPE_HARDWARE:
                    commands = self._hardware_commands()
                elif info_type == INFO_TYPE_SOFTWARE:
                    commands = self._software_commands()
                elif info_type == INFO_TYPE_NETWORK:
                    commands = self._network_commands()
                for cmd in commands:
                    try:
                        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                        if result.returncode == 0:
                            self._write_command_output(f, cmd, result.stdout)
                    except Exception:
                        continue
            print(f'System info saved to {output_file}')
            return output_file
        except Exception as e:
            raise RuntimeError(f'Error gathering system info: {str(e)}')

    def list_info_reports(self):
        return [f for f in os.listdir(self.output_dir) if f.endswith(REPORT_FILE_EXTENSION)]

    @staticmethod
    def _is_valid_report_filename(filename):
        return (filename.endswith(REPORT_FILE_EXTENSION)
                and '/' not in filename
                and '\\' not in filename)

    def view_report(self, filename):
        if not self._is_valid_report_filename(filename):
            raise ValueError('Invalid filename')
        filepath = os.path.join(self.output_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError('Report file not found')
        with open(filepath, 'r') as f:
            return f.read()


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def print_menu():
    print('\nSystem Information Tool:')
    print('1. Gather system information')
    print('2. List available reports')
    print('3. View report')
    print('4. Exit')
    print(f"Available info types: {', '.join(SystemInfoTool().info_types)}")


def _handle_gather(info_tool):
    info_type = input(PROMPT_INFO_TYPE)
    try:
        info_tool.get_system_info(info_type)
    except Exception as e:
        print(f'Error: {e}')


def _handle_list(info_tool):
    reports = info_tool.list_info_reports()
    print('Available reports:')
    for report in reports:
        print(f'- {report}')


def _handle_view(info_tool):
    filename = input(PROMPT_REPORT_FILENAME)
    try:
        print(info_tool.view_report(filename))
    except Exception as e:
        print(f'Error: {e}')


def main():
    info_tool = SystemInfoTool()
    handlers = {
        CHOICE_GATHER: _handle_gather,
        CHOICE_LIST: _handle_list,
        CHOICE_VIEW: _handle_view,
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
