import os
import subprocess
import sys
import platform
from datetime import datetime


class SystemInfoTool:
    """Collect, store and inspect system information reports."""

    def __init__(self, output_dir='system_info'):
        self.output_dir = output_dir
        self.info_types = ['all', 'hardware', 'software', 'network']
        self.create_output_dir()

    def create_output_dir(self):
        """Create the output directory if it does not exist yet."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_info_type(self, info_type):
        """Raise ValueError if info_type is not one of the supported types."""
        if info_type.lower() not in self.info_types:
            raise ValueError(f'Invalid info type: {info_type}')

    def generate_filename(self, info_type):
        """Return a report filename built from host, info type and timestamp."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        hostname = platform.node()
        return f'{hostname}_{info_type}_{timestamp}.txt'

    def get_system_info(self, info_type='all'):
        """Write system information of the requested type to a report file."""
        self.validate_info_type(info_type)
        output_file = os.path.join(self.output_dir, self.generate_filename(info_type))
        try:
            with open(output_file, 'w') as report:
                commands = self._commands_for(info_type)
                self._write_command_outputs(report, commands)
            print(f'System info saved to {output_file}')
            return output_file
        except Exception as e:
            raise RuntimeError(f'Error gathering system info: {str(e)}')

    def _commands_for(self, info_type):
        """Return the platform-specific commands for the given info type."""
        system = platform.system()
        if info_type == 'all':
            commands = [
                ['uname', '-a'],
                ['lscpu'],
                ['free', '-h'],
                ['df', '-h'],
                ['ifconfig'] if system != 'Windows' else ['ipconfig'],
            ]
        elif info_type == 'hardware':
            commands = (
                [['system_profiler', 'SPHardwareDataType']]
                if system == 'Darwin'
                else [['lshw', '-short']]
            )
        elif info_type == 'software':
            if system == 'Linux':
                commands = [['dpkg', '-l']] if os.path.exists('/usr/bin/dpkg') else [['rpm', '-qa']]
            elif system == 'Darwin':
                commands = [['brew', 'list']] if os.path.exists('/usr/local/bin/brew') else []
        elif info_type == 'network':
            commands = [['ifconfig']] if system != 'Windows' else [['ipconfig']]
        return commands

    @staticmethod
    def _write_command_outputs(report, commands):
        """Run each command and append the output of the successful ones.

        Errors raised by individual commands (or while writing their
        output) are silently ignored.
        """
        for cmd in commands:
            try:
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if result.returncode == 0:
                    report.write(f"=== {' '.join(cmd)} ===\n")
                    report.write(result.stdout)
                    report.write('\n\n')
            except Exception:
                continue

    def list_info_reports(self):
        """Return the names of all report files in the output directory."""
        return [f for f in os.listdir(self.output_dir) if f.endswith('.txt')]

    def view_report(self, filename):
        """Return the contents of the report with the given filename."""
        if not filename.endswith('.txt') or '/' in filename or '\\' in filename:
            raise ValueError('Invalid filename')
        filepath = os.path.join(self.output_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError('Report file not found')
        with open(filepath, 'r') as f:
            return f.read()


def print_menu():
    """Print the main menu of the interactive interface."""
    print('\nSystem Information Tool:')
    print('1. Gather system information')
    print('2. List available reports')
    print('3. View report')
    print('4. Exit')
    print(f"Available info types: {', '.join(SystemInfoTool().info_types)}")


def main():
    """Run the interactive command-line interface."""
    info_tool = SystemInfoTool()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '1':
            info_type = input('Info type (all/hardware/software/network): ')
            try:
                info_tool.get_system_info(info_type)
            except Exception as e:
                print(f'Error: {e}')
        elif choice == '2':
            reports = info_tool.list_info_reports()
            print('Available reports:')
            for report in reports:
                print(f'- {report}')
        elif choice == '3':
            filename = input('Enter report filename: ')
            try:
                print(info_tool.view_report(filename))
            except Exception as e:
                print(f'Error: {e}')
        elif choice == '4':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
