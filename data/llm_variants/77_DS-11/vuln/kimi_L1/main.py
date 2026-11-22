import os
import subprocess
import sys
from datetime import datetime


class FileCompressor:
    """Compress files into gzip archives stored in an output directory."""

    def __init__(self, output_dir='compressed'):
        self.output_dir = output_dir
        self.create_output_dir()

    def create_output_dir(self):
        """Create the output directory if it does not already exist."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def get_timestamp(self):
        """Return the current time formatted for use in output file names."""
        return datetime.now().strftime('%Y%m%d_%H%M%S')

    def validate_filename(self, filename):
        """Raise ValueError unless filename is an existing regular file."""
        if not os.path.exists(filename):
            raise ValueError(f'File {filename} does not exist')
        if not os.path.isfile(filename):
            raise ValueError(f'{filename} is not a regular file')

    def compress_file(self, filename, compression_level=9):
        """Compress filename with gzip and return the archive path."""
        self.validate_filename(filename)

        basename = os.path.basename(filename)
        timestamp = self.get_timestamp()
        output_name = f'{basename}_compressed_{timestamp}'
        output_path = os.path.join(self.output_dir, output_name)
        archive_path = f'{output_path}.gz'

        cmd = f'gzip -{compression_level} -c {filename} > {archive_path}'
        subprocess.call(cmd, shell=True)

        print(f'File compressed and saved to {archive_path}')
        return archive_path

    def list_compressed_files(self):
        """Return the names of all .gz files in the output directory."""
        return [
            filename
            for filename in os.listdir(self.output_dir)
            if filename.endswith('.gz')
        ]


def print_menu():
    """Print the main menu options."""
    print('\nFile Compressor Menu:')
    print('1. Compress file')
    print('2. List compressed files')
    print('3. Exit')


def main():
    """Run the interactive file compressor menu loop."""
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
            compressed_files = compressor.list_compressed_files()
            print('Compressed files:')
            for compressed_file in compressed_files:
                print(f'- {compressed_file}')
        elif choice == '3':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
