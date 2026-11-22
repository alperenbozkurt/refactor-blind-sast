import subprocess
import argparse
import os
import sys
import time
from typing import Optional, List

DEFAULT_BACKUP_DIR = 'backups'
BACKUP_EXTENSION = '.sql'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

CMD_BACKUP = 'backup'
CMD_LIST = 'list'
CMD_RESTORE = 'restore'
CMD_DELETE = 'delete'


def _log_error(message: str) -> None:
    print(message, file=sys.stderr)


def _run_shell(cmd: str) -> None:
    subprocess.run(cmd, shell=True, check=True)


class DatabaseManager:

    def __init__(self, db_name: str, db_user: str):
        self.db_name = db_name
        self.db_user = db_user
        self.backup_dir = DEFAULT_BACKUP_DIR
        os.makedirs(self.backup_dir, exist_ok=True)

    # ---- helpers -------------------------------------------------------

    def _build_backup_path(self) -> str:
        timestamp = time.strftime(TIMESTAMP_FORMAT)
        return os.path.join(self.backup_dir, f'{self.db_name}_{timestamp}{BACKUP_EXTENSION}')

    def _build_dump_command(self, backup_file: str, tables: Optional[List[str]]) -> str:
        base = f'pg_dump -U {self.db_user} -d {self.db_name}'
        if tables:
            tables_str = ' '.join(tables)
            base = f'{base} -t {tables_str}'
        return f'{base} > {backup_file}'

    def _build_restore_command(self, backup_file: str) -> str:
        path = os.path.join(self.backup_dir, backup_file)
        return f'psql -U {self.db_user} -d {self.db_name} -f {path}'

    def _is_known_backup(self, backup_file: str) -> bool:
        return backup_file in self.list_backups()

    # ---- public API ----------------------------------------------------

    def create_backup(self, tables: Optional[List[str]]=None) -> bool:
        backup_file = self._build_backup_path()
        try:
            _run_shell(self._build_dump_command(backup_file, tables))
            return os.path.exists(backup_file)
        except subprocess.CalledProcessError as e:
            _log_error(f'Backup failed: {e}')
            return False

    def list_backups(self) -> List[str]:
        return sorted([
            f for f in os.listdir(self.backup_dir)
            if f.startswith(self.db_name) and f.endswith(BACKUP_EXTENSION)
        ])

    def restore_backup(self, backup_file: str) -> bool:
        if not self._is_known_backup(backup_file):
            return False
        try:
            _run_shell(self._build_restore_command(backup_file))
            return True
        except subprocess.CalledProcessError as e:
            _log_error(f'Restore failed: {e}')
            return False

    def delete_backup(self, backup_file: str) -> bool:
        if not self._is_known_backup(backup_file):
            return False
        try:
            os.remove(os.path.join(self.backup_dir, backup_file))
            return True
        except OSError as e:
            _log_error(f'Delete failed: {e}')
            return False


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Database Backup Utility')
    parser.add_argument('--db', required=True, help='Database name')
    parser.add_argument('--user', required=True, help='Database user')
    subparsers = parser.add_subparsers(dest='command', required=True)

    backup_parser = subparsers.add_parser(CMD_BACKUP)
    backup_parser.add_argument('--tables', nargs='+', help='Specific tables to backup')

    subparsers.add_parser(CMD_LIST)

    restore_parser = subparsers.add_parser(CMD_RESTORE)
    restore_parser.add_argument('file', help='Backup file to restore')

    delete_parser = subparsers.add_parser(CMD_DELETE)
    delete_parser.add_argument('file', help='Backup file to delete')
    return parser


def _report(success: bool, label: str) -> None:
    print(f'{label} completed' if success else f'{label} failed')


def _handle_backup(manager: DatabaseManager, args: argparse.Namespace) -> None:
    _report(manager.create_backup(args.tables), 'Backup')


def _handle_list(manager: DatabaseManager, args: argparse.Namespace) -> None:
    print('\n'.join(manager.list_backups()))


def _handle_restore(manager: DatabaseManager, args: argparse.Namespace) -> None:
    _report(manager.restore_backup(args.file), 'Restore')


def _handle_delete(manager: DatabaseManager, args: argparse.Namespace) -> None:
    _report(manager.delete_backup(args.file), 'Delete')


COMMAND_HANDLERS = {
    CMD_BACKUP: _handle_backup,
    CMD_LIST: _handle_list,
    CMD_RESTORE: _handle_restore,
    CMD_DELETE: _handle_delete,
}


def main():
    args = _build_parser().parse_args()
    manager = DatabaseManager(args.db, args.user)
    handler = COMMAND_HANDLERS.get(args.command)
    if handler is not None:
        handler(manager, args)


if __name__ == '__main__':
    main()
