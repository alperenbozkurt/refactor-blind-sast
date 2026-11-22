import os
import subprocess
import sys
import time
from datetime import datetime

SECONDS_PER_DAY = 86400
BACKUP_EXTENSIONS = ('.sql', '.gz')
DEFAULT_HOST = 'localhost'
DEFAULT_DAYS_TO_KEEP = 30


class DatabaseBackupTool:

    def __init__(self, backup_dir='backups'):
        self.backup_dir = backup_dir
        self.supported_dbs = ['mysql', 'postgresql', 'mongodb']
        self.create_backup_dir()

    def create_backup_dir(self):
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)

    def validate_db_type(self, db_type):
        if db_type.lower() not in self.supported_dbs:
            raise ValueError(f'Unsupported database type: {db_type}')

    def generate_backup_name(self, db_type):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{db_type}_backup_{timestamp}.sql'

    @staticmethod
    def _build_backup_command(db_type, db_name, db_user, db_password, host, backup_file):
        # Note: the command is intentionally built as a shell string, exactly as
        # before, so that behaviour (including output redirection) is unchanged.
        if db_type == 'mysql':
            return f'mysqldump -u {db_user} -p{db_password} -h {host} {db_name} > {backup_file}'
        if db_type == 'postgresql':
            return f'pg_dump -U {db_user} -h {host} {db_name} > {backup_file}'
        return (
            f'mongodump --host {host} --username {db_user} '
            f'--password {db_password} --db {db_name} --out {backup_file}'
        )

    def create_backup(self, db_type, db_name, db_user, db_password, host='localhost'):
        self.validate_db_type(db_type)
        backup_file = os.path.join(self.backup_dir, self.generate_backup_name(db_type))
        cmd = self._build_backup_command(
            db_type, db_name, db_user, db_password, host, backup_file
        )
        subprocess.run(cmd, shell=True, check=True)
        print(f'Backup created at {backup_file}')
        return backup_file

    def list_backups(self):
        return sorted(
            filename for filename in os.listdir(self.backup_dir)
            if filename.endswith(BACKUP_EXTENSIONS)
        )

    def cleanup_old_backups(self, days_to_keep=30):
        cutoff = time.time() - days_to_keep * SECONDS_PER_DAY
        for filename in os.listdir(self.backup_dir):
            filepath = os.path.join(self.backup_dir, filename)
            if os.path.getmtime(filepath) < cutoff:
                os.remove(filepath)
                print(f'Removed old backup: {filename}')


def print_menu():
    print('\nDatabase Backup Tool:')
    print('1. Create new backup')
    print('2. List existing backups')
    print('3. Cleanup old backups')
    print('4. Exit')


def _handle_create_backup(backup_tool):
    db_type = input('Database type (mysql/postgresql/mongodb): ')
    db_name = input('Database name: ')
    db_user = input('Database user: ')
    db_password = input('Database password: ')
    host = input('Host (default localhost): ') or DEFAULT_HOST
    try:
        backup_tool.create_backup(db_type, db_name, db_user, db_password, host)
    except Exception as e:
        print(f'Error: {e}')


def _handle_list_backups(backup_tool):
    backups = backup_tool.list_backups()
    print('Available backups:')
    for backup in backups:
        print(f'- {backup}')


def _handle_cleanup(backup_tool):
    days = input('Days to keep (default 30): ') or str(DEFAULT_DAYS_TO_KEEP)
    backup_tool.cleanup_old_backups(int(days))


def main():
    backup_tool = DatabaseBackupTool()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '1':
            _handle_create_backup(backup_tool)
        elif choice == '2':
            _handle_list_backups(backup_tool)
        elif choice == '3':
            _handle_cleanup(backup_tool)
        elif choice == '4':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
