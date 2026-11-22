"""Interactive command-line tool for creating and managing database backups."""

import os
import subprocess
import sys
import time
from datetime import datetime


class DatabaseBackupTool:
    """Create, list, and clean up database backups.

    Supports MySQL, PostgreSQL, and MongoDB. Backups are written to a
    configurable local directory.
    """

    def __init__(self, backup_dir='backups'):
        self.backup_dir = backup_dir
        self.supported_dbs = ['mysql', 'postgresql', 'mongodb']
        self.create_backup_dir()

    def create_backup_dir(self):
        """Create the backup directory if it does not already exist."""
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)

    def validate_db_type(self, db_type):
        """Raise ValueError if the given database type is not supported."""
        if db_type.lower() not in self.supported_dbs:
            raise ValueError(f'Unsupported database type: {db_type}')

    def generate_backup_name(self, db_type):
        """Return a timestamped backup file name for the given database type."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{db_type}_backup_{timestamp}.sql'

    def create_backup(self, db_type, db_name, db_user, db_password, host='localhost'):
        """Create a backup and return the path of the resulting backup file."""
        self.validate_db_type(db_type)
        backup_file = os.path.join(
            self.backup_dir, self.generate_backup_name(db_type)
        )

        commands = {
            'mysql': (
                f'mysqldump -u {db_user} -p{db_password} '
                f'-h {host} {db_name} > {backup_file}'
            ),
            'postgresql': (
                f'pg_dump -U {db_user} -h {host} {db_name} > {backup_file}'
            ),
        }
        cmd = commands.get(
            db_type,
            f'mongodump --host {host} --username {db_user} '
            f'--password {db_password} --db {db_name} --out {backup_file}',
        )

        subprocess.run(cmd, shell=True, check=True)
        print(f'Backup created at {backup_file}')
        return backup_file

    def list_backups(self):
        """Return the sorted names of all backup files in the backup directory."""
        return sorted(
            filename
            for filename in os.listdir(self.backup_dir)
            if filename.endswith(('.sql', '.gz'))
        )

    def cleanup_old_backups(self, days_to_keep=30):
        """Delete backup files older than the given number of days."""
        seconds_per_day = 86400
        cutoff = time.time() - days_to_keep * seconds_per_day
        for filename in os.listdir(self.backup_dir):
            filepath = os.path.join(self.backup_dir, filename)
            if os.path.getmtime(filepath) < cutoff:
                os.remove(filepath)
                print(f'Removed old backup: {filename}')


def print_menu():
    """Print the main menu of the command-line interface."""
    print('\nDatabase Backup Tool:')
    print('1. Create new backup')
    print('2. List existing backups')
    print('3. Cleanup old backups')
    print('4. Exit')


def main():
    """Run the interactive command-line interface."""
    backup_tool = DatabaseBackupTool()

    def prompt_for_backup():
        db_type = input('Database type (mysql/postgresql/mongodb): ')
        db_name = input('Database name: ')
        db_user = input('Database user: ')
        db_password = input('Database password: ')
        host = input('Host (default localhost): ') or 'localhost'
        try:
            backup_tool.create_backup(db_type, db_name, db_user, db_password, host)
        except Exception as e:
            print(f'Error: {e}')

    def show_backups():
        backups = backup_tool.list_backups()
        print('Available backups:')
        for backup in backups:
            print(f'- {backup}')

    def cleanup_backups():
        days = input('Days to keep (default 30): ') or '30'
        backup_tool.cleanup_old_backups(int(days))

    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '1':
            prompt_for_backup()
        elif choice == '2':
            show_backups()
        elif choice == '3':
            cleanup_backups()
        elif choice == '4':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
