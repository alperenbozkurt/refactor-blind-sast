import os
import subprocess
import sys
import time
from datetime import datetime

DEFAULT_BACKUP_DIR = 'backups'
DEFAULT_HOST = 'localhost'
DEFAULT_DAYS_TO_KEEP = 30
SECONDS_PER_DAY = 86400
SUPPORTED_DATABASES = ('mysql', 'postgresql', 'mongodb')
BACKUP_EXTENSIONS = ('.sql', '.gz')
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
BACKUP_FILE_EXTENSION = 'sql'

DB_MYSQL = 'mysql'
DB_POSTGRESQL = 'postgresql'

MENU_TITLE = '\nDatabase Backup Tool:'
MENU_OPTIONS = (
    '1. Create new backup',
    '2. List existing backups',
    '3. Cleanup old backups',
    '4. Exit',
)

CHOICE_CREATE = '1'
CHOICE_LIST = '2'
CHOICE_CLEANUP = '3'
CHOICE_EXIT = '4'


def _build_mysql_command(db_user, db_password, host, db_name):
    return ['mysqldump', '-u', db_user, f'-p{db_password}', '-h', host, db_name]


def _build_postgresql_command(db_user, host, db_name):
    return ['pg_dump', '-U', db_user, '-h', host, db_name]


def _build_mongodb_command(db_user, db_password, host, db_name, output_path):
    return [
        'mongodump',
        '--host', host,
        '--username', db_user,
        '--password', db_password,
        '--db', db_name,
        '--out', output_path,
    ]


def _run_dump_to_file(command, backup_file, env=None):
    """Run a dump command, streaming stdout into backup_file."""
    with open(backup_file, 'w') as f:
        kwargs = {'stdout': f, 'stderr': subprocess.PIPE, 'check': True}
        if env is not None:
            kwargs['env'] = env
        subprocess.run(command, **kwargs)


def _extract_error_message(error):
    return error.stderr.decode().strip() if error.stderr else str(error)


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
        return f'{db_type}_backup_{timestamp}.{BACKUP_FILE_EXTENSION}'

    def _backup_mysql(self, backup_file, db_name, db_user, db_password, host):
        command = _build_mysql_command(db_user, db_password, host, db_name)
        _run_dump_to_file(command, backup_file)

    def _backup_postgresql(self, backup_file, db_name, db_user, db_password, host):
        env = os.environ.copy()
        env['PGPASSWORD'] = db_password
        command = _build_postgresql_command(db_user, host, db_name)
        _run_dump_to_file(command, backup_file, env=env)

    def _backup_mongodb(self, backup_file, db_name, db_user, db_password, host):
        command = _build_mongodb_command(db_user, db_password, host, db_name, backup_file)
        subprocess.run(command, stderr=subprocess.PIPE, check=True)

    def _dispatch_backup(self, db_type, backup_file, db_name, db_user, db_password, host):
        if db_type == DB_MYSQL:
            self._backup_mysql(backup_file, db_name, db_user, db_password, host)
        elif db_type == DB_POSTGRESQL:
            self._backup_postgresql(backup_file, db_name, db_user, db_password, host)
        else:
            self._backup_mongodb(backup_file, db_name, db_user, db_password, host)

    def create_backup(self, db_type, db_name, db_user, db_password, host=DEFAULT_HOST):
        self.validate_db_type(db_type)
        backup_file = os.path.join(self.backup_dir, self.generate_backup_name(db_type))
        try:
            self._dispatch_backup(db_type, backup_file, db_name, db_user, db_password, host)
            print(f'Backup created at {backup_file}')
            return backup_file
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Backup failed: {_extract_error_message(e)}')
        except Exception as e:
            raise RuntimeError(f'Error during backup: {str(e)}')

    def list_backups(self):
        return sorted(
            [f for f in os.listdir(self.backup_dir) if f.endswith(BACKUP_EXTENSIONS)]
        )

    def cleanup_old_backups(self, days_to_keep=DEFAULT_DAYS_TO_KEEP):
        cutoff = time.time() - days_to_keep * SECONDS_PER_DAY
        for filename in os.listdir(self.backup_dir):
            filepath = os.path.join(self.backup_dir, filename)
            if os.path.getmtime(filepath) < cutoff:
                os.remove(filepath)
                print(f'Removed old backup: {filename}')


def print_menu():
    print(MENU_TITLE)
    for option in MENU_OPTIONS:
        print(option)


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
        if choice == CHOICE_CREATE:
            _handle_create_backup(backup_tool)
        elif choice == CHOICE_LIST:
            _handle_list_backups(backup_tool)
        elif choice == CHOICE_CLEANUP:
            _handle_cleanup(backup_tool)
        elif choice == CHOICE_EXIT:
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
