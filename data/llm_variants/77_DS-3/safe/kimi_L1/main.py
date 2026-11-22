"""Log analysis tool.

Provides the :class:`LogAnalyzer` class for listing, searching, rotating,
and summarizing ``.log`` files in a directory, along with a command-line
interface implemented in :func:`main`.
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime


class LogAnalyzer:
    """Perform operations on the ``.log`` files in a single directory."""

    def __init__(self, log_dir):
        self.log_dir = os.path.abspath(log_dir)
        if not os.path.exists(self.log_dir):
            raise ValueError(f'Log directory {self.log_dir} does not exist')

    def list_logs(self):
        """Return the names of all ``.log`` files in the log directory."""
        return [
            filename
            for filename in os.listdir(self.log_dir)
            if filename.endswith('.log')
        ]

    def search_logs(self, pattern, case_sensitive=False):
        """Search every log file for ``pattern`` using grep.

        Returns the matching lines (each prefixed with its file name), or an
        empty list if the search could not be performed.
        """
        try:
            grep_cmd = ['grep', '--with-filename', '--no-messages']
            if not case_sensitive:
                grep_cmd.append('-i')
            # '--' ensures the pattern is never interpreted as a grep option.
            grep_cmd.extend([
                pattern,
                '--',
                os.path.join(self.log_dir, '*.log'),
            ])
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

    def rotate_logs(self, max_size_mb=10):
        """Rotate logs larger than ``max_size_mb`` megabytes.

        Each oversized log is renamed with a timestamped ``.bak`` suffix and
        a fresh empty log file is created in its place.
        """
        for log_file in self.list_logs():
            file_path = os.path.join(self.log_dir, log_file)
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            if size_mb > max_size_mb:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_name = f'{log_file}.{timestamp}.bak'
                os.rename(file_path, os.path.join(self.log_dir, backup_name))
                # Recreate the original log file as an empty file.
                with open(file_path, 'w'):
                    pass

    def count_entries(self, log_file):
        """Return the number of lines in ``log_file``, or ``-1`` on error."""
        try:
            with open(os.path.join(self.log_dir, log_file), 'r') as f:
                return sum(1 for _ in f)
        except IOError:
            return -1

    def get_stats(self):
        """Return size, modification time, and entry count for each log."""
        stats = {}
        for log_file in self.list_logs():
            file_path = os.path.join(self.log_dir, log_file)
            stats[log_file] = {
                'size': os.path.getsize(file_path),
                'modified': datetime.fromtimestamp(os.path.getmtime(file_path)),
                'entries': self.count_entries(log_file),
            }
        return stats


def main():
    """Parse command-line arguments and run the requested operation."""
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

    args = parser.parse_args()

    try:
        analyzer = LogAnalyzer(args.dir)
        if args.command == 'list':
            print('\n'.join(analyzer.list_logs()))
        elif args.command == 'search':
            results = analyzer.search_logs(args.pattern, args.case)
            print('\n'.join(results))
        elif args.command == 'rotate':
            analyzer.rotate_logs(args.size)
            print('Log rotation completed')
        elif args.command == 'stats':
            stats = analyzer.get_stats()
            for log, data in stats.items():
                print(
                    f"{log}: {data['entries']} entries, {data['size']} "
                    f"bytes, last modified {data['modified']}"
                )
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
