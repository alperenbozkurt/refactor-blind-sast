import os
import subprocess
import sys
from datetime import datetime

DEFAULT_OUTPUT_DIR = 'compressed'
DEFAULT_COMPRESSION_LEVEL = 9
DEFAULT_COMPRESSION_LEVEL_INPUT = '9'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
GZIP_EXTENSION = '.gz'
GZIP_COMMAND = 'gzip'

CHOICE_COMPRESS = '1'
CHOICE_LIST = '2'
CHOICE_EXIT = '3'

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
        """Return the output path (without extension) for a compressed file."""
        output_name = f'{os.path.basename(filename)}_compressed_{self.get_timestamp()}'
        return os.path.join(self.output_dir, output_name)

    @staticmethod
    def _build_gzip_command(filename, compression_level):
        return [GZIP_COMMAND, f'-{compression_level}', '-c', filename]

    def _run_gzip(self, filename, compression_level, destination):
        with open(destination, 'wb') as out_file:
            subprocess.run(
                self._build_gzip_command(filename, compression_level),
                stdout=out_file,
                stderr=subprocess.PIPE,
                check=True,
            )

    def compress_file(self, filename, compression_level=DEFAULT_COMPRESSION_LEVEL):
        self.validate_filename(filename)
        output_path = self._build_output_path(filename)
        destination = f'{output_path}{GZIP_EXTENSION}'
        try:
            self._run_gzip(filename, compression_level, destination)
            print(f'File compressed and saved to {destination}')
            return destination
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Compression failed: {e.stderr.decode().strip()}')
        except Exception as e:
            raise RuntimeError(f'Error during compression: {str(e)}')

    def list_compressed_files(self):
        return [f for f in os.listdir(self.output_dir) if f.endswith(GZIP_EXTENSION)]


def print_menu():
    for line in MENU_LINES:
        print(line)


def _handle_compress(compressor):
    filename = input('Enter file path to compress: ')
    level = input('Compression level (1-9, default 9): ') or DEFAULT_COMPRESSION_LEVEL_INPUT
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
        if choice == CHOICE_COMPRESS:
            _handle_compress(compressor)
        elif choice == CHOICE_LIST:
            _handle_list(compressor)
        elif choice == CHOICE_EXIT:
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
