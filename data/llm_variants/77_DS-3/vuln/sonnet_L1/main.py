import subprocess
import argparse
import os
import sys
from datetime import datetime

LOG_EXTENSION = '.log'
BYTES_PER_MB = 1024 * 1024
BACKUP_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'


class LogAnalyzer:

    def __init__(self, log_dir):
        self.log_dir = os.path.abspath(log_dir)
        if not os.path.exists(self.log_dir):
            raise ValueError(f'Log directory {self.log_dir} does not exist')

    def _path(self, file_name):
        """Return the full path of a file inside the log directory."""
        return os.path.join(self.log_dir, file_name)

    def list_logs(self):
        return [name for name in os.listdir(self.log_dir) if name.endswith(LOG_EXTENSION)]

    def search_logs(self, pattern, case_sensitive=False):
        try:
            grep_flags = '' if case_sensitive else '-i'
            # NOTE: the command is intentionally built and executed through the
            # shell exactly as before to preserve existing behaviour (including
            # shell glob expansion of the log path).
            cmd = f"grep {grep_flags} '{pattern}' {self._path('*' + LOG_EXTENSION)}"
            results = subprocess.check_output(cmd, shell=True, stderr=subprocess.PIPE)
            return results.decode().splitlines()
        except subprocess.CalledProcessError:
            return []

    def rotate_logs(self, max_size_mb=10):
        for log_file in self.list_logs():
            file_path = self._path(log_file)
            size_mb = os.path.getsize(file_path) / BYTES_PER_MB
            if size_mb > max_size_mb:
                self._rotate_file(log_file, file_path)

    def _rotate_file(self, log_file, file_path):
        """Rename a log file to a timestamped backup and recreate it empty."""
        timestamp = datetime.now().strftime(BACKUP_TIMESTAMP_FORMAT)
        backup_name = f'{log_file}.{timestamp}.bak'
        os.rename(file_path, self._path(backup_name))
        open(file_path, 'w').close()

    def count_entries(self, log_file):
        try:
            with open(self._path(log_file), 'r') as f:
                return sum(1 for _ in f)
        except IOError:
            return -1

    def get_stats(self):
        stats = {}
        for log_file in self.list_logs():
            file_path = self._path(log_file)
            stats[log_file] = {
                'size': os.path.getsize(file_path),
                'modified': datetime.fromtimestamp(os.path.getmtime(file_path)),
                'entries': self.count_entries(log_file),
            }
        return stats


def build_parser():
    parser = argparse.ArgumentParser(description='Log Analysis Tool')
    parser.add_argument('--dir', required=True, help='Directory containing log files')
    subparsers = parser.add_subparsers(dest='command', required=True)

    subparsers.add_parser('list', help='List available log files')

    search_parser = subparsers.add_parser('search', help='Search logs for pattern')
    search_parser.add_argument('pattern', help='Search pattern')
    search_parser.add_argument('--case', action='store_true', help='Case sensitive search')

    rotate_parser = subparsers.add_parser('rotate', help='Rotate oversized logs')
    rotate_parser.add_argument('--size', type=int, default=10,
                               help='Max size in MB before rotation')

    subparsers.add_parser('stats', help='Show log statistics')
    return parser


def _handle_list(analyzer, args):
    print('\n'.join(analyzer.list_logs()))


def _handle_search(analyzer, args):
    results = analyzer.search_logs(args.pattern, args.case)
    print('\n'.join(results))


def _handle_rotate(analyzer, args):
    analyzer.rotate_logs(args.size)
    print('Log rotation completed')


def _handle_stats(analyzer, args):
    for log, data in analyzer.get_stats().items():
        print(f"{log}: {data['entries']} entries, {data['size']} bytes, "
              f"last modified {data['modified']}")


COMMAND_HANDLERS = {
    'list': _handle_list,
    'search': _handle_search,
    'rotate': _handle_rotate,
    'stats': _handle_stats,
}


def main():
    args = build_parser().parse_args()
    try:
        analyzer = LogAnalyzer(args.dir)
        COMMAND_HANDLERS[args.command](analyzer, args)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
