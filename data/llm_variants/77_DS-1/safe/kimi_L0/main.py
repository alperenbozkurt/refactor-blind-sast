import os
import sys
import subprocess
import argparse
from datetime import datetime


class FileManager:
    """Utility for listing, searching, backing up and inspecting files."""

    def __init__(self, base_dir):
        self.base_dir = os.path.abspath(base_dir)
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    def _path(self, filename):
        """Return the path of *filename* inside the base directory."""
        return os.path.join(self.base_dir, filename)

    def list_files(self, pattern='*'):
        try:
            files = os.listdir(self.base_dir)
            if pattern != '*':
                files = [name for name in files if pattern in name]
            return files
        except Exception as exc:
            print(f'Error listing files: {exc}')
            return []

    def search_files(self, keyword):
        try:
            result = subprocess.run(
                ['grep', '-l', keyword, '--', f'{self.base_dir}/*'],
                capture_output=True,
                text=True,
            )
            return result.stdout.splitlines()
        except Exception as exc:
            print(f'Search failed: {exc}')
            return []

    def create_backup(self, filename):
        try:
            source = self._path(filename)
            if not os.path.exists(source):
                return False
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = self._path(f'{filename}.bak_{timestamp}')
            subprocess.run(['cp', source, backup_path], check=True)
            return True
        except Exception as exc:
            print(f'Backup failed: {exc}')
            return False

    def get_file_stats(self, filename):
        try:
            stat = os.stat(self._path(filename))
            return {
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime),
                'created': datetime.fromtimestamp(stat.st_ctime),
            }
        except Exception as exc:
            print(f'Error getting stats: {exc}')
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


def _handle_list(fm, args):
    print('\n'.join(fm.list_files(args.pattern)))


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
