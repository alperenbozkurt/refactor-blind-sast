import os
import sys
import subprocess
import argparse
from datetime import datetime

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
WILDCARD_PATTERN = '*'
BACKUP_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
BACKUP_SUFFIX_TEMPLATE = '{filename}.bak_{timestamp}'

GREP_COMMAND = 'grep'
GREP_LIST_FLAG = '-l'
COPY_COMMAND = 'cp'

CMD_LIST = 'list'
CMD_SEARCH = 'search'
CMD_BACKUP = 'backup'
CMD_STATS = 'stats'

MSG_BACKUP_OK = 'Backup created'
MSG_BACKUP_FAIL = 'Backup failed'
MSG_SEARCH_HEADER = 'Found in files:\n'


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _filter_by_substring(names, pattern):
    """Return names containing ``pattern``; the wildcard matches everything."""
    if pattern == WILDCARD_PATTERN:
        return names
    return [name for name in names if pattern in name]


def _build_backup_name(filename, now=None):
    """Build a timestamped backup file name."""
    now = now if now is not None else datetime.now()
    timestamp = now.strftime(BACKUP_TIMESTAMP_FORMAT)
    return BACKUP_SUFFIX_TEMPLATE.format(filename=filename, timestamp=timestamp)


def _stat_to_dict(stat):
    """Convert an ``os.stat_result`` into the public stats dictionary."""
    return {
        'size': stat.st_size,
        'modified': datetime.fromtimestamp(stat.st_mtime),
        'created': datetime.fromtimestamp(stat.st_ctime),
    }


# --------------------------------------------------------------------------- #
# Core class
# --------------------------------------------------------------------------- #
class FileManager:

    def __init__(self, base_dir):
        self.base_dir = os.path.abspath(base_dir)
        self._ensure_base_dir()

    def _ensure_base_dir(self):
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    def _path_for(self, filename):
        return os.path.join(self.base_dir, filename)

    def list_files(self, pattern='*'):
        try:
            files = os.listdir(self.base_dir)
            return _filter_by_substring(files, pattern)
        except Exception as e:
            print(f'Error listing files: {e}')
            return []

    def search_files(self, keyword):
        try:
            command = [GREP_COMMAND, GREP_LIST_FLAG, keyword, '--', f'{self.base_dir}/*']
            result = subprocess.run(command, capture_output=True, text=True)
            return result.stdout.splitlines()
        except Exception as e:
            print(f'Search failed: {e}')
            return []

    def create_backup(self, filename):
        try:
            source = self._path_for(filename)
            if not os.path.exists(source):
                return False
            backup_name = _build_backup_name(filename)
            destination = self._path_for(backup_name)
            subprocess.run([COPY_COMMAND, source, destination], check=True)
            return True
        except Exception as e:
            print(f'Backup failed: {e}')
            return False

    def get_file_stats(self, filename):
        try:
            stat = os.stat(self._path_for(filename))
            return _stat_to_dict(stat)
        except Exception as e:
            print(f'Error getting stats: {e}')
            return None


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _build_parser():
    parser = argparse.ArgumentParser(description='File Management Utility')
    parser.add_argument('--dir', required=True, help='Base directory')
    subparsers = parser.add_subparsers(dest='command')

    list_parser = subparsers.add_parser(CMD_LIST)
    list_parser.add_argument('--pattern', default=WILDCARD_PATTERN, help='File pattern')

    search_parser = subparsers.add_parser(CMD_SEARCH)
    search_parser.add_argument('keyword', help='Search keyword')

    backup_parser = subparsers.add_parser(CMD_BACKUP)
    backup_parser.add_argument('filename', help='File to backup')

    stats_parser = subparsers.add_parser(CMD_STATS)
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
    print(MSG_BACKUP_OK if success else MSG_BACKUP_FAIL)


def _handle_stats(fm, args):
    stats = fm.get_file_stats(args.filename)
    if stats:
        print(f"Size: {stats['size']} bytes")
        print(f"Created: {stats['created']}")
        print(f"Modified: {stats['modified']}")


_COMMAND_HANDLERS = {
    CMD_LIST: _handle_list,
    CMD_SEARCH: _handle_search,
    CMD_BACKUP: _handle_backup,
    CMD_STATS: _handle_stats,
}


def main():
    parser = _build_parser()
    args = parser.parse_args()
    fm = FileManager(args.dir)
    handler = _COMMAND_HANDLERS.get(args.command)
    if handler is not None:
        handler(fm, args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
