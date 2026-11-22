import subprocess
import argparse
import os
import sys
import time
from typing import Optional, List

BACKUP_DIR_NAME = 'backups'
BACKUP_EXTENSION = '.sql'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'


class DatabaseManager:

    def __init__(self, db_name: str, db_user: str):
        self.db_name = db_name
        self.db_user = db_user
        self.backup_dir = BACKUP_DIR_NAME
        os.makedirs(self.backup_dir, exist_ok=True)

    @staticmethod
    def _validate_table_names(tables: List[str]) -> None:
        for table in tables:
            if not table.replace('_', '').isalnum():
                raise ValueError(f'Invalid table name: {table}')

    def _backup_path(self, backup_file: str) -> str:
        return os.path.join(self.backup_dir, backup_file)

    def _is_known_backup(self, backup_file: str) -> bool:
        return backup_file in self.list_backups()

    def create_backup(self, tables: Optional[List[str]]=None) -> bool:
        timestamp = time.strftime(TIMESTAMP_FORMAT)
        backup_file = self._backup_path(f'{self.db_name}_{timestamp}{BACKUP_EXTENSION}')
        try:
            cmd = ['pg_dump', '-U', self.db_user, '-d', self.db_name, '-f', backup_file]
            if tables:
                self._validate_table_names(tables)
                cmd.extend(['-t'] + tables)
            subprocess.run(cmd, check=True)
            return os.path.exists(backup_file)
        except subprocess.CalledProcessError as e:
            print(f'Backup failed: {e}', file=sys.stderr)
            return False
        except ValueError as e:
            print(f'Validation error: {e}', file=sys.stderr)
            return False

    def list_backups(self) -> List[str]:
        return sorted(
            name for name in os.listdir(self.backup_dir)
            if name.startswith(self.db_name) and name.endswith(BACKUP_EXTENSION)
        )

    def restore_backup(self, backup_file: str) -> bool:
        if not self._is_known_backup(backup_file):
            return False
        try:
            cmd = ['psql', '-U', self.db_user, '-d', self.db_name, '-f', self._backup_path(backup_file)]
            subprocess.run(cmd, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f'Restore failed: {e}', file=sys.stderr)
            return False

    def delete_backup(self, backup_file: str) -> bool:
        if not self._is_known_backup(backup_file):
            return False
        try:
            os.remove(self._backup_path(backup_file))
            return True
        except OSError as e:
            print(f'Delete failed: {e}', file=sys.stderr)
            return False


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


def _report(success: bool, action: str) -> None:
    print(f'{action} completed' if success else f'{action} failed')


def main():
    args = _build_parser().parse_args()
    manager = DatabaseManager(args.db, args.user)

    if args.command == 'backup':
        _report(manager.create_backup(args.tables), 'Backup')
    elif args.command == 'list':
        print('\n'.join(manager.list_backups()))
    elif args.command == 'restore':
        _report(manager.restore_backup(args.file), 'Restore')
    elif args.command == 'delete':
        _report(manager.delete_backup(args.file), 'Delete')


if __name__ == '__main__':
    main()
