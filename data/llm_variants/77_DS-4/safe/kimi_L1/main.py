"""Database backup utility.

Command-line tool for creating, listing, restoring, and deleting
PostgreSQL backups using pg_dump and psql.
"""

import argparse
import os
import subprocess
import sys
import time
from typing import List, Optional


class DatabaseManager:
    """Manage backup files for a single PostgreSQL database."""

    def __init__(self, db_name: str, db_user: str):
        self.db_name = db_name
        self.db_user = db_user
        self.backup_dir = 'backups'
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self, tables: Optional[List[str]] = None) -> bool:
        """Create a backup of the database, optionally limited to the given tables.

        Returns True if the backup file was created, False otherwise.
        """
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(self.backup_dir, f'{self.db_name}_{timestamp}.sql')
        try:
            command = ['pg_dump', '-U', self.db_user, '-d', self.db_name, '-f', backup_file]
            if tables:
                for table in tables:
                    if not table.replace('_', '').isalnum():
                        raise ValueError(f'Invalid table name: {table}')
                command.extend(['-t'] + tables)
            subprocess.run(command, check=True)
            return os.path.exists(backup_file)
        except subprocess.CalledProcessError as e:
            print(f'Backup failed: {e}', file=sys.stderr)
            return False
        except ValueError as e:
            print(f'Validation error: {e}', file=sys.stderr)
            return False

    def list_backups(self) -> List[str]:
        """Return the sorted names of this database's backup files."""
        return sorted(
            filename
            for filename in os.listdir(self.backup_dir)
            if filename.startswith(self.db_name) and filename.endswith('.sql')
        )

    def restore_backup(self, backup_file: str) -> bool:
        """Restore the database from one of the known backup files."""
        if backup_file not in self.list_backups():
            return False
        try:
            backup_path = os.path.join(self.backup_dir, backup_file)
            command = ['psql', '-U', self.db_user, '-d', self.db_name, '-f', backup_path]
            subprocess.run(command, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f'Restore failed: {e}', file=sys.stderr)
            return False

    def delete_backup(self, backup_file: str) -> bool:
        """Delete one of the known backup files."""
        if backup_file not in self.list_backups():
            return False
        try:
            os.remove(os.path.join(self.backup_dir, backup_file))
            return True
        except OSError as e:
            print(f'Delete failed: {e}', file=sys.stderr)
            return False


def main():
    """Parse command-line arguments and run the requested operation."""
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

    if args.command == 'backup':
        success = manager.create_backup(args.tables)
        print('Backup completed' if success else 'Backup failed')
    elif args.command == 'list':
        print('\n'.join(manager.list_backups()))
    elif args.command == 'restore':
        success = manager.restore_backup(args.file)
        print('Restore completed' if success else 'Restore failed')
    elif args.command == 'delete':
        success = manager.delete_backup(args.file)
        print('Delete completed' if success else 'Delete failed')


if __name__ == '__main__':
    main()
