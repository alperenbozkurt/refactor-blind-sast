"""File management utility command-line tool."""

import os
import sys
import subprocess
import argparse
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DEFAULT_PATTERN = '*'
BACKUP_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
CLI_DESCRIPTION = 'File Management Utility'

COMMAND_LIST = 'list'
COMMAND_SEARCH = 'search'
COMMAND_BACKUP = 'backup'
COMMAND_STATS = 'stats'

# ---------------------------------------------------------------------------
# File-related helpers
# ---------------------------------------------------------------------------


def _filter_by_pattern(files, pattern):
    """Return only the file names containing ``pattern`` ('*' matches all)."""
    if pattern == DEFAULT_PATTERN:
        return files
    return [f for f in files if pattern in f]


def _timestamped_backup_name(filename):
    """Build the backup file name for ``filename`` using the current time."""
    timestamp = datetime.now().strftime(BACKUP_TIMESTAMP_FORMAT)
    return f'{filename}.bak_{timestamp}'


def _file_stats_dict(stat):
    """Convert an ``os.stat`` result into the public stats dictionary."""
    return {
        'size': stat.st_size,
        'modified': datetime.fromtimestamp(stat.st_mtime),
        'created': datetime.fromtimestamp(stat.st_ctime),
    }


# ---------------------------------------------------------------------------
# Core file management
# ---------------------------------------------------------------------------


class FileManager:

    def __init__(self, base_dir):
        self.base_dir = os.path.abspath(base_dir)
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    def _resolve(self, filename):
        """Return the absolute path of ``filename`` inside the base directory."""
        return os.path.join(self.base_dir, filename)

    def list_files(self, pattern='*'):
        try:
            files = os.listdir(self.base_dir)
            return _filter_by_pattern(files, pattern)
        except Exception as e:
            print(f'Error listing files: {e}')
            return []

    def search_files(self, keyword):
        try:
            command = ['grep', '-l', keyword, '--', f'{self.base_dir}/*']
            result = subprocess.run(command, capture_output=True, text=True)
            return result.stdout.splitlines()
        except Exception as e:
            print(f'Search failed: {e}')
            return []

    def create_backup(self, filename):
        try:
            source = self._resolve(filename)
            if not os.path.exists(source):
                return False
            backup_path = self._resolve(_timestamped_backup_name(filename))
            subprocess.run(['cp', source, backup_path], check=True)
            return True
        except Exception as e:
            print(f'Backup failed: {e}')
            return False

    def get_file_stats(self, filename):
        try:
            stat = os.stat(self._resolve(filename))
            return _file_stats_dict(stat)
        except Exception as e:
            print(f'Error getting stats: {e}')
            return None


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------


def _build_parser():
    """Create the argument parser with all subcommands configured."""
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


def _run_list(fm, args):
    files = fm.list_files(args.pattern)
    print('\n'.join(files))


def _run_search(fm, args):
    results = fm.search_files(args.keyword)
    print('Found in files:\n' + '\n'.join(results))


def _run_backup(fm, args):
    success = fm.create_backup(args.filename)
    print('Backup created' if success else 'Backup failed')


def _run_stats(fm, args):
    stats = fm.get_file_stats(args.filename)
    if stats:
        print(f"Size: {stats['size']} bytes")
        print(f"Created: {stats['created']}")
        print(f"Modified: {stats['modified']}")


_COMMAND_HANDLERS = {
    COMMAND_LIST: _run_list,
    COMMAND_SEARCH: _run_search,
    COMMAND_BACKUP: _run_backup,
    COMMAND_STATS: _run_stats,
}


def main():
    parser = _build_parser()
    args = parser.parse_args()
    fm = FileManager(args.dir)
    handler = _COMMAND_HANDLERS.get(args.command)
    if handler is None:
        parser.print_help()
        return
    handler(fm, args)


if __name__ == '__main__':
    main()
