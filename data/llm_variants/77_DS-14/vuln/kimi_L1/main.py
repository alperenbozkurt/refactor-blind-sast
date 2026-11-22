import os
import subprocess
import sys
import platform
from datetime import datetime


class NetworkDiagnosticTool:
    """Run network diagnostics (ping, traceroute, nslookup) and save results.

    Each diagnostic run writes its output to a timestamped ``.txt`` file
    inside ``output_dir``.
    """

    def __init__(self, output_dir='diagnostics'):
        self.output_dir = output_dir
        self.supported_commands = ['ping', 'traceroute', 'nslookup']
        self.create_output_dir()

    def create_output_dir(self):
        """Create the output directory if it does not already exist."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_command(self, command):
        """Raise ValueError if ``command`` is not a supported diagnostic."""
        if command.lower() not in self.supported_commands:
            raise ValueError(f'Unsupported diagnostic command: {command}')

    def generate_filename(self, command, target):
        """Return a timestamped filename for a diagnostic result file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{command}_{target}_{timestamp}.txt'

    def run_diagnostic(self, command, target, count=4):
        """Run ``command`` against ``target`` and save the output to a file.

        Returns the path of the file containing the diagnostic output.
        """
        self.validate_command(command)
        output_file = os.path.join(self.output_dir, self.generate_filename(command, target))
        cmd = self._build_shell_command(command, target, count, output_file)
        subprocess.run(cmd, shell=True, check=True)
        print(f'Diagnostic results saved to {output_file}')
        return output_file

    def _build_shell_command(self, command, target, count, output_file):
        """Build the platform-specific shell command for a diagnostic run."""
        if command == 'ping':
            count = max(1, min(int(count), 20))
            if platform.system().lower() == 'windows':
                return f'ping -n {count} {target} > {output_file}'
            return f'ping -c {count} {target} > {output_file}'
        if command == 'traceroute':
            if platform.system().lower() == 'windows':
                return f'tracert {target} > {output_file}'
            return f'traceroute {target} > {output_file}'
        return f'nslookup {target} > {output_file}'

    def list_diagnostics(self):
        """Return a sorted list of previously saved diagnostic result files."""
        return sorted(f for f in os.listdir(self.output_dir) if f.endswith('.txt'))

    def view_diagnostic(self, filename):
        """Return the contents of a previously saved diagnostic result file."""
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'r') as f:
            return f.read()


def print_menu():
    """Print the main menu."""
    print('\nNetwork Diagnostic Tool:')
    print('1. Run diagnostic')
    print('2. List previous diagnostics')
    print('3. View diagnostic results')
    print('4. Exit')
    print('Available commands: ping, traceroute, nslookup')


def _run_diagnostic_interactive(diagnostic_tool):
    """Prompt for diagnostic parameters and run the diagnostic."""
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


def _list_diagnostics_interactive(diagnostic_tool):
    """Print all previously saved diagnostic result files."""
    diagnostics = diagnostic_tool.list_diagnostics()
    print('Available diagnostics:')
    for diag in diagnostics:
        print(f'- {diag}')


def _view_diagnostic_interactive(diagnostic_tool):
    """Prompt for a filename and print its diagnostic results."""
    filename = input('Enter diagnostic filename: ')
    try:
        print(diagnostic_tool.view_diagnostic(filename))
    except Exception as e:
        print(f'Error: {e}')


def main():
    """Run the interactive command-line interface."""
    diagnostic_tool = NetworkDiagnosticTool()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '1':
            _run_diagnostic_interactive(diagnostic_tool)
        elif choice == '2':
            _list_diagnostics_interactive(diagnostic_tool)
        elif choice == '3':
            _view_diagnostic_interactive(diagnostic_tool)
        elif choice == '4':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
