import os
import sys
import subprocess
import argparse
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DEFAULT_PATTERN = '*'
BACKUP_SUFFIX = '.bak_'
BACKUP_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
COPY_COMMAND = 'cp'
SEARCH_COMMAND_TEMPLATE = "grep -l '{keyword}' {base_dir}/*"

CLI_DESCRIPTION = 'File Management Utility'

COMMAND_LIST = 'list'
COMMAND_SEARCH = 'search'
COMMAND_BACKUP = 'backup'
COMMAND_STATS = 'stats'

MSG_SEARCH_HEADER = 'Found in files:\n'
MSG_BACKUP_CREATED = 'Backup created'
MSG_BACKUP_FAILED = 'Backup failed'


class FileManager:
    """Perform file operations within a single managed base directory."""

    def __init__(self, base_dir):
        self.base_dir = os.path.abspath(base_dir)
        self._ensure_base_dir()

    def _ensure_base_dir(self):
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    def _resolve_path(self, filename):
        return os.path.join(self.base_dir, filename)

    @staticmethod
    def _build_backup_name(filename):
        timestamp = datetime.now().strftime(BACKUP_TIMESTAMP_FORMAT)
        return f'{filename}{BACKUP_SUFFIX}{timestamp}'

    def list_files(self, pattern=DEFAULT_PATTERN):
        try:
            files = os.listdir(self.base_dir)
            if pattern != DEFAULT_PATTERN:
                files = [name for name in files if pattern in name]
            return files
        except Exception as e:
            print(f'Error listing files: {e}')
            return []

    def search_files(self, keyword):
        command = SEARCH_COMMAND_TEMPLATE.format(
            keyword=keyword, base_dir=self.base_dir
        )
        try:
            result = subprocess.check_output(
                command, shell=True, stderr=subprocess.STDOUT
            )
            return result.decode().splitlines()
        except subprocess.CalledProcessError:
            return []

    def create_backup(self, filename):
        try:
            source_path = self._resolve_path(filename)
            if not os.path.exists(source_path):
                return False
            backup_path = self._resolve_path(self._build_backup_name(filename))
            subprocess.run([COPY_COMMAND, source_path, backup_path], check=True)
            return True
        except Exception as e:
            print(f'Backup failed: {e}')
            return False

    def get_file_stats(self, filename):
        try:
            path = self._resolve_path(filename)
            stat = os.stat(path)
            return {
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime),
                'created': datetime.fromtimestamp(stat.st_ctime),
            }
        except Exception as e:
            print(f'Error getting stats: {e}')
            return None


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def _build_parser():
    parser = argparse.ArgumentParser(description=CLI_DESCRIPTION)
    parser.add_argument('--dir', required=True, help='Base directory')
    subparsers = parser.add_subparsers(dest='command')

    list_parser = subparsers.add_parser(COMMAND_LIST)
    list_parser.add_argument('--pattern', default=DEFAULT_PATTERN,
                             help='File pattern')

    search_parser = subparsers.add_parser(COMMAND_SEARCH)
    search_parser.add_argument('keyword', help='Search keyword')

    backup_parser = subparsers.add_parser(COMMAND_BACKUP)
    backup_parser.add_argument('filename', help='File to backup')

    stats_parser = subparsers.add_parser(COMMAND_STATS)
    stats_parser.add_argument('filename', help='File to check')

    return parser


def _handle_list(fm, args):
    files = fm.list_files(args.pattern)
    print('\n'.join(files))


def _handle_search(fm, args):
    results = fm.search_files(args.keyword)
    print(MSG_SEARCH_HEADER + '\n'.join(results))


def _handle_backup(fm, args):
    success = fm.create_backup(args.filename)
    print(MSG_BACKUP_CREATED if success else MSG_BACKUP_FAILED)


def _handle_stats(fm, args):
    stats = fm.get_file_stats(args.filename)
    if stats:
        print(f"Size: {stats['size']} bytes")
        print(f"Created: {stats['created']}")
        print(f"Modified: {stats['modified']}")


_COMMAND_HANDLERS = {
    COMMAND_LIST: _handle_list,
    COMMAND_SEARCH: _handle_search,
    COMMAND_BACKUP: _handle_backup,
    COMMAND_STATS: _handle_stats,
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
