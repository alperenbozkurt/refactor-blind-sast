import argparse
import os
import subprocess
import sys
import time
from typing import Callable, Dict, List, Optional

# --- Configuration constants --------------------------------------------------

DEFAULT_BACKUP_DIR = 'backups'
BACKUP_FILE_EXTENSION = '.sql'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

ACTION_BACKUP = 'Backup'
ACTION_RESTORE = 'Restore'
ACTION_DELETE = 'Delete'


# --- Shared helpers -------------------------------------------------------------

def _print_failure(action: str, error: Exception) -> None:
    """Write a failure message for ``action`` to stderr."""
    print(f'{action} failed: {error}', file=sys.stderr)


def _run_shell_command(cmd: str, action: str) -> bool:
    """Run ``cmd`` in a shell, reporting failures; return True on success."""
    try:
        subprocess.run(cmd, shell=True, check=True)
        return True
    except subprocess.CalledProcessError as error:
        _print_failure(action, error)
        return False


def _report_result(action: str, success: bool) -> None:
    """Print the standard CLI outcome message for ``action``."""
    print(f'{action} completed' if success else f'{action} failed')


# --- Backup management ----------------------------------------------------------

class DatabaseManager:

    def __init__(self, db_name: str, db_user: str):
        self.db_name = db_name
        self.db_user = db_user
        self.backup_dir = DEFAULT_BACKUP_DIR
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self, tables: Optional[List[str]] = None) -> bool:
        backup_file = self._backup_path(self._generate_backup_filename())
        cmd = self._build_dump_command(backup_file, tables)
        if not _run_shell_command(cmd, ACTION_BACKUP):
            return False
        return os.path.exists(backup_file)

    def list_backups(self) -> List[str]:
        return sorted(
            f
            for f in os.listdir(self.backup_dir)
            if f.startswith(self.db_name) and f.endswith(BACKUP_FILE_EXTENSION)
        )

    def restore_backup(self, backup_file: str) -> bool:
        if backup_file not in self.list_backups():
            return False
        backup_path = self._backup_path(backup_file)
        cmd = f'psql -U {self.db_user} -d {self.db_name} -f {backup_path}'
        return _run_shell_command(cmd, ACTION_RESTORE)

    def delete_backup(self, backup_file: str) -> bool:
        if backup_file not in self.list_backups():
            return False
        try:
            os.remove(self._backup_path(backup_file))
            return True
        except OSError as error:
            _print_failure(ACTION_DELETE, error)
            return False

    def _backup_path(self, backup_file: str) -> str:
        return os.path.join(self.backup_dir, backup_file)

    def _generate_backup_filename(self) -> str:
        timestamp = time.strftime(TIMESTAMP_FORMAT)
        return f'{self.db_name}_{timestamp}{BACKUP_FILE_EXTENSION}'

    def _build_dump_command(self, backup_file: str, tables: Optional[List[str]]) -> str:
        cmd = f'pg_dump -U {self.db_user} -d {self.db_name}'
        if tables:
            tables_str = ' '.join(tables)
            cmd += f' -t {tables_str}'
        return f'{cmd} > {backup_file}'


# --- Command line interface -----------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Database Backup Utility')
    parser.add_argument('--db', required=True, help='Database name')
    parser.add_argument('--user', required=True, help='Database user')

    subparsers = parser.add_subparsers(dest='command', required=True)

    backup_parser = subparsers.add_parser('backup')
    backup_parser.add_argument('--tables', nargs='+', help='Specific tables to backup')

    subparsers.add_parser('list')

    restore_parser = subparsers.add_parser('restore')
    restore_parser.add_argument('file', help='Backup file to restore')

    delete_parser = subparsers.add_parser('delete')
    delete_parser.add_argument('file', help='Backup file to delete')

    return parser


def _handle_backup(manager: DatabaseManager, args: argparse.Namespace) -> None:
    _report_result(ACTION_BACKUP, manager.create_backup(args.tables))


def _handle_list(manager: DatabaseManager, args: argparse.Namespace) -> None:
    print('\n'.join(manager.list_backups()))


def _handle_restore(manager: DatabaseManager, args: argparse.Namespace) -> None:
    _report_result(ACTION_RESTORE, manager.restore_backup(args.file))


def _handle_delete(manager: DatabaseManager, args: argparse.Namespace) -> None:
    _report_result(ACTION_DELETE, manager.delete_backup(args.file))


_COMMAND_HANDLERS: Dict[str, Callable[[DatabaseManager, argparse.Namespace], None]] = {
    'backup': _handle_backup,
    'list': _handle_list,
    'restore': _handle_restore,
    'delete': _handle_delete,
}


def main():
    args = _build_parser().parse_args()
    manager = DatabaseManager(args.db, args.user)
    _COMMAND_HANDLERS[args.command](manager, args)


if __name__ == '__main__':
    main()
