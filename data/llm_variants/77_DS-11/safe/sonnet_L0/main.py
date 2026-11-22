import os
import subprocess
import sys
from datetime import datetime

DEFAULT_COMPRESSION_LEVEL = '9'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
COMPRESSED_EXTENSION = '.gz'


class FileCompressor:

    def __init__(self, output_dir='compressed'):
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
        return os.path.join(self.output_dir, output_name) + COMPRESSED_EXTENSION

    def compress_file(self, filename, compression_level=9):
        self.validate_filename(filename)
        output_path = self._build_output_path(filename)
        command = ['gzip', f'-{compression_level}', '-c', filename]
        try:
            with open(output_path, 'wb') as out_file:
                subprocess.run(command, stdout=out_file, stderr=subprocess.PIPE, check=True)
            print(f'File compressed and saved to {output_path}')
            return output_path
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Compression failed: {e.stderr.decode().strip()}')
        except Exception as e:
            raise RuntimeError(f'Error during compression: {str(e)}')

    def list_compressed_files(self):
        return [f for f in os.listdir(self.output_dir) if f.endswith(COMPRESSED_EXTENSION)]


def print_menu():
    print('\nFile Compressor Menu:')
    print('1. Compress file')
    print('2. List compressed files')
    print('3. Exit')


def _handle_compress(compressor):
    filename = input('Enter file path to compress: ')
    level = input('Compression level (1-9, default 9): ') or DEFAULT_COMPRESSION_LEVEL
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
        if choice == '1':
            _handle_compress(compressor)
        elif choice == '2':
            _handle_list(compressor)
        elif choice == '3':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
