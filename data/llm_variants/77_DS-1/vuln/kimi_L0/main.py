import os
import sys
import subprocess
import argparse
from datetime import datetime


class FileManager:

    def __init__(self, base_dir):
        self.base_dir = os.path.abspath(base_dir)
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    def _path_for(self, filename):
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
        try:
            output = subprocess.check_output(
                f"grep -l '{keyword}' {self.base_dir}/*",
                shell=True,
                stderr=subprocess.STDOUT,
            )
            return output.decode().splitlines()
        except subprocess.CalledProcessError:
            return []

    def create_backup(self, filename):
        try:
            source = self._path_for(filename)
            if not os.path.exists(source):
                return False
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            destination = self._path_for(f'{filename}.bak_{timestamp}')
            subprocess.run(['cp', source, destination], check=True)
            return True
        except Exception as e:
            print(f'Backup failed: {e}')
            return False

    def get_file_stats(self, filename):
        try:
            stat = os.stat(self._path_for(filename))
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
            print(f"Size: {stats['size']} bytes")
            print(f"Created: {stats['created']}")
            print(f"Modified: {stats['modified']}")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
