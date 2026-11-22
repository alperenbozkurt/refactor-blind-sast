"""Interactive command-line tool for compressing files with gzip."""

import os
import subprocess
import sys
from datetime import datetime


class FileCompressor:
    """Compress individual files into gzip archives in an output directory."""

    def __init__(self, output_dir='compressed'):
        self.output_dir = output_dir
        self.create_output_dir()

    def create_output_dir(self):
        """Create the output directory if it does not already exist."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def get_timestamp(self):
        """Return the current time formatted for use in output filenames."""
        return datetime.now().strftime('%Y%m%d_%H%M%S')

    def validate_filename(self, filename):
        """Ensure that ``filename`` points to an existing regular file."""
        if not os.path.exists(filename):
            raise ValueError(f'File {filename} does not exist')
        if not os.path.isfile(filename):
            raise ValueError(f'{filename} is not a regular file')

    def compress_file(self, filename, compression_level=9):
        """Compress ``filename`` with gzip and return the archive path."""
        self.validate_filename(filename)
        output_name = f'{os.path.basename(filename)}_compressed_{self.get_timestamp()}'
        output_path = os.path.join(self.output_dir, output_name)
        archive_path = f'{output_path}.gz'
        command = ['gzip', f'-{compression_level}', '-c', filename]
        try:
            with open(archive_path, 'wb') as out_file:
                subprocess.run(command, stdout=out_file, stderr=subprocess.PIPE, check=True)
            print(f'File compressed and saved to {archive_path}')
            return archive_path
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Compression failed: {e.stderr.decode().strip()}')
        except Exception as e:
            raise RuntimeError(f'Error during compression: {str(e)}')

    def list_compressed_files(self):
        """Return the names of all ``.gz`` files in the output directory."""
        return [f for f in os.listdir(self.output_dir) if f.endswith('.gz')]


def print_menu():
    """Display the available menu options."""
    print('\nFile Compressor Menu:')
    print('1. Compress file')
    print('2. List compressed files')
    print('3. Exit')


def main():
    """Run the interactive compressor menu loop."""
    compressor = FileCompressor()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '1':
            filename = input('Enter file path to compress: ')
            level = input('Compression level (1-9, default 9): ') or '9'
            try:
                compressor.compress_file(filename, int(level))
            except Exception as e:
                print(f'Error: {e}')
        elif choice == '2':
            files = compressor.list_compressed_files()
            print('Compressed files:')
            for f in files:
                print(f'- {f}')
        elif choice == '3':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
