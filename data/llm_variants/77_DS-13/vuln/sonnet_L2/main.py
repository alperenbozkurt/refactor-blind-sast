import os
import subprocess
import sys
import time
from datetime import datetime

DEFAULT_BACKUP_DIR = 'backups'
DEFAULT_HOST = 'localhost'
DEFAULT_DAYS_TO_KEEP = 30
SECONDS_PER_DAY = 86400
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
BACKUP_EXTENSIONS = ('.sql', '.gz')
SUPPORTED_DATABASES = ('mysql', 'postgresql', 'mongodb')

DB_MYSQL = 'mysql'
DB_POSTGRESQL = 'postgresql'

MENU_CREATE = '1'
MENU_LIST = '2'
MENU_CLEANUP = '3'
MENU_EXIT = '4'

MENU_LINES = (
    '\nDatabase Backup Tool:',
    '1. Create new backup',
    '2. List existing backups',
    '3. Cleanup old backups',
    '4. Exit',
)


def _build_mysql_command(db_user, db_password, host, db_name, backup_file):
    return f'mysqldump -u {db_user} -p{db_password} -h {host} {db_name} > {backup_file}'


def _build_postgresql_command(db_user, db_password, host, db_name, backup_file):
    return f'pg_dump -U {db_user} -h {host} {db_name} > {backup_file}'


def _build_mongodb_command(db_user, db_password, host, db_name, backup_file):
    return (
        f'mongodump --host {host} --username {db_user} --password {db_password} '
        f'--db {db_name} --out {backup_file}'
    )


def _build_backup_command(db_type, db_user, db_password, host, db_name, backup_file):
    """Select the command builder (exact-match on db_type; anything else falls back to mongodb)."""
    if db_type == DB_MYSQL:
        builder = _build_mysql_command
    elif db_type == DB_POSTGRESQL:
        builder = _build_postgresql_command
    else:
        builder = _build_mongodb_command
    return builder(db_user, db_password, host, db_name, backup_file)


def _is_backup_file(filename):
    return filename.endswith(BACKUP_EXTENSIONS)


class DatabaseBackupTool:

    def __init__(self, backup_dir=DEFAULT_BACKUP_DIR):
        self.backup_dir = backup_dir
        self.supported_dbs = list(SUPPORTED_DATABASES)
        self.create_backup_dir()

    def create_backup_dir(self):
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)

    def validate_db_type(self, db_type):
        if db_type.lower() not in self.supported_dbs:
            raise ValueError(f'Unsupported database type: {db_type}')

    def generate_backup_name(self, db_type):
        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        return f'{db_type}_backup_{timestamp}.sql'

    def create_backup(self, db_type, db_name, db_user, db_password, host=DEFAULT_HOST):
        self.validate_db_type(db_type)
        backup_file = os.path.join(self.backup_dir, self.generate_backup_name(db_type))
        cmd = _build_backup_command(db_type, db_user, db_password, host, db_name, backup_file)
        subprocess.run(cmd, shell=True, check=True)
        print(f'Backup created at {backup_file}')
        return backup_file

    def list_backups(self):
        return sorted([f for f in os.listdir(self.backup_dir) if _is_backup_file(f)])

    def cleanup_old_backups(self, days_to_keep=DEFAULT_DAYS_TO_KEEP):
        cutoff = time.time() - days_to_keep * SECONDS_PER_DAY
        for filename in os.listdir(self.backup_dir):
            filepath = os.path.join(self.backup_dir, filename)
            if os.path.getmtime(filepath) < cutoff:
                os.remove(filepath)
                print(f'Removed old backup: {filename}')


def print_menu():
    for line in MENU_LINES:
        print(line)


def _handle_create(backup_tool):
    db_type = input('Database type (mysql/postgresql/mongodb): ')
    db_name = input('Database name: ')
    db_user = input('Database user: ')
    db_password = input('Database password: ')
    host = input('Host (default localhost): ') or DEFAULT_HOST
    try:
        backup_tool.create_backup(db_type, db_name, db_user, db_password, host)
    except Exception as e:
        print(f'Error: {e}')


def _handle_list(backup_tool):
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
        if choice == MENU_CREATE:
            _handle_create(backup_tool)
        elif choice == MENU_LIST:
            _handle_list(backup_tool)
        elif choice == MENU_CLEANUP:
            _handle_cleanup(backup_tool)
        elif choice == MENU_EXIT:
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
