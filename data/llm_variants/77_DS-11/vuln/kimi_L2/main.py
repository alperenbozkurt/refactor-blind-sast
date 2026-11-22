"""Gzip-based file compressor with an interactive command-line menu."""

import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = 'compressed'
DEFAULT_COMPRESSION_LEVEL = 9
COMPRESSED_EXTENSION = '.gz'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

CHOICE_COMPRESS = '1'
CHOICE_LIST = '2'
CHOICE_EXIT = '3'

MENU_LINES = (
    '\nFile Compressor Menu:',
    '1. Compress file',
    '2. List compressed files',
    '3. Exit',
)

PROMPT_CHOICE = 'Enter your choice: '
PROMPT_FILENAME = 'Enter file path to compress: '
PROMPT_COMPRESSION_LEVEL = 'Compression level (1-9, default 9): '


# ---------------------------------------------------------------------------
# Configuration object
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompressorConfig:
    """Settings controlling how :class:`FileCompressor` names and stores
    compressed archives."""

    output_dir: str = DEFAULT_OUTPUT_DIR
    default_compression_level: int = DEFAULT_COMPRESSION_LEVEL
    compressed_extension: str = COMPRESSED_EXTENSION
    timestamp_format: str = TIMESTAMP_FORMAT


# ---------------------------------------------------------------------------
# Small helper functions
# ---------------------------------------------------------------------------


def _ensure_directory(path):
    """Create ``path`` (including parents) unless it already exists."""
    if not os.path.exists(path):
        os.makedirs(path)


def _run_shell_command(command):
    """Run ``command`` through the system shell."""
    subprocess.call(command, shell=True)


# ---------------------------------------------------------------------------
# Compressor
# ---------------------------------------------------------------------------


class FileCompressor:
    """Compress individual files with ``gzip`` into a dedicated directory."""

    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR):
        self.config = CompressorConfig(output_dir=output_dir)
        self.output_dir = output_dir
        self.create_output_dir()

    def create_output_dir(self):
        _ensure_directory(self.output_dir)

    def get_timestamp(self):
        return datetime.now().strftime(self.config.timestamp_format)

    def validate_filename(self, filename):
        if not os.path.exists(filename):
            raise ValueError(f'File {filename} does not exist')
        if not os.path.isfile(filename):
            raise ValueError(f'{filename} is not a regular file')

    def compress_file(self, filename, compression_level=DEFAULT_COMPRESSION_LEVEL):
        self.validate_filename(filename)
        output_path = self._build_output_path(filename)
        archive_path = self._append_extension(output_path)
        command = self._build_gzip_command(filename, compression_level, archive_path)
        _run_shell_command(command)
        print(f'File compressed and saved to {archive_path}')
        return archive_path

    def list_compressed_files(self):
        return [
            entry
            for entry in os.listdir(self.output_dir)
            if entry.endswith(self.config.compressed_extension)
        ]

    # -- internal helpers ---------------------------------------------------

    def _build_output_path(self, filename):
        output_name = f'{os.path.basename(filename)}_compressed_{self.get_timestamp()}'
        return os.path.join(self.output_dir, output_name)

    def _append_extension(self, output_path):
        return f'{output_path}{self.config.compressed_extension}'

    @staticmethod
    def _build_gzip_command(filename, compression_level, archive_path):
        return f'gzip -{compression_level} -c {filename} > {archive_path}'


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------


def print_menu():
    for line in MENU_LINES:
        print(line)


def _handle_compress(compressor):
    filename = input(PROMPT_FILENAME)
    level = input(PROMPT_COMPRESSION_LEVEL) or str(DEFAULT_COMPRESSION_LEVEL)
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
        choice = input(PROMPT_CHOICE)
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
