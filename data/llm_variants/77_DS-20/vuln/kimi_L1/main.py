import os
import platform
import subprocess
import sys
from datetime import datetime


class SystemInfoTool:
    """Collect system information reports and store them as text files."""

    def __init__(self, output_dir='system_info'):
        self.output_dir = output_dir
        self.info_types = ['all', 'hardware', 'software', 'network', 'custom']
        self.create_output_dir()

    def create_output_dir(self):
        """Create the output directory if it does not already exist."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_info_type(self, info_type):
        """Raise ValueError if the requested info type is not supported."""
        if info_type.lower() not in self.info_types:
            raise ValueError(f'Invalid info type: {info_type}')

    def generate_filename(self, info_type):
        """Build a report filename from hostname, info type and timestamp."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        hostname = platform.node()
        return f'{hostname}_{info_type}_{timestamp}.txt'

    def get_system_info(self, info_type='all', custom_command=None):
        """Run the command for the requested info type and save its output."""
        self.validate_info_type(info_type)
        output_file = os.path.join(self.output_dir, self.generate_filename(info_type))
        commands = {
            'all': f'(uname -a; lscpu; free -h; df -h; ifconfig) > {output_file}',
            'hardware': f'(lshw -short 2>/dev/null || system_profiler SPHardwareDataType) > {output_file}',
            'software': f'(dpkg -l || rpm -qa || brew list) > {output_file}',
            'network': f'(ifconfig || ip addr) > {output_file}',
        }
        cmd = commands.get(info_type, f'{custom_command} > {output_file}')
        subprocess.run(cmd, shell=True, check=True)
        print(f'System info saved to {output_file}')
        return output_file

    def list_info_reports(self):
        """Return the names of all text reports in the output directory."""
        return [
            filename
            for filename in os.listdir(self.output_dir)
            if filename.endswith('.txt')
        ]

    def view_report(self, filename):
        """Return the contents of the named report."""
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'r') as report:
            return report.read()


def print_menu():
    """Display the main menu."""
    print('\nSystem Information Tool:')
    print('1. Gather system information')
    print('2. List available reports')
    print('3. View report')
    print('4. Exit')
    print('Available info types: all, hardware, software, network, custom')


def main():
    """Run the interactive command-line interface."""
    info_tool = SystemInfoTool()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '1':
            info_type = input('Info type (all/hardware/software/network/custom): ')
            custom_cmd = None
            if info_type == 'custom':
                custom_cmd = input('Enter custom command to execute: ')
            try:
                info_tool.get_system_info(info_type, custom_cmd)
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
