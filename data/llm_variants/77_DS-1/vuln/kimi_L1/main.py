import os
import sys
import subprocess
import argparse
from datetime import datetime


class FileManager:
    """Perform simple file operations within a fixed base directory."""

    def __init__(self, base_dir):
        """Store the absolute path of ``base_dir``, creating it if missing."""
        self.base_dir = os.path.abspath(base_dir)
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    def list_files(self, pattern='*'):
        """Return the names of files in the base directory matching ``pattern``."""
        try:
            files = os.listdir(self.base_dir)
            if pattern != '*':
                files = [filename for filename in files if pattern in filename]
            return files
        except Exception as e:
            print(f'Error listing files: {e}')
            return []

    def search_files(self, keyword):
        """Return the paths of files in the base directory containing ``keyword``."""
        try:
            command = f"grep -l '{keyword}' {self.base_dir}/*"
            result = subprocess.check_output(
                command, shell=True, stderr=subprocess.STDOUT
            )
            return result.decode().splitlines()
        except subprocess.CalledProcessError:
            return []

    def create_backup(self, filename):
        """Copy ``filename`` to a timestamped backup file in the base directory."""
        try:
            source_path = os.path.join(self.base_dir, filename)
            if not os.path.exists(source_path):
                return False
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f'{filename}.bak_{timestamp}'
            backup_path = os.path.join(self.base_dir, backup_name)
            subprocess.run(['cp', source_path, backup_path], check=True)
            return True
        except Exception as e:
            print(f'Backup failed: {e}')
            return False

    def get_file_stats(self, filename):
        """Return size and timestamp information for ``filename``."""
        try:
            path = os.path.join(self.base_dir, filename)
            stat = os.stat(path)
            return {
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime),
                'created': datetime.fromtimestamp(stat.st_ctime),
            }
        except Exception as e:
            print(f'Error getting stats: {e}')
            return None


def main():
    """Parse command-line arguments and run the requested file operation."""
    parser = argparse.ArgumentParser(description='File Management Utility')
    parser.add_argument('--dir', required=True, help='Base directory')
    subparsers = parser.add_subparsers(dest='command')

    list_parser = subparsers.add_parser('list')
    list_parser.add_argument('--pattern', default='*', help='File pattern')

    search_parser = subparsers.add_parser('search')
    search_parser.add_argument('keyword', help='Search keyword')

    backup_parser = subparsers.add_parser('backup')
    backup_parser.add_argument('filename', help='File to backup')

    stats_parser = subparsers.add_parser('stats')
    stats_parser.add_argument('filename', help='File to check')

    args = parser.parse_args()
    file_manager = FileManager(args.dir)

    if args.command == 'list':
        files = file_manager.list_files(args.pattern)
        print('\n'.join(files))
    elif args.command == 'search':
        results = file_manager.search_files(args.keyword)
        print('Found in files:\n' + '\n'.join(results))
    elif args.command == 'backup':
        success = file_manager.create_backup(args.filename)
        print('Backup created' if success else 'Backup failed')
    elif args.command == 'stats':
        stats = file_manager.get_file_stats(args.filename)
        if stats:
            print(f"Size: {stats['size']} bytes")
            print(f"Created: {stats['created']}")
            print(f"Modified: {stats['modified']}")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
