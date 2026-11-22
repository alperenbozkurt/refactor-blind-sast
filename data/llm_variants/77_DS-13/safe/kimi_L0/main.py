import os
import subprocess
import time
from datetime import datetime

MENU_TEXT = (
    '\nDatabase Backup Tool:\n'
    '1. Create new backup\n'
    '2. List existing backups\n'
    '3. Cleanup old backups\n'
    '4. Exit'
)


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

    def create_backup(self, db_type, db_name, db_user, db_password, host='localhost'):
        self.validate_db_type(db_type)
        backup_file = os.path.join(self.backup_dir, self.generate_backup_name(db_type))
        backup_handlers = {
            'mysql': self._backup_mysql,
            'postgresql': self._backup_postgresql,
        }
        handler = backup_handlers.get(db_type, self._backup_mongodb)
        try:
            handler(db_name, db_user, db_password, host, backup_file)
            print(f'Backup created at {backup_file}')
            return backup_file
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode().strip() if e.stderr else str(e)
            raise RuntimeError(f'Backup failed: {error_msg}')
        except Exception as e:
            raise RuntimeError(f'Error during backup: {str(e)}')

    def _backup_mysql(self, db_name, db_user, db_password, host, backup_file):
        command = ['mysqldump', '-u', db_user, f'-p{db_password}', '-h', host, db_name]
        self._run_sql_dump(command, backup_file)

    def _backup_postgresql(self, db_name, db_user, db_password, host, backup_file):
        env = os.environ.copy()
        env['PGPASSWORD'] = db_password
        command = ['pg_dump', '-U', db_user, '-h', host, db_name]
        self._run_sql_dump(command, backup_file, env=env)

    def _backup_mongodb(self, db_name, db_user, db_password, host, backup_file):
        command = [
            'mongodump', '--host', host,
            '--username', db_user, '--password', db_password,
            '--db', db_name, '--out', backup_file,
        ]
        subprocess.run(command, stderr=subprocess.PIPE, check=True)

    @staticmethod
    def _run_sql_dump(command, backup_file, env=None):
        with open(backup_file, 'w') as dump_file:
            subprocess.run(command, stdout=dump_file, stderr=subprocess.PIPE, check=True, env=env)

    def list_backups(self):
        return sorted(
            f for f in os.listdir(self.backup_dir)
            if f.endswith(('.sql', '.gz'))
        )

    def cleanup_old_backups(self, days_to_keep=30):
        cutoff = time.time() - days_to_keep * 86400
        for filename in os.listdir(self.backup_dir):
            filepath = os.path.join(self.backup_dir, filename)
            if os.path.getmtime(filepath) < cutoff:
                os.remove(filepath)
                print(f'Removed old backup: {filename}')


def print_menu():
    print(MENU_TEXT)


def _create_backup(backup_tool):
    db_type = input('Database type (mysql/postgresql/mongodb): ')
    db_name = input('Database name: ')
    db_user = input('Database user: ')
    db_password = input('Database password: ')
    host = input('Host (default localhost): ') or 'localhost'
    try:
        backup_tool.create_backup(db_type, db_name, db_user, db_password, host)
    except Exception as e:
        print(f'Error: {e}')


def _list_backups(backup_tool):
    print('Available backups:')
    for backup in backup_tool.list_backups():
        print(f'- {backup}')


def _cleanup_old_backups(backup_tool):
    days = input('Days to keep (default 30): ') or '30'
    backup_tool.cleanup_old_backups(int(days))


def main():
    backup_tool = DatabaseBackupTool()
    menu_handlers = {
        '1': _create_backup,
        '2': _list_backups,
        '3': _cleanup_old_backups,
    }
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '4':
            print('Exiting...')
            break
        handler = menu_handlers.get(choice)
        if handler is None:
            print('Invalid choice. Please try again.')
        else:
            handler(backup_tool)


if __name__ == '__main__':
    main()
