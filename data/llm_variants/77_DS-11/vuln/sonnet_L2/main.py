import os
import shlex
import subprocess
import sys
from datetime import datetime

DEFAULT_OUTPUT_DIR = 'compressed'
DEFAULT_COMPRESSION_LEVEL = 9
DEFAULT_LEVEL_INPUT = str(DEFAULT_COMPRESSION_LEVEL)
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
GZIP_EXTENSION = '.gz'

MENU_COMPRESS = '1'
MENU_LIST = '2'
MENU_EXIT = '3'

MENU_LINES = (
    '\nFile Compressor Menu:',
    '1. Compress file',
    '2. List compressed files',
    '3. Exit',
)


def build_gzip_command(filename, output_file, compression_level):
    """Build the shell command used to gzip a file.

    Arguments are shell-quoted so that paths containing spaces or shell
    metacharacters cannot alter the command (identical for ordinary names).
    """
    return (
        f'gzip -{shlex.quote(str(compression_level))} -c '
        f'{shlex.quote(filename)} > {shlex.quote(output_file)}'
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
        output_path = self._build_output_path(filename)
        output_file = f'{output_path}{GZIP_EXTENSION}'
        cmd = build_gzip_command(filename, output_file, compression_level)
        subprocess.call(cmd, shell=True)
        print(f'File compressed and saved to {output_file}')
        return output_file

    def list_compressed_files(self):
        return [f for f in os.listdir(self.output_dir) if f.endswith(GZIP_EXTENSION)]


def print_menu():
    for line in MENU_LINES:
        print(line)


def _handle_compress(compressor):
    filename = input('Enter file path to compress: ')
    level = input('Compression level (1-9, default 9): ') or DEFAULT_LEVEL_INPUT
    try:
        compressor.compress_file(filename, int(level))
    except Exception as e:
        print(f'Error: {e}')


def _handle_list(compressor):
    files = compressor.list_compressed_files()
    print('Compressed files:')
    for f in files:
        print(f'- {f}')


def main():
    compressor = FileCompressor()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == MENU_COMPRESS:
            _handle_compress(compressor)
        elif choice == MENU_LIST:
            _handle_list(compressor)
        elif choice == MENU_EXIT:
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
