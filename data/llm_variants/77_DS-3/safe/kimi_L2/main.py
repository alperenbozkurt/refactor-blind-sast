import argparse
import os
import subprocess
import sys
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

LOG_FILE_EXTENSION = '.log'
ROTATED_LOG_EXTENSION = '.bak'
ROTATION_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
BYTES_PER_MEGABYTE = 1024 * 1024
DEFAULT_MAX_SIZE_MB = 10

GREP_EXECUTABLE = 'grep'
GREP_BASE_OPTIONS = ('--with-filename', '--no-messages')
GREP_CASE_INSENSITIVE_FLAG = '-i'
GREP_PATTERN_SEPARATOR = '--'
GREP_LOG_GLOB = '*.log'

COMMAND_LIST = 'list'
COMMAND_SEARCH = 'search'
COMMAND_ROTATE = 'rotate'
COMMAND_STATS = 'stats'


# ---------------------------------------------------------------------------
# Small helper functions
# ---------------------------------------------------------------------------

def _build_grep_command(pattern, case_sensitive, log_dir):
    """Assemble the grep command line used to search the log directory."""
    command = [GREP_EXECUTABLE, *GREP_BASE_OPTIONS]
    if not case_sensitive:
        command.append(GREP_CASE_INSENSITIVE_FLAG)
    command.extend([
        pattern,
        GREP_PATTERN_SEPARATOR,
        os.path.join(log_dir, GREP_LOG_GLOB),
    ])
    return command


def _file_size_mb(file_path):
    """Return the size of *file_path* expressed in megabytes."""
    return os.path.getsize(file_path) / BYTES_PER_MEGABYTE


def _print_lines(lines):
    """Print an iterable of strings, one per line."""
    print('\n'.join(lines))


class LogAnalyzer:
    """Analyze, search and rotate the ``.log`` files contained in a directory."""

    def __init__(self, log_dir):
        self.log_dir = os.path.abspath(log_dir)
        if not os.path.exists(self.log_dir):
            raise ValueError(f'Log directory {self.log_dir} does not exist')

    def list_logs(self):
        return [f for f in os.listdir(self.log_dir) if f.endswith(LOG_FILE_EXTENSION)]

    def search_logs(self, pattern, case_sensitive=False):
        try:
            grep_cmd = _build_grep_command(pattern, case_sensitive, self.log_dir)
            result = subprocess.run(
                grep_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            return result.stdout.splitlines()
        except Exception as e:
            print(f'Search error: {e}', file=sys.stderr)
            return []

    def rotate_logs(self, max_size_mb=DEFAULT_MAX_SIZE_MB):
        for log_file in self.list_logs():
            file_path = self._log_path(log_file)
            if _file_size_mb(file_path) > max_size_mb:
                self._rotate_log(file_path, log_file)

    def count_entries(self, log_file):
        try:
            with open(self._log_path(log_file), 'r') as f:
                return sum((1 for _ in f))
        except IOError:
            return -1

    def get_stats(self):
        stats = {}
        for log_file in self.list_logs():
            stats[log_file] = self._log_stats(log_file)
        return stats

    # -- internal helpers ----------------------------------------------------

    def _log_path(self, log_file):
        """Return the absolute path of *log_file* inside the log directory."""
        return os.path.join(self.log_dir, log_file)

    def _rotate_log(self, file_path, log_file):
        """Rename a single oversized log file and recreate it empty."""
        timestamp = datetime.now().strftime(ROTATION_TIMESTAMP_FORMAT)
        new_name = f'{log_file}.{timestamp}{ROTATED_LOG_EXTENSION}'
        os.rename(file_path, self._log_path(new_name))
        open(file_path, 'w').close()

    def _log_stats(self, log_file):
        """Collect size, modification time and entry count for one log file."""
        file_path = self._log_path(log_file)
        return {
            'size': os.path.getsize(file_path),
            'modified': datetime.fromtimestamp(os.path.getmtime(file_path)),
            'entries': self.count_entries(log_file),
        }


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def _build_parser():
    """Create the argument parser for the log analysis tool."""
    parser = argparse.ArgumentParser(description='Log Analysis Tool')
    parser.add_argument('--dir', required=True, help='Directory containing log files')
    subparsers = parser.add_subparsers(dest='command', required=True)

    subparsers.add_parser(COMMAND_LIST, help='List available log files')

    search_parser = subparsers.add_parser(COMMAND_SEARCH, help='Search logs for pattern')
    search_parser.add_argument('pattern', help='Search pattern')
    search_parser.add_argument('--case', action='store_true', help='Case sensitive search')

    rotate_parser = subparsers.add_parser(COMMAND_ROTATE, help='Rotate oversized logs')
    rotate_parser.add_argument(
        '--size',
        type=int,
        default=DEFAULT_MAX_SIZE_MB,
        help='Max size in MB before rotation',
    )

    subparsers.add_parser(COMMAND_STATS, help='Show log statistics')

    return parser


def _format_stats_line(log, data):
    """Format a single line of the ``stats`` command output."""
    return (
        f"{log}: {data['entries']} entries, {data['size']} bytes, "
        f"last modified {data['modified']}"
    )


def _run_list(analyzer, args):
    _print_lines(analyzer.list_logs())


def _run_search(analyzer, args):
    _print_lines(analyzer.search_logs(args.pattern, args.case))


def _run_rotate(analyzer, args):
    analyzer.rotate_logs(args.size)
    print('Log rotation completed')


def _run_stats(analyzer, args):
    stats = analyzer.get_stats()
    for log, data in stats.items():
        print(_format_stats_line(log, data))


_COMMAND_HANDLERS = {
    COMMAND_LIST: _run_list,
    COMMAND_SEARCH: _run_search,
    COMMAND_ROTATE: _run_rotate,
    COMMAND_STATS: _run_stats,
}


def main():
    parser = _build_parser()
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
