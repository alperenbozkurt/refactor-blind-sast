"""Interactive command-line utility for compressing files with gzip."""

import os
import subprocess
import sys
from datetime import datetime

DEFAULT_OUTPUT_DIR = 'compressed'
DEFAULT_COMPRESSION_LEVEL = 9
GZIP_EXTENSION = '.gz'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

CHOICE_COMPRESS = '1'
CHOICE_LIST = '2'
CHOICE_EXIT = '3'

MENU_TITLE = '\nFile Compressor Menu:'
MENU_ENTRIES = (
    (CHOICE_COMPRESS, 'Compress file'),
    (CHOICE_LIST, 'List compressed files'),
    (CHOICE_EXIT, 'Exit'),
)


class FileCompressor:
    """Compress files into gzip archives within a dedicated output directory."""

    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR):
        self.output_dir = output_dir
        self.create_output_dir()

    def create_output_dir(self):
        """Create the output directory unless it already exists."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def get_timestamp(self):
        """Return the current date and time as a filename-safe string."""
        return datetime.now().strftime(TIMESTAMP_FORMAT)

    def validate_filename(self, filename):
        """Raise ValueError unless *filename* is an existing regular file."""
        if not os.path.exists(filename):
            raise ValueError(f'File {filename} does not exist')
        if not os.path.isfile(filename):
            raise ValueError(f'{filename} is not a regular file')

    def compress_file(self, filename, compression_level=DEFAULT_COMPRESSION_LEVEL):
        """Compress *filename* with gzip and return the archive path.

        The archive is written to the output directory under the source
        file's basename, suffixed with a timestamp.
        """
        self.validate_filename(filename)
        output_name = f'{os.path.basename(filename)}_compressed_{self.get_timestamp()}'
        output_path = os.path.join(self.output_dir, output_name)
        gzip_path = f'{output_path}{GZIP_EXTENSION}'
        try:
            with open(gzip_path, 'wb') as out_file:
                subprocess.run(
                    ['gzip', f'-{compression_level}', '-c', filename],
                    stdout=out_file,
                    stderr=subprocess.PIPE,
                    check=True,
                )
            print(f'File compressed and saved to {gzip_path}')
            return gzip_path
        except subprocess.CalledProcessError as error:
            raise RuntimeError(f'Compression failed: {error.stderr.decode().strip()}')
        except Exception as error:
            raise RuntimeError(f'Error during compression: {str(error)}')

    def list_compressed_files(self):
        """Return the names of all gzip archives in the output directory."""
        return [
            entry
            for entry in os.listdir(self.output_dir)
            if entry.endswith(GZIP_EXTENSION)
        ]


def print_menu():
    """Display the available menu options."""
    print(MENU_TITLE)
    for choice, label in MENU_ENTRIES:
        print(f'{choice}. {label}')


def main():
    """Run the interactive compressor menu loop."""
    compressor = FileCompressor()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == CHOICE_COMPRESS:
            filename = input('Enter file path to compress: ')
            level = input('Compression level (1-9, default 9): ') or str(DEFAULT_COMPRESSION_LEVEL)
            try:
                compressor.compress_file(filename, int(level))
            except Exception as error:
                print(f'Error: {error}')
        elif choice == CHOICE_LIST:
            print('Compressed files:')
            for compressed_file in compressor.list_compressed_files():
                print(f'- {compressed_file}')
        elif choice == CHOICE_EXIT:
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
