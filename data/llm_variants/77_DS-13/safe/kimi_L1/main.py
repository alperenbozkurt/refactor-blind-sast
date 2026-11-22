import os
import subprocess
import sys
import time
from datetime import datetime


class DatabaseBackupTool:
    """Create, list, and clean up database backups."""

    def __init__(self, backup_dir='backups'):
        self.backup_dir = backup_dir
        self.supported_dbs = ['mysql', 'postgresql', 'mongodb']
        self.create_backup_dir()

    def create_backup_dir(self):
        """Ensure the backup directory exists."""
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)

    def validate_db_type(self, db_type):
        """Raise ValueError if the given database type is not supported."""
        if db_type.lower() not in self.supported_dbs:
            raise ValueError(f'Unsupported database type: {db_type}')

    def generate_backup_name(self, db_type):
        """Build a timestamped backup file name for the given database type."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{db_type}_backup_{timestamp}.sql'

    def create_backup(self, db_type, db_name, db_user, db_password, host='localhost'):
        """Create a backup of the given database and return the backup path."""
        self.validate_db_type(db_type)
        backup_file = os.path.join(self.backup_dir, self.generate_backup_name(db_type))
        try:
            if db_type == 'mysql':
                self._create_mysql_backup(backup_file, db_name, db_user, db_password, host)
            elif db_type == 'postgresql':
                self._create_postgresql_backup(backup_file, db_name, db_user, db_password, host)
            else:
                self._create_mongodb_backup(backup_file, db_name, db_user, db_password, host)
            print(f'Backup created at {backup_file}')
            return backup_file
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode().strip() if e.stderr else str(e)
            raise RuntimeError(f'Backup failed: {error_msg}')
        except Exception as e:
            raise RuntimeError(f'Error during backup: {str(e)}')

    def _create_mysql_backup(self, backup_file, db_name, db_user, db_password, host):
        """Run mysqldump and write the dump to the backup file."""
        command = ['mysqldump', '-u', db_user, f'-p{db_password}', '-h', host, db_name]
        with open(backup_file, 'w') as output_file:
            subprocess.run(command, stdout=output_file, stderr=subprocess.PIPE, check=True)

    def _create_postgresql_backup(self, backup_file, db_name, db_user, db_password, host):
        """Run pg_dump with PGPASSWORD set and write the dump to the backup file."""
        env = os.environ.copy()
        env['PGPASSWORD'] = db_password
        command = ['pg_dump', '-U', db_user, '-h', host, db_name]
        with open(backup_file, 'w') as output_file:
            subprocess.run(command, stdout=output_file, stderr=subprocess.PIPE, check=True, env=env)

    def _create_mongodb_backup(self, backup_file, db_name, db_user, db_password, host):
        """Run mongodump with the backup file path as the output location."""
        command = [
            'mongodump',
            '--host', host,
            '--username', db_user,
            '--password', db_password,
            '--db', db_name,
            '--out', backup_file,
        ]
        subprocess.run(command, stderr=subprocess.PIPE, check=True)

    def list_backups(self):
        """Return a sorted list of backup file names in the backup directory."""
        return sorted(
            filename
            for filename in os.listdir(self.backup_dir)
            if filename.endswith(('.sql', '.gz'))
        )

    def cleanup_old_backups(self, days_to_keep=30):
        """Remove backups whose modification time is older than the cutoff."""
        seconds_per_day = 86400
        cutoff = time.time() - days_to_keep * seconds_per_day
        for filename in os.listdir(self.backup_dir):
            filepath = os.path.join(self.backup_dir, filename)
            if os.path.getmtime(filepath) < cutoff:
                os.remove(filepath)
                print(f'Removed old backup: {filename}')


def print_menu():
    """Display the main menu options."""
    print('\nDatabase Backup Tool:')
    print('1. Create new backup')
    print('2. List existing backups')
    print('3. Cleanup old backups')
    print('4. Exit')


def main():
    """Run the interactive command-line menu loop."""
    backup_tool = DatabaseBackupTool()

    def handle_create_backup():
        db_type = input('Database type (mysql/postgresql/mongodb): ')
        db_name = input('Database name: ')
        db_user = input('Database user: ')
        db_password = input('Database password: ')
        host = input('Host (default localhost): ') or 'localhost'
        try:
            backup_tool.create_backup(db_type, db_name, db_user, db_password, host)
        except Exception as e:
            print(f'Error: {e}')

    def handle_list_backups():
        backups = backup_tool.list_backups()
        print('Available backups:')
        for backup in backups:
            print(f'- {backup}')

    def handle_cleanup_backups():
        days = input('Days to keep (default 30): ') or '30'
        backup_tool.cleanup_old_backups(int(days))

    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '1':
            handle_create_backup()
        elif choice == '2':
            handle_list_backups()
        elif choice == '3':
            handle_cleanup_backups()
        elif choice == '4':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
