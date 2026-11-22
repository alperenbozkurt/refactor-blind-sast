import os
import subprocess
import sys
import platform
from datetime import datetime

DEFAULT_OUTPUT_DIR = 'system_info'
INFO_TYPES = ['all', 'hardware', 'software', 'network', 'custom']
CUSTOM_INFO_TYPE = 'custom'
REPORT_EXTENSION = '.txt'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

# Shell command bodies for each predefined info type. Anything not listed
# here (i.e. "custom") uses the user-provided command instead.
PREDEFINED_COMMANDS = {
    'all': '(uname -a; lscpu; free -h; df -h; ifconfig)',
    'hardware': '(lshw -short 2>/dev/null || system_profiler SPHardwareDataType)',
    'software': '(dpkg -l || rpm -qa || brew list)',
    'network': '(ifconfig || ip addr)',
}

MENU_GATHER = '1'
MENU_LIST = '2'
MENU_VIEW = '3'
MENU_EXIT = '4'

MENU_LINES = (
    '\nSystem Information Tool:',
    '1. Gather system information',
    '2. List available reports',
    '3. View report',
    '4. Exit',
    'Available info types: all, hardware, software, network, custom',
)


class SystemInfoTool:

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
        return f'{hostname}_{info_type}_{timestamp}{REPORT_EXTENSION}'

    @staticmethod
    def _build_command(info_type, custom_command, output_file):
        body = PREDEFINED_COMMANDS.get(info_type)
        if body is None:
            body = f'{custom_command}'
        return f'{body} > {output_file}'

    def get_system_info(self, info_type='all', custom_command=None):
        self.validate_info_type(info_type)
        output_file = os.path.join(self.output_dir, self.generate_filename(info_type))
        cmd = self._build_command(info_type, custom_command, output_file)
        subprocess.run(cmd, shell=True, check=True)
        print(f'System info saved to {output_file}')
        return output_file

    def list_info_reports(self):
        return [f for f in os.listdir(self.output_dir) if f.endswith(REPORT_EXTENSION)]

    def view_report(self, filename):
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'r') as f:
            return f.read()


def print_menu():
    for line in MENU_LINES:
        print(line)


def _gather_info(info_tool, info_type, *args):
    try:
        info_tool.get_system_info(info_type, *args)
    except Exception as e:
        print(f'Error: {e}')


def _handle_gather(info_tool):
    info_type = input('Info type (all/hardware/software/network/custom): ')
    if info_type == CUSTOM_INFO_TYPE:
        custom_cmd = input('Enter custom command to execute: ')
        _gather_info(info_tool, info_type, custom_cmd)
    else:
        _gather_info(info_tool, info_type)


def _handle_list(info_tool):
    reports = info_tool.list_info_reports()
    print('Available reports:')
    for report in reports:
        print(f'- {report}')


def _handle_view(info_tool):
    filename = input('Enter report filename: ')
    try:
        print(info_tool.view_report(filename))
    except Exception as e:
        print(f'Error: {e}')


def main():
    info_tool = SystemInfoTool()
    handlers = {
        MENU_GATHER: _handle_gather,
        MENU_LIST: _handle_list,
        MENU_VIEW: _handle_view,
    }
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == MENU_EXIT:
            print('Exiting...')
            break
        handler = handlers.get(choice)
        if handler is None:
            print('Invalid choice. Please try again.')
        else:
            handler(info_tool)


if __name__ == '__main__':
    main()
