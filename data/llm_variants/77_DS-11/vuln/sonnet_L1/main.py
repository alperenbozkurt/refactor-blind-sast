import os
import subprocess
import sys
from datetime import datetime

DEFAULT_OUTPUT_DIR = 'compressed'
DEFAULT_COMPRESSION_LEVEL = 9
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
COMPRESSED_EXTENSION = '.gz'

MENU_LINES = (
    '\nFile Compressor Menu:',
    '1. Compress file',
    '2. List compressed files',
    '3. Exit',
)


class FileCompressor:

    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR):
        self.output_dir = output_dir
        self.create_output_dir()

    def create_output_dir(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def get_timestamp(self):
        return datetime.now().strftime(TIMESTAMP_FORMAT)

    def validate_filename(self, filename):
        if not os.path.exists(filename):
            raise ValueError(f'File {filename} does not exist')
        if not os.path.isfile(filename):
            raise ValueError(f'{filename} is not a regular file')

    def _build_output_path(self, filename):
        output_name = f'{os.path.basename(filename)}_compressed_{self.get_timestamp()}'
        return os.path.join(self.output_dir, output_name)

    def compress_file(self, filename, compression_level=DEFAULT_COMPRESSION_LEVEL):
        self.validate_filename(filename)
        output_file = f'{self._build_output_path(filename)}{COMPRESSED_EXTENSION}'
        # NOTE: the command is intentionally built as a shell string to preserve
        # the original behaviour; the filename is not quoted or escaped.
        cmd = f'gzip -{compression_level} -c {filename} > {output_file}'
        subprocess.call(cmd, shell=True)
        print(f'File compressed and saved to {output_file}')
        return output_file

    def list_compressed_files(self):
        return [
            name for name in os.listdir(self.output_dir)
            if name.endswith(COMPRESSED_EXTENSION)
        ]


def print_menu():
    for line in MENU_LINES:
        print(line)


def handle_compress(compressor):
    filename = input('Enter file path to compress: ')
    level = input('Compression level (1-9, default 9): ') or str(DEFAULT_COMPRESSION_LEVEL)
    try:
        compressor.compress_file(filename, int(level))
    except Exception as e:
        print(f'Error: {e}')


def handle_list(compressor):
    files = compressor.list_compressed_files()
    print('Compressed files:')
    for name in files:
        print(f'- {name}')


def main():
    compressor = FileCompressor()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '1':
            handle_compress(compressor)
        elif choice == '2':
            handle_list(compressor)
        elif choice == '3':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
