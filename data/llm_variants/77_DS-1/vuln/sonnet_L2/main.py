import os
import sys
import subprocess
import argparse
from datetime import datetime

# --- Constants -------------------------------------------------------------

DEFAULT_PATTERN = '*'
BACKUP_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
BACKUP_SUFFIX_TEMPLATE = '{filename}.bak_{timestamp}'
GREP_COMMAND_TEMPLATE = "grep -l '{keyword}' {base_dir}/*"
COPY_COMMAND = 'cp'

CMD_LIST = 'list'
CMD_SEARCH = 'search'
CMD_BACKUP = 'backup'
CMD_STATS = 'stats'

PROGRAM_DESCRIPTION = 'File Management Utility'


# --- Small helpers ---------------------------------------------------------

def _ensure_directory(path):
    """Create the directory (and parents) if it does not already exist."""
    if not os.path.exists(path):
        os.makedirs(path)


def _filter_by_substring(names, pattern):
    """Return names containing pattern; the default pattern matches everything."""
    if pattern != DEFAULT_PATTERN:
        return [n for n in names if pattern in n]
    return names


def _build_backup_name(filename, now=None):
    """Build a timestamped backup file name for the given file."""
    now = now if now is not None else datetime.now()
    timestamp = now.strftime(BACKUP_TIMESTAMP_FORMAT)
    return BACKUP_SUFFIX_TEMPLATE.format(filename=filename, timestamp=timestamp)


def _stat_to_dict(stat):
    """Convert an os.stat_result into the stats dictionary used by the API."""
    return {
        'size': stat.st_size,
        'modified': datetime.fromtimestamp(stat.st_mtime),
        'created': datetime.fromtimestamp(stat.st_ctime),
    }


# --- Core class ------------------------------------------------------------

class FileManager:

    def __init__(self, base_dir):
        self.base_dir = os.path.abspath(base_dir)
        _ensure_directory(self.base_dir)

    def _path(self, filename):
        return os.path.join(self.base_dir, filename)

    def list_files(self, pattern=DEFAULT_PATTERN):
        try:
            files = os.listdir(self.base_dir)
            return _filter_by_substring(files, pattern)
        except Exception as e:
            print(f'Error listing files: {e}')
            return []

    def search_files(self, keyword):
        try:
            command = GREP_COMMAND_TEMPLATE.format(keyword=keyword, base_dir=self.base_dir)
            result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
            return result.decode().splitlines()
        except subprocess.CalledProcessError:
            return []

    def create_backup(self, filename):
        try:
            if not os.path.exists(self._path(filename)):
                return False
            backup_name = _build_backup_name(filename)
            subprocess.run(
                [COPY_COMMAND, self._path(filename), self._path(backup_name)],
                check=True,
            )
            return True
        except Exception as e:
            print(f'Backup failed: {e}')
            return False

    def get_file_stats(self, filename):
        try:
            stat = os.stat(self._path(filename))
            return _stat_to_dict(stat)
        except Exception as e:
            print(f'Error getting stats: {e}')
            return None


# --- CLI -------------------------------------------------------------------

def _build_parser():
    parser = argparse.ArgumentParser(description=PROGRAM_DESCRIPTION)
    parser.add_argument('--dir', required=True, help='Base directory')
    subparsers = parser.add_subparsers(dest='command')

    list_parser = subparsers.add_parser(CMD_LIST)
    list_parser.add_argument('--pattern', default=DEFAULT_PATTERN, help='File pattern')

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
