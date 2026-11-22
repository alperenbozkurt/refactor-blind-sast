"""Log analysis tool.

Provides the :class:`LogAnalyzer` class for listing, searching, rotating
and summarising ``*.log`` files, plus a small command-line interface.
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

LOG_FILE_EXTENSION = '.log'
BACKUP_FILE_SUFFIX = '.bak'
ROTATION_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
BYTES_PER_MEGABYTE = 1024 * 1024
DEFAULT_MAX_SIZE_MB = 10

GREP_CASE_INSENSITIVE_FLAG = '-i'
GREP_COMMAND_TEMPLATE = "grep {flags} '{pattern}' {glob_pattern}"

COMMAND_LIST = 'list'
COMMAND_SEARCH = 'search'
COMMAND_ROTATE = 'rotate'
COMMAND_STATS = 'stats'


# ---------------------------------------------------------------------------
# Small helper functions
# ---------------------------------------------------------------------------

def _file_size_mb(file_path):
    """Return the size of *file_path* expressed in megabytes."""
    return os.path.getsize(file_path) / BYTES_PER_MEGABYTE


def _build_grep_command(log_dir, pattern, case_sensitive):
    """Assemble the shell command used to search the log files."""
    flags = '' if case_sensitive else GREP_CASE_INSENSITIVE_FLAG
    return GREP_COMMAND_TEMPLATE.format(
        flags=flags,
        pattern=pattern,
        glob_pattern=os.path.join(log_dir, '*' + LOG_FILE_EXTENSION),
    )


def _timestamped_backup_name(log_file):
    """Return the backup name used when rotating *log_file*."""
    timestamp = datetime.now().strftime(ROTATION_TIMESTAMP_FORMAT)
    return f'{log_file}.{timestamp}{BACKUP_FILE_SUFFIX}'


def _format_stats_line(log, data):
    """Render one line of output for the ``stats`` subcommand."""
    return (
        f"{log}: {data['entries']} entries, "
        f"{data['size']} bytes, "
        f"last modified {data['modified']}"
    )


class LogAnalyzer:
    """List, search, rotate and summarise the logs in a directory."""

    def __init__(self, log_dir):
        self.log_dir = os.path.abspath(log_dir)
        if not os.path.exists(self.log_dir):
            raise ValueError(f'Log directory {self.log_dir} does not exist')

    def list_logs(self):
        """Return the names of every ``*.log`` file in the log directory."""
        return [
            name
            for name in os.listdir(self.log_dir)
            if name.endswith(LOG_FILE_EXTENSION)
        ]

    def search_logs(self, pattern, case_sensitive=False):
        """Return the lines matching *pattern* across every log file."""
        command = _build_grep_command(self.log_dir, pattern, case_sensitive)
        try:
            output = subprocess.check_output(
                command, shell=True, stderr=subprocess.PIPE
            )
            return output.decode().splitlines()
        except subprocess.CalledProcessError:
            return []

    def rotate_logs(self, max_size_mb=DEFAULT_MAX_SIZE_MB):
        """Rotate every log file larger than *max_size_mb* megabytes."""
        for log_file in self.list_logs():
            file_path = os.path.join(self.log_dir, log_file)
            if _file_size_mb(file_path) > max_size_mb:
                self._rotate_log(file_path, log_file)

    def _rotate_log(self, file_path, log_file):
        """Rename *file_path* to a timestamped backup and recreate it empty."""
        backup_name = _timestamped_backup_name(log_file)
        os.rename(file_path, os.path.join(self.log_dir, backup_name))
        open(file_path, 'w').close()

    def count_entries(self, log_file):
        """Return the number of lines in *log_file*, or ``-1`` on error."""
        try:
            with open(os.path.join(self.log_dir, log_file), 'r') as entries:
                return sum(1 for _ in entries)
        except IOError:
            return -1

    def get_stats(self):
        """Return size, modification time and entry count per log file."""
        stats = {}
        for log_file in self.list_logs():
            file_path = os.path.join(self.log_dir, log_file)
            stats[log_file] = self._build_stats_entry(log_file, file_path)
        return stats

    def _build_stats_entry(self, log_file, file_path):
        """Build the statistics dictionary for a single log file."""
        return {
            'size': os.path.getsize(file_path),
            'modified': datetime.fromtimestamp(os.path.getmtime(file_path)),
            'entries': self.count_entries(log_file),
        }


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def _handle_list(analyzer, args):
    """Handle the ``list`` subcommand."""
    print('\n'.join(analyzer.list_logs()))


def _handle_search(analyzer, args):
    """Handle the ``search`` subcommand."""
    print('\n'.join(analyzer.search_logs(args.pattern, args.case)))


def _handle_rotate(analyzer, args):
    """Handle the ``rotate`` subcommand."""
    analyzer.rotate_logs(args.size)
    print('Log rotation completed')


def _handle_stats(analyzer, args):
    """Handle the ``stats`` subcommand."""
    for log, data in analyzer.get_stats().items():
        print(_format_stats_line(log, data))


_COMMAND_HANDLERS = {
    COMMAND_LIST: _handle_list,
    COMMAND_SEARCH: _handle_search,
    COMMAND_ROTATE: _handle_rotate,
    COMMAND_STATS: _handle_stats,
}


def _build_argument_parser():
    """Build the argument parser for the command-line interface."""
    parser = argparse.ArgumentParser(description='Log Analysis Tool')
    parser.add_argument(
        '--dir', required=True, help='Directory containing log files'
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    subparsers.add_parser(COMMAND_LIST, help='List available log files')

    search_parser = subparsers.add_parser(
        COMMAND_SEARCH, help='Search logs for pattern'
    )
    search_parser.add_argument('pattern', help='Search pattern')
    search_parser.add_argument(
        '--case', action='store_true', help='Case sensitive search'
    )

    rotate_parser = subparsers.add_parser(
        COMMAND_ROTATE, help='Rotate oversized logs'
    )
    rotate_parser.add_argument(
        '--size',
        type=int,
        default=DEFAULT_MAX_SIZE_MB,
        help='Max size in MB before rotation',
    )

    subparsers.add_parser(COMMAND_STATS, help='Show log statistics')

    return parser


def main():
    """Entry point for the command-line interface."""
    parser = _build_argument_parser()
    args = parser.parse_args()
    try:
        analyzer = LogAnalyzer(args.dir)
        handler = _COMMAND_HANDLERS.get(args.command)
        if handler is not None:
            handler(analyzer, args)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
