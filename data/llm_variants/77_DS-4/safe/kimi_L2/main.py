import argparse
import os
import subprocess
import sys
import time
from typing import Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

BACKUP_DIR = 'backups'
BACKUP_FILE_SUFFIX = '.sql'
BACKUP_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

PG_DUMP_BIN = 'pg_dump'
PSQL_BIN = 'psql'

CMD_BACKUP = 'backup'
CMD_LIST = 'list'
CMD_RESTORE = 'restore'
CMD_DELETE = 'delete'


# ---------------------------------------------------------------------------
# Small pure helper functions
# ---------------------------------------------------------------------------

def _current_timestamp() -> str:
    """Return the timestamp string used when naming new backup files."""
    return time.strftime(BACKUP_TIMESTAMP_FORMAT)


def _new_backup_filename(db_name: str) -> str:
    """Build the file name for a new backup of the given database."""
    return f'{db_name}_{_current_timestamp()}{BACKUP_FILE_SUFFIX}'


def _is_valid_table_name(table: str) -> bool:
    """A valid table name is alphanumeric (underscores allowed)."""
    return table.replace('_', '').isalnum()


def _validate_table_names(tables: List[str]) -> None:
    """Raise ValueError on the first invalid table name."""
    for table in tables:
        if not _is_valid_table_name(table):
            raise ValueError(f'Invalid table name: {table}')


def _print_error(prefix: str, error: Exception) -> None:
    """Report an operational error on stderr."""
    print(f'{prefix}: {error}', file=sys.stderr)


def _report_result(action: str, success: bool) -> None:
    """Print the standard '<action> completed/failed' result message."""
    print(f'{action} completed' if success else f'{action} failed')


class DatabaseManager:

    def __init__(self, db_name: str, db_user: str):
        self.db_name = db_name
        self.db_user = db_user
        self.backup_dir = BACKUP_DIR
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self, tables: Optional[List[str]]=None) -> bool:
        backup_file = self._backup_path(_new_backup_filename(self.db_name))
        try:
            cmd = self._build_dump_command(backup_file, tables)
            subprocess.run(cmd, check=True)
            return os.path.exists(backup_file)
        except subprocess.CalledProcessError as e:
            _print_error('Backup failed', e)
            return False
        except ValueError as e:
            _print_error('Validation error', e)
            return False

    def list_backups(self) -> List[str]:
        return sorted(
            f for f in os.listdir(self.backup_dir) if self._is_backup_file(f)
        )

    def restore_backup(self, backup_file: str) -> bool:
        if backup_file not in self.list_backups():
            return False
        try:
            subprocess.run(self._build_restore_command(backup_file), check=True)
            return True
        except subprocess.CalledProcessError as e:
            _print_error('Restore failed', e)
            return False

    def delete_backup(self, backup_file: str) -> bool:
        if backup_file not in self.list_backups():
            return False
        try:
            os.remove(self._backup_path(backup_file))
            return True
        except OSError as e:
            _print_error('Delete failed', e)
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _backup_path(self, backup_file: str) -> str:
        """Resolve a backup file name to its full path."""
        return os.path.join(self.backup_dir, backup_file)

    def _is_backup_file(self, filename: str) -> bool:
        """Check whether a directory entry is a backup of this database."""
        return (
            filename.startswith(self.db_name)
            and filename.endswith(BACKUP_FILE_SUFFIX)
        )

    def _build_dump_command(
        self, backup_file: str, tables: Optional[List[str]]
    ) -> List[str]:
        """Assemble the pg_dump command line, validating table names."""
        cmd = [
            PG_DUMP_BIN,
            '-U', self.db_user,
            '-d', self.db_name,
            '-f', backup_file,
        ]
        if tables:
            _validate_table_names(tables)
            cmd.extend(['-t'] + tables)
        return cmd

    def _build_restore_command(self, backup_file: str) -> List[str]:
        """Assemble the psql command line for a restore operation."""
        return [
            PSQL_BIN,
            '-U', self.db_user,
            '-d', self.db_name,
            '-f', self._backup_path(backup_file),
        ]


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for the backup utility."""
    parser = argparse.ArgumentParser(description='Database Backup Utility')
    parser.add_argument('--db', required=True, help='Database name')
    parser.add_argument('--user', required=True, help='Database user')

    subparsers = parser.add_subparsers(dest='command', required=True)

    backup_parser = subparsers.add_parser(CMD_BACKUP)
    backup_parser.add_argument('--tables', nargs='+',
                               help='Specific tables to backup')

    subparsers.add_parser(CMD_LIST)

    restore_parser = subparsers.add_parser(CMD_RESTORE)
    restore_parser.add_argument('file', help='Backup file to restore')

    delete_parser = subparsers.add_parser(CMD_DELETE)
    delete_parser.add_argument('file', help='Backup file to delete')

    return parser


def _handle_backup(manager: DatabaseManager, args: argparse.Namespace) -> None:
    _report_result('Backup', manager.create_backup(args.tables))


def _handle_list(manager: DatabaseManager, args: argparse.Namespace) -> None:
    print('\n'.join(manager.list_backups()))


def _handle_restore(manager: DatabaseManager, args: argparse.Namespace) -> None:
    _report_result('Restore', manager.restore_backup(args.file))


def _handle_delete(manager: DatabaseManager, args: argparse.Namespace) -> None:
    _report_result('Delete', manager.delete_backup(args.file))


_COMMAND_HANDLERS: Dict[
    str, Callable[[DatabaseManager, argparse.Namespace], None]
] = {
    CMD_BACKUP: _handle_backup,
    CMD_LIST: _handle_list,
    CMD_RESTORE: _handle_restore,
    CMD_DELETE: _handle_delete,
}


def main():
    args = _build_parser().parse_args()
    manager = DatabaseManager(args.db, args.user)
    _COMMAND_HANDLERS[args.command](manager, args)


if __name__ == '__main__':
    main()
