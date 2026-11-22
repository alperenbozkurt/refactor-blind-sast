"""Interactive command-line tool for creating and managing database backups."""

import os
import subprocess
import sys
import time
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DEFAULT_BACKUP_DIR = 'backups'
DEFAULT_HOST = 'localhost'
DEFAULT_DAYS_TO_KEEP = 30

SUPPORTED_DATABASE_TYPES = ['mysql', 'postgresql', 'mongodb']
BACKUP_FILE_EXTENSIONS = ('.sql', '.gz')

TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
BACKUP_FILENAME_TEMPLATE = '{db_type}_backup_{timestamp}.sql'

SECONDS_PER_DAY = 86400

CHOICE_CREATE_BACKUP = '1'
CHOICE_LIST_BACKUPS = '2'
CHOICE_CLEANUP_BACKUPS = '3'
CHOICE_EXIT = '4'

MENU_LINES = (
    '\nDatabase Backup Tool:',
    '1. Create new backup',
    '2. List existing backups',
    '3. Cleanup old backups',
    '4. Exit',
)


class DatabaseBackupTool:

    def __init__(self, backup_dir=DEFAULT_BACKUP_DIR):
        self.backup_dir = backup_dir
        self.supported_dbs = list(SUPPORTED_DATABASE_TYPES)
        self.create_backup_dir()

    def create_backup_dir(self):
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)

    def validate_db_type(self, db_type):
        if db_type.lower() not in self.supported_dbs:
            raise ValueError(f'Unsupported database type: {db_type}')

    def generate_backup_name(self, db_type):
        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        return BACKUP_FILENAME_TEMPLATE.format(db_type=db_type, timestamp=timestamp)

    def create_backup(self, db_type, db_name, db_user, db_password, host=DEFAULT_HOST):
        self.validate_db_type(db_type)
        backup_file = os.path.join(self.backup_dir, self.generate_backup_name(db_type))
        try:
            self._run_backup(db_type, backup_file, db_name, db_user, db_password, host)
            print(f'Backup created at {backup_file}')
            return backup_file
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode().strip() if e.stderr else str(e)
            raise RuntimeError(f'Backup failed: {error_msg}')
        except Exception as e:
            raise RuntimeError(f'Error during backup: {str(e)}')

    def list_backups(self):
        return sorted(f for f in os.listdir(self.backup_dir) if self._is_backup_file(f))

    def cleanup_old_backups(self, days_to_keep=DEFAULT_DAYS_TO_KEEP):
        cutoff = time.time() - days_to_keep * SECONDS_PER_DAY
        for filename in os.listdir(self.backup_dir):
            filepath = os.path.join(self.backup_dir, filename)
            if self._is_expired(filepath, cutoff):
                os.remove(filepath)
                print(f'Removed old backup: {filename}')

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_backup(self, db_type, backup_file, db_name, db_user, db_password, host):
        if db_type == 'mysql':
            self._run_mysql_backup(backup_file, db_name, db_user, db_password, host)
        elif db_type == 'postgresql':
            self._run_postgresql_backup(backup_file, db_name, db_user, db_password, host)
        else:
            self._run_mongodb_backup(backup_file, db_name, db_user, db_password, host)

    @staticmethod
    def _run_mysql_backup(backup_file, db_name, db_user, db_password, host):
        with open(backup_file, 'w') as f:
            subprocess.run(
                ['mysqldump', '-u', db_user, f'-p{db_password}', '-h', host, db_name],
                stdout=f, stderr=subprocess.PIPE, check=True,
            )

    @staticmethod
    def _run_postgresql_backup(backup_file, db_name, db_user, db_password, host):
        env = os.environ.copy()
        env['PGPASSWORD'] = db_password
        with open(backup_file, 'w') as f:
            subprocess.run(
                ['pg_dump', '-U', db_user, '-h', host, db_name],
                stdout=f, stderr=subprocess.PIPE, check=True, env=env,
            )

    @staticmethod
    def _run_mongodb_backup(backup_file, db_name, db_user, db_password, host):
        subprocess.run(
            ['mongodump', '--host', host, '--username', db_user, '--password', db_password,
             '--db', db_name, '--out', backup_file],
            stderr=subprocess.PIPE, check=True,
        )

    @staticmethod
    def _is_backup_file(filename):
        return filename.endswith(BACKUP_FILE_EXTENSIONS)

    @staticmethod
    def _is_expired(filepath, cutoff):
        return os.path.getmtime(filepath) < cutoff


def print_menu():
    for line in MENU_LINES:
        print(line)


# ---------------------------------------------------------------------------
# CLI handlers
# ---------------------------------------------------------------------------

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


def _handle_cleanup_backups(backup_tool):
    days = input('Days to keep (default 30): ') or str(DEFAULT_DAYS_TO_KEEP)
    backup_tool.cleanup_old_backups(int(days))


def main():
    backup_tool = DatabaseBackupTool()
    handlers = {
        CHOICE_CREATE_BACKUP: _handle_create_backup,
        CHOICE_LIST_BACKUPS: _handle_list_backups,
        CHOICE_CLEANUP_BACKUPS: _handle_cleanup_backups,
    }
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == CHOICE_EXIT:
            print('Exiting...')
            break
        handler = handlers.get(choice)
        if handler is None:
            print('Invalid choice. Please try again.')
        else:
            handler(backup_tool)


if __name__ == '__main__':
    main()
