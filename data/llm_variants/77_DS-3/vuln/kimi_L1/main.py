"""Command-line tool for listing, searching, rotating, and summarizing logs."""

import argparse
import os
import subprocess
import sys
from datetime import datetime

LOG_FILE_EXTENSION = '.log'
ROTATED_LOG_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
BYTES_PER_MEGABYTE = 1024 * 1024


class LogAnalyzer:
    """Analyze, search, and rotate the log files in a directory."""

    def __init__(self, log_dir):
        self.log_dir = os.path.abspath(log_dir)
        if not os.path.exists(self.log_dir):
            raise ValueError(f'Log directory {self.log_dir} does not exist')

    def list_logs(self):
        """Return the names of every log file in the log directory."""
        return [
            filename
            for filename in os.listdir(self.log_dir)
            if filename.endswith(LOG_FILE_EXTENSION)
        ]

    def search_logs(self, pattern, case_sensitive=False):
        """Return the lines from all log files that match ``pattern``."""
        try:
            command = self._build_grep_command(pattern, case_sensitive)
            results = subprocess.check_output(
                command, shell=True, stderr=subprocess.PIPE
            )
            return results.decode().splitlines()
        except subprocess.CalledProcessError:
            return []

    def rotate_logs(self, max_size_mb=10):
        """Back up logs larger than ``max_size_mb`` and start them fresh."""
        for log_file in self.list_logs():
            file_path = os.path.join(self.log_dir, log_file)
            if self._exceeds_size_limit(file_path, max_size_mb):
                self._rotate_log(file_path, log_file)

    def count_entries(self, log_file):
        """Return the number of lines in ``log_file``, or -1 if unreadable."""
        try:
            with open(os.path.join(self.log_dir, log_file), 'r') as handle:
                return sum(1 for _ in handle)
        except IOError:
            return -1

    def get_stats(self):
        """Return size, modification time, and entry count for each log."""
        return {
            log_file: self._collect_stats(log_file)
            for log_file in self.list_logs()
        }

    def _build_grep_command(self, pattern, case_sensitive):
        grep_flags = '' if case_sensitive else '-i'
        log_glob = os.path.join(self.log_dir, f'*{LOG_FILE_EXTENSION}')
        return f"grep {grep_flags} '{pattern}' {log_glob}"

    def _exceeds_size_limit(self, file_path, max_size_mb):
        size_mb = os.path.getsize(file_path) / BYTES_PER_MEGABYTE
        return size_mb > max_size_mb

    def _rotate_log(self, file_path, log_file):
        timestamp = datetime.now().strftime(ROTATED_LOG_TIMESTAMP_FORMAT)
        backup_name = f'{log_file}.{timestamp}.bak'
        os.rename(file_path, os.path.join(self.log_dir, backup_name))
        with open(file_path, 'w'):
            pass

    def _collect_stats(self, log_file):
        file_path = os.path.join(self.log_dir, log_file)
        return {
            'size': os.path.getsize(file_path),
            'modified': datetime.fromtimestamp(os.path.getmtime(file_path)),
            'entries': self.count_entries(log_file),
        }


def _build_parser():
    parser = argparse.ArgumentParser(description='Log Analysis Tool')
    parser.add_argument(
        '--dir', required=True, help='Directory containing log files'
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    subparsers.add_parser('list', help='List available log files')

    search_parser = subparsers.add_parser(
        'search', help='Search logs for pattern'
    )
    search_parser.add_argument('pattern', help='Search pattern')
    search_parser.add_argument(
        '--case', action='store_true', help='Case sensitive search'
    )

    rotate_parser = subparsers.add_parser(
        'rotate', help='Rotate oversized logs'
    )
    rotate_parser.add_argument(
        '--size', type=int, default=10, help='Max size in MB before rotation'
    )

    subparsers.add_parser('stats', help='Show log statistics')

    return parser


def _run_command(analyzer, args):
    if args.command == 'list':
        print('\n'.join(analyzer.list_logs()))
    elif args.command == 'search':
        print('\n'.join(analyzer.search_logs(args.pattern, args.case)))
    elif args.command == 'rotate':
        analyzer.rotate_logs(args.size)
        print('Log rotation completed')
    elif args.command == 'stats':
        _print_stats(analyzer.get_stats())


def _print_stats(stats):
    for log, data in stats.items():
        entries = data['entries']
        size = data['size']
        modified = data['modified']
        print(
            f'{log}: {entries} entries, {size} bytes, '
            f'last modified {modified}'
        )


def main():
    args = _build_parser().parse_args()
    try:
        analyzer = LogAnalyzer(args.dir)
        _run_command(analyzer, args)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
