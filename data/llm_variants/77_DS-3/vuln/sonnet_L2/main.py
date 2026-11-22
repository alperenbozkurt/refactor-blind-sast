import subprocess
import argparse
import os
import sys
import glob
from datetime import datetime

LOG_EXTENSION = '.log'
LOG_GLOB_PATTERN = '*' + LOG_EXTENSION
BACKUP_SUFFIX = '.bak'
BACKUP_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
BYTES_PER_MB = 1024 * 1024
DEFAULT_MAX_SIZE_MB = 10
GREP_EXECUTABLE = 'grep'
GREP_IGNORE_CASE_FLAG = '-i'
EXIT_CODE_ERROR = 1

CMD_LIST = 'list'
CMD_SEARCH = 'search'
CMD_ROTATE = 'rotate'
CMD_STATS = 'stats'


class LogAnalyzer:

    def __init__(self, log_dir):
        self.log_dir = os.path.abspath(log_dir)
        if not os.path.exists(self.log_dir):
            raise ValueError(f'Log directory {self.log_dir} does not exist')

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _path_for(self, file_name):
        return os.path.join(self.log_dir, file_name)

    def _log_file_paths(self):
        """Sorted absolute paths of all log files (shell-glob equivalent)."""
        return sorted(glob.glob(self._path_for(LOG_GLOB_PATTERN)))

    @staticmethod
    def _build_grep_command(pattern, case_sensitive, files):
        # Arguments are passed as a list (no shell) so that the pattern and
        # paths can never be interpreted as shell syntax.
        cmd = [GREP_EXECUTABLE]
        if not case_sensitive:
            cmd.append(GREP_IGNORE_CASE_FLAG)
        cmd.extend(['-e', pattern])
        cmd.extend(files)
        return cmd

    @staticmethod
    def _size_in_mb(file_path):
        return os.path.getsize(file_path) / BYTES_PER_MB

    @staticmethod
    def _backup_name(log_file):
        timestamp = datetime.now().strftime(BACKUP_TIMESTAMP_FORMAT)
        return f'{log_file}.{timestamp}{BACKUP_SUFFIX}'

    def _rotate_file(self, log_file):
        file_path = self._path_for(log_file)
        os.rename(file_path, self._path_for(self._backup_name(log_file)))
        open(file_path, 'w').close()

    def _file_stats(self, log_file):
        file_path = self._path_for(log_file)
        return {
            'size': os.path.getsize(file_path),
            'modified': datetime.fromtimestamp(os.path.getmtime(file_path)),
            'entries': self.count_entries(log_file),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def list_logs(self):
        return [f for f in os.listdir(self.log_dir) if f.endswith(LOG_EXTENSION)]

    def search_logs(self, pattern, case_sensitive=False):
        files = self._log_file_paths()
        if not files:
            return []
        cmd = self._build_grep_command(pattern, case_sensitive, files)
        try:
            results = subprocess.check_output(cmd, stderr=subprocess.PIPE)
            return results.decode().splitlines()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return []

    def rotate_logs(self, max_size_mb=DEFAULT_MAX_SIZE_MB):
        for log_file in self.list_logs():
            if self._size_in_mb(self._path_for(log_file)) > max_size_mb:
                self._rotate_file(log_file)

    def count_entries(self, log_file):
        try:
            with open(self._path_for(log_file), 'r') as f:
                return sum((1 for _ in f))
        except IOError:
            return -1

    def get_stats(self):
        return {log_file: self._file_stats(log_file) for log_file in self.list_logs()}


def build_parser():
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


def _format_stats_line(log, data):
    return (f"{log}: {data['entries']} entries, {data['size']} bytes, "
            f"last modified {data['modified']}")


def _handle_list(analyzer, args):
    print('\n'.join(analyzer.list_logs()))


def _handle_search(analyzer, args):
    results = analyzer.search_logs(args.pattern, args.case)
    print('\n'.join(results))


def _handle_rotate(analyzer, args):
    analyzer.rotate_logs(args.size)
    print('Log rotation completed')


def _handle_stats(analyzer, args):
    for (log, data) in analyzer.get_stats().items():
        print(_format_stats_line(log, data))


COMMAND_HANDLERS = {
    CMD_LIST: _handle_list,
    CMD_SEARCH: _handle_search,
    CMD_ROTATE: _handle_rotate,
    CMD_STATS: _handle_stats,
}


def main():
    args = build_parser().parse_args()
    try:
        analyzer = LogAnalyzer(args.dir)
        handler = COMMAND_HANDLERS.get(args.command)
        if handler is not None:
            handler(analyzer, args)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(EXIT_CODE_ERROR)


if __name__ == '__main__':
    main()
