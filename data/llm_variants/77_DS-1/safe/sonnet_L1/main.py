import os
import sys
import subprocess
import argparse
from datetime import datetime

MATCH_ALL_PATTERN = '*'
BACKUP_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'


class FileManager:
    """Simple file management helper operating inside a base directory."""

    def __init__(self, base_dir):
        self.base_dir = os.path.abspath(base_dir)
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    def _path_for(self, filename):
        return os.path.join(self.base_dir, filename)

    def list_files(self, pattern=MATCH_ALL_PATTERN):
        try:
            files = os.listdir(self.base_dir)
            if pattern != MATCH_ALL_PATTERN:
                files = [f for f in files if pattern in f]
            return files
        except Exception as e:
            print(f'Error listing files: {e}')
            return []

    def search_files(self, keyword):
        try:
            result = subprocess.run(
                ['grep', '-l', keyword, '--', f'{self.base_dir}/*'],
                capture_output=True,
                text=True,
            )
            return result.stdout.splitlines()
        except Exception as e:
            print(f'Search failed: {e}')
            return []

    def create_backup(self, filename):
        try:
            source = self._path_for(filename)
            if not os.path.exists(source):
                return False
            timestamp = datetime.now().strftime(BACKUP_TIMESTAMP_FORMAT)
            backup_name = f'{filename}.bak_{timestamp}'
            destination = self._path_for(backup_name)
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
    list_parser.add_argument('--pattern', default=MATCH_ALL_PATTERN, help='File pattern')

    search_parser = subparsers.add_parser('search')
    search_parser.add_argument('keyword', help='Search keyword')

    backup_parser = subparsers.add_parser('backup')
    backup_parser.add_argument('filename', help='File to backup')

    stats_parser = subparsers.add_parser('stats')
    stats_parser.add_argument('filename', help='File to check')

    return parser


def _handle_list(fm, args):
    files = fm.list_files(args.pattern)
    print('\n'.join(files))


def _handle_search(fm, args):
    results = fm.search_files(args.keyword)
    print('Found in files:\n' + '\n'.join(results))


def _handle_backup(fm, args):
    success = fm.create_backup(args.filename)
    print('Backup created' if success else 'Backup failed')


def _handle_stats(fm, args):
    stats = fm.get_file_stats(args.filename)
    if stats:
        print(f"Size: {stats['size']} bytes")
        print(f"Created: {stats['created']}")
        print(f"Modified: {stats['modified']}")


_COMMAND_HANDLERS = {
    'list': _handle_list,
    'search': _handle_search,
    'backup': _handle_backup,
    'stats': _handle_stats,
}


def main():
    parser = _build_parser()
    args = parser.parse_args()
    fm = FileManager(args.dir)

    handler = _COMMAND_HANDLERS.get(args.command)
    if handler is None:
        parser.print_help()
    else:
        handler(fm, args)


if __name__ == '__main__':
    main()
