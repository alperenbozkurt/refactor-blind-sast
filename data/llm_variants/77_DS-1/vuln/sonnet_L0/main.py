import os
import sys
import shlex
import subprocess
import argparse
from datetime import datetime

BACKUP_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'


class FileManager:

    def __init__(self, base_dir):
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def _path(self, filename):
        return os.path.join(self.base_dir, filename)

    def list_files(self, pattern='*'):
        try:
            files = os.listdir(self.base_dir)
            if pattern != '*':
                files = [f for f in files if pattern in f]
            return files
        except Exception as e:
            print(f'Error listing files: {e}')
            return []

    def search_files(self, keyword):
        # Quote user-supplied values so they cannot inject shell syntax;
        # the trailing glob is intentionally left for the shell to expand.
        command = f'grep -l {shlex.quote(keyword)} {shlex.quote(self.base_dir)}/*'
        try:
            result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
            return result.decode().splitlines()
        except subprocess.CalledProcessError:
            return []

    def create_backup(self, filename):
        try:
            source = self._path(filename)
            if not os.path.exists(source):
                return False
            timestamp = datetime.now().strftime(BACKUP_TIMESTAMP_FORMAT)
            destination = self._path(f'{filename}.bak_{timestamp}')
            subprocess.run(['cp', source, destination], check=True)
            return True
        except Exception as e:
            print(f'Backup failed: {e}')
            return False

    def get_file_stats(self, filename):
        try:
            stat = os.stat(self._path(filename))
            return {
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime),
                'created': datetime.fromtimestamp(stat.st_ctime),
            }
        except Exception as e:
            print(f'Error getting stats: {e}')
            return None


def _build_parser():
    parser = argparse.ArgumentParser(description='File Management Utility')
    parser.add_argument('--dir', required=True, help='Base directory')
    subparsers = parser.add_subparsers(dest='command')

    list_parser = subparsers.add_parser('list')
    list_parser.add_argument('--pattern', default='*', help='File pattern')

    search_parser = subparsers.add_parser('search')
    search_parser.add_argument('keyword', help='Search keyword')

    backup_parser = subparsers.add_parser('backup')
    backup_parser.add_argument('filename', help='File to backup')

    stats_parser = subparsers.add_parser('stats')
    stats_parser.add_argument('filename', help='File to check')
    return parser


def _print_stats(stats):
    print(f"Size: {stats['size']} bytes")
    print(f"Created: {stats['created']}")
    print(f"Modified: {stats['modified']}")


def main():
    parser = _build_parser()
    args = parser.parse_args()
    fm = FileManager(args.dir)

    if args.command == 'list':
        print('\n'.join(fm.list_files(args.pattern)))
    elif args.command == 'search':
        results = fm.search_files(args.keyword)
        print('Found in files:\n' + '\n'.join(results))
    elif args.command == 'backup':
        success = fm.create_backup(args.filename)
        print('Backup created' if success else 'Backup failed')
    elif args.command == 'stats':
        stats = fm.get_file_stats(args.filename)
        if stats:
            _print_stats(stats)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
