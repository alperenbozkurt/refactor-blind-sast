"""Interactive command-line database backup tool.

Supports creating, listing and cleaning up backups for MySQL, PostgreSQL
and MongoDB databases.
"""

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

BACKUP_NAME_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
BACKUP_FILE_EXTENSIONS = ('.sql', '.gz')
SECONDS_PER_DAY = 86400

MYSQL_BACKUP_COMMAND_TEMPLATE = (
    'mysqldump -u {db_user} -p{db_password} -h {host} {db_name} > {backup_file}'
)
POSTGRESQL_BACKUP_COMMAND_TEMPLATE = (
    'pg_dump -U {db_user} -h {host} {db_name} > {backup_file}'
)
MONGODB_BACKUP_COMMAND_TEMPLATE = (
    'mongodump --host {host} --username {db_user} '
    '--password {db_password} --db {db_name} --out {backup_file}'
)

# Exact-match templates; any other (already validated) type falls back to
# the default template, mirroring the original if/elif/else dispatch.
BACKUP_COMMAND_TEMPLATES = {
    'mysql': MYSQL_BACKUP_COMMAND_TEMPLATE,
    'postgresql': POSTGRESQL_BACKUP_COMMAND_TEMPLATE,
}
DEFAULT_BACKUP_COMMAND_TEMPLATE = MONGODB_BACKUP_COMMAND_TEMPLATE

MENU_LINES = (
    '\nDatabase Backup Tool:',
    '1. Create new backup',
    '2. List existing backups',
    '3. Cleanup old backups',
    '4. Exit',
)

CHOICE_CREATE_BACKUP = '1'
CHOICE_LIST_BACKUPS = '2'
CHOICE_CLEANUP_BACKUPS = '3'
CHOICE_EXIT = '4'


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _build_backup_command(db_type, db_name, db_user, db_password, host, backup_file):
    """Return the shell command used to back up the given database."""
    template = BACKUP_COMMAND_TEMPLATES.get(db_type, DEFAULT_BACKUP_COMMAND_TEMPLATE)
    return template.format(
        db_name=db_name,
        db_user=db_user,
        db_password=db_password,
        host=host,
        backup_file=backup_file,
    )


def _is_backup_file(filename):
    """Return True if *filename* looks like a generated backup file."""
    return filename.endswith(BACKUP_FILE_EXTENSIONS)


def _is_older_than(filepath, cutoff):
    """Return True if the file at *filepath* was modified before *cutoff*."""
    return os.path.getmtime(filepath) < cutoff


# ---------------------------------------------------------------------------
# Core backup tool
# ---------------------------------------------------------------------------

class DatabaseBackupTool:
    """Create, list and clean up database backups in a backup directory."""

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
        timestamp = datetime.now().strftime(BACKUP_NAME_TIMESTAMP_FORMAT)
        return f'{db_type}_backup_{timestamp}.sql'

    def create_backup(self, db_type, db_name, db_user, db_password, host=DEFAULT_HOST):
        self.validate_db_type(db_type)
        backup_file = os.path.join(self.backup_dir, self.generate_backup_name(db_type))
        cmd = _build_backup_command(db_type, db_name, db_user, db_password, host, backup_file)
        subprocess.run(cmd, shell=True, check=True)
        print(f'Backup created at {backup_file}')
        return backup_file

    def list_backups(self):
        return sorted(f for f in os.listdir(self.backup_dir) if _is_backup_file(f))

    def cleanup_old_backups(self, days_to_keep=DEFAULT_DAYS_TO_KEEP):
        cutoff = time.time() - days_to_keep * SECONDS_PER_DAY
        for filename in os.listdir(self.backup_dir):
            filepath = os.path.join(self.backup_dir, filename)
            if _is_older_than(filepath, cutoff):
                os.remove(filepath)
                print(f'Removed old backup: {filename}')


# ---------------------------------------------------------------------------
# Interactive command-line interface
# ---------------------------------------------------------------------------

def print_menu():
    for line in MENU_LINES:
        print(line)


def _handle_create_backup(backup_tool):
    db_type = input(f"Database type ({'/'.join(SUPPORTED_DATABASE_TYPES)}): ")
    db_name = input('Database name: ')
    db_user = input('Database user: ')
    db_password = input('Database password: ')
    host = input(f'Host (default {DEFAULT_HOST}): ') or DEFAULT_HOST
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
    days = input(f'Days to keep (default {DEFAULT_DAYS_TO_KEEP}): ') or str(DEFAULT_DAYS_TO_KEEP)
    backup_tool.cleanup_old_backups(int(days))


_MENU_HANDLERS = {
    CHOICE_CREATE_BACKUP: _handle_create_backup,
    CHOICE_LIST_BACKUPS: _handle_list_backups,
    CHOICE_CLEANUP_BACKUPS: _handle_cleanup_backups,
}


def main():
    backup_tool = DatabaseBackupTool()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == CHOICE_EXIT:
            print('Exiting...')
            break
        handler = _MENU_HANDLERS.get(choice)
        if handler is None:
            print('Invalid choice. Please try again.')
        else:
            handler(backup_tool)


if __name__ == '__main__':
    main()
