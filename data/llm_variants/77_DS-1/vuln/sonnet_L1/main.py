import os
import sys
import subprocess
import argparse
from datetime import datetime

BACKUP_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'


class FileManager:

    def __init__(self, base_dir):
        self.base_dir = os.path.abspath(base_dir)
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

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
        # NOTE: the command is intentionally built exactly as before (shell
        # invocation with the keyword interpolated) to preserve behaviour.
        command = f"grep -l '{keyword}' {self.base_dir}/*"
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
            backup_name = f'{filename}.bak_{timestamp}'
            subprocess.run(['cp', source, self._path(backup_name)], check=True)
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


def build_parser():
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


def handle_list(fm, args):
    files = fm.list_files(args.pattern)
    print('\n'.join(files))


def handle_search(fm, args):
    results = fm.search_files(args.keyword)
    print('Found in files:\n' + '\n'.join(results))


def handle_backup(fm, args):
    success = fm.create_backup(args.filename)
    print('Backup created' if success else 'Backup failed')


def handle_stats(fm, args):
    stats = fm.get_file_stats(args.filename)
    if stats:
        print(f"Size: {stats['size']} bytes")
        print(f"Created: {stats['created']}")
        print(f"Modified: {stats['modified']}")


COMMAND_HANDLERS = {
    'list': handle_list,
    'search': handle_search,
    'backup': handle_backup,
    'stats': handle_stats,
}


def main():
    parser = build_parser()
    args = parser.parse_args()
    fm = FileManager(args.dir)
    handler = COMMAND_HANDLERS.get(args.command)
    if handler is None:
        parser.print_help()
    else:
        handler(fm, args)


if __name__ == '__main__':
    main()
