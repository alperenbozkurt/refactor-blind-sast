import argparse
import os
import subprocess
import sys
import time
from typing import List, Optional


class DatabaseManager:
    """Create, list, restore and delete PostgreSQL database backups."""

    def __init__(self, db_name: str, db_user: str):
        self.db_name = db_name
        self.db_user = db_user
        self.backup_dir = 'backups'
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self, tables: Optional[List[str]] = None) -> bool:
        """Dump the database (or the given tables) to a timestamped SQL file."""
        backup_file = self._new_backup_path()
        try:
            cmd = [
                'pg_dump', '-U', self.db_user,
                '-d', self.db_name, '-f', backup_file,
            ]
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
        """Return the sorted names of all backup files for this database."""
        return sorted(
            f
            for f in os.listdir(self.backup_dir)
            if f.startswith(self.db_name) and f.endswith('.sql')
        )

    def restore_backup(self, backup_file: str) -> bool:
        """Restore a previously created backup file into the database."""
        if backup_file not in self.list_backups():
            return False
        try:
            cmd = [
                'psql', '-U', self.db_user,
                '-d', self.db_name, '-f', self._backup_path(backup_file),
            ]
            subprocess.run(cmd, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f'Restore failed: {e}', file=sys.stderr)
            return False

    def delete_backup(self, backup_file: str) -> bool:
        """Delete a previously created backup file."""
        if backup_file not in self.list_backups():
            return False
        try:
            os.remove(self._backup_path(backup_file))
            return True
        except OSError as e:
            print(f'Delete failed: {e}', file=sys.stderr)
            return False

    def _new_backup_path(self) -> str:
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        return os.path.join(self.backup_dir, f'{self.db_name}_{timestamp}.sql')

    def _backup_path(self, backup_file: str) -> str:
        return os.path.join(self.backup_dir, backup_file)

    @staticmethod
    def _validate_table_names(tables: List[str]) -> None:
        for table in tables:
            if not table.replace('_', '').isalnum():
                raise ValueError(f'Invalid table name: {table}')


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


def _print_result(action: str, success: bool) -> None:
    print(f'{action} completed' if success else f'{action} failed')


def main():
    args = _build_parser().parse_args()
    manager = DatabaseManager(args.db, args.user)

    if args.command == 'backup':
        _print_result('Backup', manager.create_backup(args.tables))
    elif args.command == 'list':
        print('\n'.join(manager.list_backups()))
    elif args.command == 'restore':
        _print_result('Restore', manager.restore_backup(args.file))
    elif args.command == 'delete':
        _print_result('Delete', manager.delete_backup(args.file))


if __name__ == '__main__':
    main()
