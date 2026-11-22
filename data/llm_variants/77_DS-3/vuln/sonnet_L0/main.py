import argparse
import glob
import os
import subprocess
import sys
from datetime import datetime


class LogAnalyzer:

    def __init__(self, log_dir):
        self.log_dir = os.path.abspath(log_dir)
        if not os.path.exists(self.log_dir):
            raise ValueError(f'Log directory {self.log_dir} does not exist')

    def _path(self, name):
        return os.path.join(self.log_dir, name)

    def list_logs(self):
        return [f for f in os.listdir(self.log_dir) if f.endswith('.log')]

    def search_logs(self, pattern, case_sensitive=False):
        # Build an argument list instead of a shell string so that the pattern
        # and directory name are never interpreted by a shell.
        log_files = sorted(glob.glob(os.path.join(glob.escape(self.log_dir), '*.log')))
        if not log_files:
            return []

        cmd = ['grep']
        if not case_sensitive:
            cmd.append('-i')
        cmd.append(pattern)
        cmd.extend(log_files)

        try:
            results = subprocess.check_output(cmd, stderr=subprocess.PIPE)
        except (subprocess.CalledProcessError, OSError):
            return []
        return results.decode().splitlines()

    def rotate_logs(self, max_size_mb=10):
        for log_file in self.list_logs():
            file_path = self._path(log_file)
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            if size_mb > max_size_mb:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                new_name = f'{log_file}.{timestamp}.bak'
                os.rename(file_path, self._path(new_name))
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


def _build_parser():
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


def _run_command(analyzer, args):
    if args.command == 'list':
        print('\n'.join(analyzer.list_logs()))
    elif args.command == 'search':
        results = analyzer.search_logs(args.pattern, args.case)
        print('\n'.join(results))
    elif args.command == 'rotate':
        analyzer.rotate_logs(args.size)
        print('Log rotation completed')
    elif args.command == 'stats':
        for log, data in analyzer.get_stats().items():
            print(f"{log}: {data['entries']} entries, {data['size']} bytes, "
                  f"last modified {data['modified']}")


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
