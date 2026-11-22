import subprocess
import argparse
import os
import sys
from datetime import datetime

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
LOG_EXTENSION = '.log'
LOG_GLOB = '*' + LOG_EXTENSION
BACKUP_SUFFIX = 'bak'
BACKUP_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
BYTES_PER_MB = 1024 * 1024
DEFAULT_MAX_SIZE_MB = 10
GREP_BASE_COMMAND = ('grep', '--with-filename', '--no-messages')
GREP_IGNORE_CASE_FLAG = '-i'
GREP_END_OF_OPTIONS = '--'
EXIT_FAILURE = 1

CMD_LIST = 'list'
CMD_SEARCH = 'search'
CMD_ROTATE = 'rotate'
CMD_STATS = 'stats'


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _build_grep_command(pattern, log_dir, case_sensitive):
    """Build the grep argument vector used for searching logs."""
    cmd = list(GREP_BASE_COMMAND)
    if not case_sensitive:
        cmd.append(GREP_IGNORE_CASE_FLAG)
    # NOTE: the glob is passed verbatim (no shell expansion), as in the
    # original implementation.
    cmd.extend([pattern, GREP_END_OF_OPTIONS, os.path.join(log_dir, LOG_GLOB)])
    return cmd


def _backup_name(log_file, now=None):
    """Return the backup file name for a rotated log file."""
    now = now or datetime.now()
    timestamp = now.strftime(BACKUP_TIMESTAMP_FORMAT)
    return f'{log_file}.{timestamp}.{BACKUP_SUFFIX}'


def _file_size_mb(file_path):
    return os.path.getsize(file_path) / BYTES_PER_MB


def _format_stats_line(log, data):
    return (f"{log}: {data['entries']} entries, {data['size']} bytes, "
            f"last modified {data['modified']}")


def _print_lines(lines):
    print('\n'.join(lines))


# --------------------------------------------------------------------------- #
# Core class
# --------------------------------------------------------------------------- #
class LogAnalyzer:

    def __init__(self, log_dir):
        self.log_dir = os.path.abspath(log_dir)
        if not os.path.exists(self.log_dir):
            raise ValueError(f'Log directory {self.log_dir} does not exist')

    def _path(self, file_name):
        return os.path.join(self.log_dir, file_name)

    def list_logs(self):
        return [f for f in os.listdir(self.log_dir) if f.endswith(LOG_EXTENSION)]

    def search_logs(self, pattern, case_sensitive=False):
        try:
            grep_cmd = _build_grep_command(pattern, self.log_dir, case_sensitive)
            result = subprocess.run(grep_cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, check=False)
            return result.stdout.splitlines()
        except Exception as e:
            print(f'Search error: {e}', file=sys.stderr)
            return []

    def _rotate_file(self, log_file):
        file_path = self._path(log_file)
        os.rename(file_path, self._path(_backup_name(log_file)))
        open(file_path, 'w').close()

    def rotate_logs(self, max_size_mb=DEFAULT_MAX_SIZE_MB):
        for log_file in self.list_logs():
            if _file_size_mb(self._path(log_file)) > max_size_mb:
                self._rotate_file(log_file)

    def count_entries(self, log_file):
        try:
            with open(self._path(log_file), 'r') as f:
                return sum((1 for _ in f))
        except IOError:
            return -1

    def _file_stats(self, log_file):
        file_path = self._path(log_file)
        return {
            'size': os.path.getsize(file_path),
            'modified': datetime.fromtimestamp(os.path.getmtime(file_path)),
            'entries': self.count_entries(log_file),
        }

    def get_stats(self):
        return {log_file: self._file_stats(log_file) for log_file in self.list_logs()}


# --------------------------------------------------------------------------- #
# Command-line interface
# --------------------------------------------------------------------------- #
def _build_parser():
    parser = argparse.ArgumentParser(description='Log Analysis Tool')
    parser.add_argument('--dir', required=True, help='Directory containing log files')
    subparsers = parser.add_subparsers(dest='command', required=True)

    subparsers.add_parser(CMD_LIST, help='List available log files')

    search_parser = subparsers.add_parser(CMD_SEARCH, help='Search logs for pattern')
    search_parser.add_argument('pattern', help='Search pattern')
    search_parser.add_argument('--case', action='store_true', help='Case sensitive search')

    rotate_parser = subparsers.add_parser(CMD_ROTATE, help='Rotate oversized logs')
    rotate_parser.add_argument('--size', type=int, default=DEFAULT_MAX_SIZE_MB,
                               help='Max size in MB before rotation')

    subparsers.add_parser(CMD_STATS, help='Show log statistics')
    return parser


def _handle_list(analyzer, args):
    _print_lines(analyzer.list_logs())


def _handle_search(analyzer, args):
    _print_lines(analyzer.search_logs(args.pattern, args.case))


def _handle_rotate(analyzer, args):
    analyzer.rotate_logs(args.size)
    print('Log rotation completed')


def _handle_stats(analyzer, args):
    for log, data in analyzer.get_stats().items():
        print(_format_stats_line(log, data))


_COMMAND_HANDLERS = {
    CMD_LIST: _handle_list,
    CMD_SEARCH: _handle_search,
    CMD_ROTATE: _handle_rotate,
    CMD_STATS: _handle_stats,
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
        sys.exit(EXIT_FAILURE)


if __name__ == '__main__':
    main()
