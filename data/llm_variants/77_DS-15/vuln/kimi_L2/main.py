"""Document conversion utilities with an interactive command-line interface."""

import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = 'converted_docs'
DEFAULT_CLEANUP_DAYS = 30
DEFAULT_CLEANUP_INPUT = '30'
SECONDS_PER_DAY = 86400
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
HIDDEN_FILE_PREFIX = '.'

FORMAT_PDF = 'pdf'
FORMAT_DOCX = 'docx'
FORMAT_TXT = 'txt'

SUPPORTED_FORMATS: Dict[str, List[str]] = {
    'pdf': ['docx', 'pptx', 'txt', 'html'],
    'docx': ['pdf', 'txt', 'odt'],
    'pptx': ['pdf', 'jpg'],
}


@dataclass(frozen=True)
class ConversionCommands:
    """Shell command templates used for each conversion path."""

    to_pdf: str = (
        'libreoffice --headless --convert-to pdf {input_path} --outdir {output_dir}'
    )
    to_docx: str = 'pandoc {input_path} -o {output_path}'
    to_txt: str = 'cat {input_path} > {output_path}'
    generic: str = (
        'soffice --convert-to {output_format} {input_path} --outdir {output_dir}'
    )


COMMANDS = ConversionCommands()

# ---------------------------------------------------------------------------
# CLI constants
# ---------------------------------------------------------------------------

MENU_TEXT = (
    '\nDocument Converter:\n'
    '1. Convert document\n'
    '2. List converted files\n'
    '3. Cleanup old conversions\n'
    '4. Exit\n'
    'Supported formats: PDF, DOCX, PPTX, TXT, HTML'
)

CHOICE_CONVERT = '1'
CHOICE_LIST = '2'
CHOICE_CLEANUP = '3'
CHOICE_EXIT = '4'

PROMPT_CHOICE = 'Enter your choice: '
PROMPT_INPUT_PATH = 'Input file path: '
PROMPT_OUTPUT_FORMAT = 'Output format: '
PROMPT_CLEANUP_DAYS = 'Delete files older than (days): '


def _fresh_supported_formats() -> Dict[str, List[str]]:
    """Return an independent copy of the supported-format mapping."""
    return {fmt: list(targets) for fmt, targets in SUPPORTED_FORMATS.items()}


class DocumentConverter:
    """Convert documents between supported formats via external tools."""

    def __init__(self, output_dir: str = DEFAULT_OUTPUT_DIR) -> None:
        self.output_dir = output_dir
        self.supported_formats = _fresh_supported_formats()
        self._commands = COMMANDS
        self.create_output_dir()

    def create_output_dir(self) -> None:
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_conversion(self, input_path: str, output_format: str) -> None:
        self._ensure_input_exists(input_path)
        input_ext = self._extract_extension(input_path)
        self._ensure_supported_input(input_ext)
        self._ensure_supported_target(input_ext, output_format)

    def generate_output_path(self, input_path: str, output_format: str) -> str:
        base_name = os.path.basename(input_path).split('.')[0]
        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        return os.path.join(
            self.output_dir, f'{base_name}_{timestamp}.{output_format}'
        )

    def convert_document(
        self,
        input_path: str,
        output_format: str,
        options: Optional[dict] = None,
    ) -> str:
        self.validate_conversion(input_path, output_format)
        output_path = self.generate_output_path(input_path, output_format)
        command = self._build_command(input_path, output_format, output_path)
        self._run_command(command)
        print(f'Document converted and saved to {output_path}')
        return output_path

    def list_converted_files(self) -> List[str]:
        return [
            filename
            for filename in os.listdir(self.output_dir)
            if not filename.startswith(HIDDEN_FILE_PREFIX)
        ]

    def cleanup_conversions(
        self, older_than_days: int = DEFAULT_CLEANUP_DAYS
    ) -> None:
        cutoff = datetime.now().timestamp() - older_than_days * SECONDS_PER_DAY
        for filename in os.listdir(self.output_dir):
            filepath = os.path.join(self.output_dir, filename)
            if self._is_expired(filepath, cutoff):
                os.remove(filepath)
                print(f'Removed old conversion: {filename}')

    # -- internal helpers ----------------------------------------------------

    @staticmethod
    def _ensure_input_exists(input_path: str) -> None:
        if not os.path.exists(input_path):
            raise ValueError('Input file does not exist')

    @staticmethod
    def _extract_extension(input_path: str) -> str:
        return input_path.split('.')[-1].lower()

    def _ensure_supported_input(self, input_ext: str) -> None:
        if input_ext not in self.supported_formats:
            raise ValueError(f'Unsupported input format: {input_ext}')

    def _ensure_supported_target(
        self, input_ext: str, output_format: str
    ) -> None:
        if output_format.lower() not in self.supported_formats[input_ext]:
            raise ValueError(f'Cannot convert {input_ext} to {output_format}')

    def _build_command(
        self, input_path: str, output_format: str, output_path: str
    ) -> str:
        if output_format == FORMAT_PDF:
            return self._commands.to_pdf.format(
                input_path=input_path, output_dir=self.output_dir
            )
        if output_format == FORMAT_DOCX:
            return self._commands.to_docx.format(
                input_path=input_path, output_path=output_path
            )
        if output_format == FORMAT_TXT:
            return self._commands.to_txt.format(
                input_path=input_path, output_path=output_path
            )
        return self._commands.generic.format(
            output_format=output_format,
            input_path=input_path,
            output_dir=self.output_dir,
        )

    @staticmethod
    def _run_command(command: str) -> None:
        subprocess.run(command, shell=True, check=True)

    @staticmethod
    def _is_expired(filepath: str, cutoff: float) -> bool:
        return os.path.getmtime(filepath) < cutoff


def print_menu() -> None:
    print(MENU_TEXT)


def _handle_convert(converter: DocumentConverter) -> None:
    input_path = input(PROMPT_INPUT_PATH)
    output_format = input(PROMPT_OUTPUT_FORMAT)
    try:
        converter.convert_document(input_path, output_format.lower())
    except Exception as e:
        print(f'Error: {e}')


def _handle_list(converter: DocumentConverter) -> None:
    files = converter.list_converted_files()
    print('Converted files:')
    for f in files:
        print(f'- {f}')


def _handle_cleanup(converter: DocumentConverter) -> None:
    days = input(PROMPT_CLEANUP_DAYS) or DEFAULT_CLEANUP_INPUT
    converter.cleanup_conversions(int(days))


def main() -> None:
    converter = DocumentConverter()
    handlers = {
        CHOICE_CONVERT: _handle_convert,
        CHOICE_LIST: _handle_list,
        CHOICE_CLEANUP: _handle_cleanup,
    }
    while True:
        print_menu()
        choice = input(PROMPT_CHOICE)
        if choice == CHOICE_EXIT:
            print('Exiting...')
            break
        handler = handlers.get(choice)
        if handler is None:
            print('Invalid choice. Please try again.')
            continue
        handler(converter)


if __name__ == '__main__':
    main()
