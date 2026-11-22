import argparse
import os
import subprocess
import sys
import time
from typing import List, Optional


class DatabaseManager:
    """Manage PostgreSQL backups stored as plain SQL files."""

    _TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

    def __init__(self, db_name: str, db_user: str):
        self.db_name = db_name
        self.db_user = db_user
        self.backup_dir = 'backups'
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self, tables: Optional[List[str]] = None) -> bool:
        backup_file = os.path.join(self.backup_dir, self._backup_filename())
        if not self._run_command(self._dump_command(backup_file, tables), 'Backup'):
            return False
        return os.path.exists(backup_file)

    def list_backups(self) -> List[str]:
        return sorted(
            filename
            for filename in os.listdir(self.backup_dir)
            if filename.startswith(self.db_name) and filename.endswith('.sql')
        )

    def restore_backup(self, backup_file: str) -> bool:
        if not self._has_backup(backup_file):
            return False
        command = (
            f'psql -U {self.db_user} -d {self.db_name} '
            f'-f {self._backup_path(backup_file)}'
        )
        return self._run_command(command, 'Restore')

    def delete_backup(self, backup_file: str) -> bool:
        if not self._has_backup(backup_file):
            return False
        try:
            os.remove(self._backup_path(backup_file))
            return True
        except OSError as e:
            print(f'Delete failed: {e}', file=sys.stderr)
            return False

    def _backup_filename(self) -> str:
        timestamp = time.strftime(self._TIMESTAMP_FORMAT)
        return f'{self.db_name}_{timestamp}.sql'

    def _dump_command(self, backup_file: str, tables: Optional[List[str]]) -> str:
        command = f'pg_dump -U {self.db_user} -d {self.db_name}'
        if tables:
            command += f" -t {' '.join(tables)}"
        return f'{command} > {backup_file}'

    def _backup_path(self, backup_file: str) -> str:
        return os.path.join(self.backup_dir, backup_file)

    def _has_backup(self, backup_file: str) -> bool:
        return backup_file in self.list_backups()

    @staticmethod
    def _run_command(command: str, action: str) -> bool:
        try:
            subprocess.run(command, shell=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f'{action} failed: {e}', file=sys.stderr)
            return False


def main():
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

    args = parser.parse_args()
    manager = DatabaseManager(args.db, args.user)

    if args.command == 'list':
        print('\n'.join(manager.list_backups()))
        return

    operations = {
        'backup': lambda: manager.create_backup(args.tables),
        'restore': lambda: manager.restore_backup(args.file),
        'delete': lambda: manager.delete_backup(args.file),
    }
    success = operations[args.command]()
    action = args.command.capitalize()
    print(f'{action} completed' if success else f'{action} failed')


if __name__ == '__main__':
    main()
