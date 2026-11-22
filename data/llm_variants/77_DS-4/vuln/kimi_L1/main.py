"""Database backup utility.

A small command-line wrapper around ``pg_dump`` and ``psql`` for creating,
listing, restoring and deleting SQL backups of a PostgreSQL database.
"""

import argparse
import os
import subprocess
import sys
import time
from typing import List, Optional


class DatabaseManager:
    """Manage SQL backup files for a single PostgreSQL database."""

    BACKUP_DIR = 'backups'
    BACKUP_EXTENSION = '.sql'
    TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

    def __init__(self, db_name: str, db_user: str):
        self.db_name = db_name
        self.db_user = db_user
        self.backup_dir = self.BACKUP_DIR
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self, tables: Optional[List[str]] = None) -> bool:
        """Create a timestamped SQL dump, optionally limited to ``tables``."""
        timestamp = time.strftime(self.TIMESTAMP_FORMAT)
        backup_name = f'{self.db_name}_{timestamp}{self.BACKUP_EXTENSION}'
        backup_file = self._backup_path(backup_name)
        command = self._build_dump_command(backup_file, tables)
        if not self._run_command(command, 'Backup'):
            return False
        return os.path.exists(backup_file)

    def list_backups(self) -> List[str]:
        """Return the sorted file names of all backups for this database."""
        return sorted(
            filename
            for filename in os.listdir(self.backup_dir)
            if self._is_backup_file(filename)
        )

    def restore_backup(self, backup_file: str) -> bool:
        """Restore an existing backup file into the database."""
        if backup_file not in self.list_backups():
            return False
        command = (
            f'psql -U {self.db_user} -d {self.db_name} '
            f'-f {self._backup_path(backup_file)}'
        )
        return self._run_command(command, 'Restore')

    def delete_backup(self, backup_file: str) -> bool:
        """Delete an existing backup file."""
        if backup_file not in self.list_backups():
            return False
        try:
            os.remove(self._backup_path(backup_file))
            return True
        except OSError as error:
            print(f'Delete failed: {error}', file=sys.stderr)
            return False

    def _backup_path(self, backup_file: str) -> str:
        return os.path.join(self.backup_dir, backup_file)

    def _is_backup_file(self, filename: str) -> bool:
        return (
            filename.startswith(self.db_name)
            and filename.endswith(self.BACKUP_EXTENSION)
        )

    def _build_dump_command(
        self, backup_file: str, tables: Optional[List[str]]
    ) -> str:
        command = f'pg_dump -U {self.db_user} -d {self.db_name}'
        if tables:
            command += f' -t {" ".join(tables)}'
        return f'{command} > {backup_file}'

    @staticmethod
    def _run_command(command: str, action: str) -> bool:
        try:
            subprocess.run(command, shell=True, check=True)
            return True
        except subprocess.CalledProcessError as error:
            print(f'{action} failed: {error}', file=sys.stderr)
            return False


def main():
    parser = _build_parser()
    args = parser.parse_args()
    manager = DatabaseManager(args.db, args.user)

    if args.command == 'backup':
        _print_result(manager.create_backup(args.tables), 'Backup')
    elif args.command == 'list':
        print('\n'.join(manager.list_backups()))
    elif args.command == 'restore':
        _print_result(manager.restore_backup(args.file), 'Restore')
    elif args.command == 'delete':
        _print_result(manager.delete_backup(args.file), 'Delete')


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Database Backup Utility')
    parser.add_argument('--db', required=True, help='Database name')
    parser.add_argument('--user', required=True, help='Database user')

    subparsers = parser.add_subparsers(dest='command', required=True)

    backup_parser = subparsers.add_parser('backup')
    backup_parser.add_argument(
        '--tables', nargs='+', help='Specific tables to backup'
    )

    subparsers.add_parser('list')

    restore_parser = subparsers.add_parser('restore')
    restore_parser.add_argument('file', help='Backup file to restore')

    delete_parser = subparsers.add_parser('delete')
    delete_parser.add_argument('file', help='Backup file to delete')

    return parser


def _print_result(success: bool, action: str) -> None:
    print(f'{action} completed' if success else f'{action} failed')


if __name__ == '__main__':
    main()
