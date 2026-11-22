import os
import subprocess
import sys
from datetime import datetime


class FileCompressor:
    GZIP_EXTENSION = '.gz'
    COMPRESSED_SUFFIX = '_compressed_'
    TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
    GZIP_EXECUTABLE = 'gzip'

    def __init__(self, output_dir='compressed'):
        self.output_dir = output_dir
        self.create_output_dir()

    def create_output_dir(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def get_timestamp(self):
        return datetime.now().strftime(self.TIMESTAMP_FORMAT)

    def validate_filename(self, filename):
        if not os.path.exists(filename):
            raise ValueError(f'File {filename} does not exist')
        if not os.path.isfile(filename):
            raise ValueError(f'{filename} is not a regular file')

    def compress_file(self, filename, compression_level=9):
        self.validate_filename(filename)
        output_path = self._build_output_path(filename)
        compressed_path = f'{output_path}{self.GZIP_EXTENSION}'
        try:
            with open(compressed_path, 'wb') as out_file:
                subprocess.run(
                    self._build_gzip_command(filename, compression_level),
                    stdout=out_file,
                    stderr=subprocess.PIPE,
                    check=True,
                )
            print(f'File compressed and saved to {compressed_path}')
            return compressed_path
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Compression failed: {e.stderr.decode().strip()}')
        except Exception as e:
            raise RuntimeError(f'Error during compression: {str(e)}')

    def list_compressed_files(self):
        return [f for f in os.listdir(self.output_dir) if f.endswith(self.GZIP_EXTENSION)]

    def _build_output_path(self, filename):
        output_name = f'{os.path.basename(filename)}{self.COMPRESSED_SUFFIX}{self.get_timestamp()}'
        return os.path.join(self.output_dir, output_name)

    def _build_gzip_command(self, filename, compression_level):
        return [self.GZIP_EXECUTABLE, f'-{compression_level}', '-c', filename]


MENU_TITLE = '\nFile Compressor Menu:'
MENU_COMPRESS_OPTION = '1. Compress file'
MENU_LIST_OPTION = '2. List compressed files'
MENU_EXIT_OPTION = '3. Exit'

CHOICE_COMPRESS = '1'
CHOICE_LIST = '2'
CHOICE_EXIT = '3'

MIN_COMPRESSION_LEVEL = 1
MAX_COMPRESSION_LEVEL = 9
DEFAULT_COMPRESSION_LEVEL = 9

PROMPT_CHOICE = 'Enter your choice: '
PROMPT_FILENAME = 'Enter file path to compress: '
PROMPT_COMPRESSION_LEVEL = (
    f'Compression level ({MIN_COMPRESSION_LEVEL}-{MAX_COMPRESSION_LEVEL}, '
    f'default {DEFAULT_COMPRESSION_LEVEL}): '
)
COMPRESSED_FILES_HEADER = 'Compressed files:'
EXIT_MESSAGE = 'Exiting...'
INVALID_CHOICE_MESSAGE = 'Invalid choice. Please try again.'


def print_menu():
    print(MENU_TITLE)
    print(MENU_COMPRESS_OPTION)
    print(MENU_LIST_OPTION)
    print(MENU_EXIT_OPTION)


def _handle_compress_file(compressor):
    filename = input(PROMPT_FILENAME)
    level = input(PROMPT_COMPRESSION_LEVEL) or str(DEFAULT_COMPRESSION_LEVEL)
    try:
        compressor.compress_file(filename, int(level))
    except Exception as e:
        print(f'Error: {e}')


def _handle_list_compressed_files(compressor):
    files = compressor.list_compressed_files()
    print(COMPRESSED_FILES_HEADER)
    for f in files:
        print(f'- {f}')


def main():
    compressor = FileCompressor()
    while True:
        print_menu()
        choice = input(PROMPT_CHOICE)
        if choice == CHOICE_COMPRESS:
            _handle_compress_file(compressor)
        elif choice == CHOICE_LIST:
            _handle_list_compressed_files(compressor)
        elif choice == CHOICE_EXIT:
            print(EXIT_MESSAGE)
            break
        else:
            print(INVALID_CHOICE_MESSAGE)


if __name__ == '__main__':
    main()
