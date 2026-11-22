"""Interactive command-line system monitoring tool.

Runs simple system checks (cpu, memory, disk, network or a custom shell
command) and stores their output in timestamped log files.
"""

import os
import subprocess
import sys  # Kept for backwards compatibility (public module attribute).
import time  # Kept for backwards compatibility (public module attribute).
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_LOG_DIR = 'monitor_logs'
LOG_FILE_EXTENSION = '.log'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

CUSTOM_CHECK_TYPE = 'custom'

# Shell commands used to gather the output of each built-in check.
CHECK_COMMANDS = {
    'cpu': "top -bn1 | grep 'Cpu(s)'",
    'memory': 'free -h',
    'disk': 'df -h',
    'network': 'netstat -tuln',
}

AVAILABLE_CHECKS = list(CHECK_COMMANDS) + [CUSTOM_CHECK_TYPE]

# ---------------------------------------------------------------------------
# Command-line interface text
# ---------------------------------------------------------------------------

MENU_LINES = (
    '\nSystem Monitoring Tool:',
    '1. Run system check',
    '2. List available logs',
    '3. View log file',
    '4. Exit',
    'Available checks: cpu, memory, disk, network, custom',
)

CHOICE_RUN_CHECK = '1'
CHOICE_LIST_LOGS = '2'
CHOICE_VIEW_LOG = '3'
CHOICE_EXIT = '4'

PROMPT_CHOICE = 'Enter your choice: '
PROMPT_CHECK_TYPE = 'Check type (cpu/memory/disk/network/custom): '
PROMPT_CUSTOM_COMMAND = 'Enter custom command to execute: '
PROMPT_LOG_FILENAME = 'Enter log filename: '

MSG_AVAILABLE_LOGS_HEADER = 'Available logs:'
MSG_EXITING = 'Exiting...'
MSG_INVALID_CHOICE = 'Invalid choice. Please try again.'


# ---------------------------------------------------------------------------
# Shell helpers
# ---------------------------------------------------------------------------

def _build_check_command(check_type, custom_command, log_file):
    """Build the shell command that redirects check output to ``log_file``."""
    base_command = CHECK_COMMANDS.get(check_type, custom_command)
    return f'{base_command} > {log_file}'


def _run_shell_command(command):
    """Run ``command`` in a shell, raising on a non-zero exit status."""
    subprocess.run(command, shell=True, check=True)


# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------

class SystemMonitor:
    """Runs system checks and manages the resulting log files."""

    def __init__(self, log_dir=DEFAULT_LOG_DIR):
        self.log_dir = log_dir
        self.available_checks = list(AVAILABLE_CHECKS)
        self.create_log_dir()

    def create_log_dir(self):
        """Create the log directory if it does not already exist."""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

    def validate_check_type(self, check_type):
        """Raise ``ValueError`` if ``check_type`` is not a known check."""
        if check_type.lower() not in self.available_checks:
            raise ValueError(f'Invalid check type: {check_type}')

    def generate_log_filename(self, check_type):
        """Return a timestamped log filename for the given check type."""
        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        return f'{check_type}_check_{timestamp}{LOG_FILE_EXTENSION}'

    def execute_system_check(self, check_type, custom_command=None):
        """Run the requested check, log its output and return the log path."""
        self.validate_check_type(check_type)
        log_file = os.path.join(self.log_dir, self.generate_log_filename(check_type))
        command = _build_check_command(check_type, custom_command, log_file)
        _run_shell_command(command)
        print(f'Check completed. Results logged to {log_file}')
        return log_file

    def list_available_logs(self):
        """Return the sorted names of all log files in the log directory."""
        return sorted(
            entry
            for entry in os.listdir(self.log_dir)
            if entry.endswith(LOG_FILE_EXTENSION)
        )

    def read_log_file(self, filename):
        """Return the contents of the log file called ``filename``."""
        filepath = os.path.join(self.log_dir, filename)
        with open(filepath, 'r') as f:
            return f.read()


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def print_menu():
    for line in MENU_LINES:
        print(line)


def _handle_run_check(monitor):
    check_type = input(PROMPT_CHECK_TYPE)
    custom_command = None
    if check_type == CUSTOM_CHECK_TYPE:
        custom_command = input(PROMPT_CUSTOM_COMMAND)
    try:
        monitor.execute_system_check(check_type, custom_command)
    except Exception as e:
        print(f'Error: {e}')


def _handle_list_logs(monitor):
    logs = monitor.list_available_logs()
    print(MSG_AVAILABLE_LOGS_HEADER)
    for log in logs:
        print(f'- {log}')


def _handle_view_log(monitor):
    filename = input(PROMPT_LOG_FILENAME)
    try:
        print(monitor.read_log_file(filename))
    except Exception as e:
        print(f'Error: {e}')


def main():
    monitor = SystemMonitor()
    handlers = {
        CHOICE_RUN_CHECK: _handle_run_check,
        CHOICE_LIST_LOGS: _handle_list_logs,
        CHOICE_VIEW_LOG: _handle_view_log,
    }
    while True:
        print_menu()
        choice = input(PROMPT_CHOICE)
        if choice == CHOICE_EXIT:
            print(MSG_EXITING)
            break
        handler = handlers.get(choice)
        if handler is None:
            print(MSG_INVALID_CHOICE)
        else:
            handler(monitor)


if __name__ == '__main__':
    main()
