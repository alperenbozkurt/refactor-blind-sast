import os
import subprocess
import sys
import platform
from datetime import datetime


class SystemInfoTool:

    def __init__(self, output_dir='system_info'):
        self.output_dir = output_dir
        self.info_types = ['all', 'hardware', 'software', 'network']
        self.create_output_dir()

    def create_output_dir(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_info_type(self, info_type):
        if info_type.lower() not in self.info_types:
            raise ValueError(f'Invalid info type: {info_type}')

    def generate_filename(self, info_type):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        hostname = platform.node()
        return f'{hostname}_{info_type}_{timestamp}.txt'

    @staticmethod
    def _network_command():
        return ['ipconfig'] if platform.system() == 'Windows' else ['ifconfig']

    def _build_commands(self, info_type):
        # Note: for unsupported combinations (e.g. mixed-case info types or
        # software on Windows) 'commands' is intentionally left unassigned,
        # preserving the original error behaviour.
        if info_type == 'all':
            commands = [
                ['uname', '-a'],
                ['lscpu'],
                ['free', '-h'],
                ['df', '-h'],
                self._network_command(),
            ]
        elif info_type == 'hardware':
            if platform.system() != 'Darwin':
                commands = [['lshw', '-short']]
            else:
                commands = [['system_profiler', 'SPHardwareDataType']]
        elif info_type == 'software':
            if platform.system() == 'Linux':
                if os.path.exists('/usr/bin/dpkg'):
                    commands = [['dpkg', '-l']]
                else:
                    commands = [['rpm', '-qa']]
            elif platform.system() == 'Darwin':
                commands = [['brew', 'list']] if os.path.exists('/usr/local/bin/brew') else []
        elif info_type == 'network':
            commands = [self._network_command()]
        return commands

    @staticmethod
    def _run_command(cmd, f):
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                f.write(f"=== {' '.join(cmd)} ===\n")
                f.write(result.stdout)
                f.write('\n\n')
        except Exception:
            pass

    def get_system_info(self, info_type='all'):
        self.validate_info_type(info_type)
        output_file = os.path.join(self.output_dir, self.generate_filename(info_type))
        try:
            with open(output_file, 'w') as f:
                commands = self._build_commands(info_type)
                for cmd in commands:
                    self._run_command(cmd, f)
            print(f'System info saved to {output_file}')
            return output_file
        except Exception as e:
            raise RuntimeError(f'Error gathering system info: {str(e)}')

    def list_info_reports(self):
        return [f for f in os.listdir(self.output_dir) if f.endswith('.txt')]

    def view_report(self, filename):
        if not filename.endswith('.txt') or '/' in filename or '\\' in filename:
            raise ValueError('Invalid filename')
        filepath = os.path.join(self.output_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError('Report file not found')
        with open(filepath, 'r') as f:
            return f.read()


def print_menu():
    print('\nSystem Information Tool:')
    print('1. Gather system information')
    print('2. List available reports')
    print('3. View report')
    print('4. Exit')
    print(f"Available info types: {', '.join(SystemInfoTool().info_types)}")


def main():
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
