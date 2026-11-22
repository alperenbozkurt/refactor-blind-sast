import os
import subprocess
import sys
import platform
from datetime import datetime

DEFAULT_OUTPUT_DIR = 'system_info'
INFO_TYPES = ['all', 'hardware', 'software', 'network']
REPORT_EXTENSION = '.txt'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

DPKG_PATH = '/usr/bin/dpkg'
BREW_PATH = '/usr/local/bin/brew'

SYSTEM_WINDOWS = 'Windows'
SYSTEM_DARWIN = 'Darwin'
SYSTEM_LINUX = 'Linux'

MENU_LINES = (
    '\nSystem Information Tool:',
    '1. Gather system information',
    '2. List available reports',
    '3. View report',
    '4. Exit',
)

if sys.version_info >= (3, 11):
    _UNASSIGNED_COMMANDS_MESSAGE = (
        "cannot access local variable 'commands' where it is not associated with a value"
    )
else:
    _UNASSIGNED_COMMANDS_MESSAGE = "local variable 'commands' referenced before assignment"


def _network_command():
    """Return the platform-specific network configuration command."""
    return ['ifconfig'] if platform.system() != SYSTEM_WINDOWS else ['ipconfig']


def _hardware_commands():
    return [['lshw', '-short'] if platform.system() != SYSTEM_DARWIN
            else ['system_profiler', 'SPHardwareDataType']]


def _software_commands():
    """Return software listing commands, or None if the platform is unsupported."""
    system = platform.system()
    if system == SYSTEM_LINUX:
        return [['dpkg', '-l'] if os.path.exists(DPKG_PATH) else ['rpm', '-qa']]
    if system == SYSTEM_DARWIN:
        return [['brew', 'list']] if os.path.exists(BREW_PATH) else []
    return None


def _all_commands():
    return [['uname', '-a'], ['lscpu'], ['free', '-h'], ['df', '-h'], _network_command()]


def _network_commands():
    return [_network_command()]


_COMMAND_BUILDERS = {
    'all': _all_commands,
    'hardware': _hardware_commands,
    'software': _software_commands,
    'network': _network_commands,
}


def _resolve_commands(info_type):
    """Return the command list for an info type, or None if none applies."""
    builder = _COMMAND_BUILDERS.get(info_type)
    return builder() if builder is not None else None


def _run_command(cmd):
    """Run a command and return its stdout on success, otherwise None."""
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except Exception:
        return None
    if result.returncode == 0:
        return result.stdout
    return None


def _write_command_section(f, cmd, output):
    f.write(f"=== {' '.join(cmd)} ===\n")
    f.write(output)
    f.write('\n\n')


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

    def get_system_info(self, info_type='all'):
        self.validate_info_type(info_type)
        output_file = os.path.join(self.output_dir, self.generate_filename(info_type))
        try:
            with open(output_file, 'w') as f:
                commands = _resolve_commands(info_type)
                if commands is None:
                    raise UnboundLocalError(_UNASSIGNED_COMMANDS_MESSAGE)
                for cmd in commands:
                    output = _run_command(cmd)
                    if output is not None:
                        _write_command_section(f, cmd, output)
            print(f'System info saved to {output_file}')
            return output_file
        except Exception as e:
            raise RuntimeError(f'Error gathering system info: {str(e)}')

    def list_info_reports(self):
        return [f for f in os.listdir(self.output_dir) if f.endswith(REPORT_EXTENSION)]

    @staticmethod
    def _is_valid_report_name(filename):
        return filename.endswith(REPORT_EXTENSION) and '/' not in filename and '\\' not in filename

    def view_report(self, filename):
        if not self._is_valid_report_name(filename):
            raise ValueError('Invalid filename')
        filepath = os.path.join(self.output_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError('Report file not found')
        with open(filepath, 'r') as f:
            return f.read()


def print_menu():
    for line in MENU_LINES:
        print(line)
    print(f"Available info types: {', '.join(SystemInfoTool().info_types)}")


def _handle_gather(info_tool):
    info_type = input('Info type (all/hardware/software/network): ')
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
    filename = input('Enter report filename: ')
    try:
        print(info_tool.view_report(filename))
    except Exception as e:
        print(f'Error: {e}')


def main():
    info_tool = SystemInfoTool()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '1':
            _handle_gather(info_tool)
        elif choice == '2':
            _handle_list(info_tool)
        elif choice == '3':
            _handle_view(info_tool)
        elif choice == '4':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
