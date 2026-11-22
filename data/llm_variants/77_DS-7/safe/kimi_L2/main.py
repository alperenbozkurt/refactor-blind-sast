"""Document conversion tool.

Converts documents between formats using LibreOffice's headless ``soffice``
binary -- either a single file or every file in a directory -- and exposes
that functionality through a small command-line interface.
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterator, List, Optional

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = 'converted'

SOFFICE_EXECUTABLE = 'soffice'
SOFFICE_HEADLESS_FLAG = '--headless'
SOFFICE_CONVERT_TO_FLAG = '--convert-to'
SOFFICE_OUTDIR_FLAG = '--outdir'

# Non-alphanumeric characters preserved in generated output file names.
SAFE_FILENAME_CHARS = (' ', '.', '_')

CONVERT_COMMAND = 'convert'
BATCH_COMMAND = 'batch'

EXIT_SUCCESS = 0
EXIT_FAILURE = 1


def _print_error(message: str) -> None:
    """Write ``message`` to standard error."""
    print(message, file=sys.stderr)


class DocumentConverter:
    """Convert documents to other formats via LibreOffice headless mode."""

    SUPPORTED_FORMATS = ['pdf', 'docx', 'odt', 'txt']

    def __init__(self, output_dir: str = DEFAULT_OUTPUT_DIR):
        self.output_dir = Path(output_dir)
        self._ensure_output_dir()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_output_dir(self) -> None:
        self.output_dir.mkdir(exist_ok=True)

    def _sanitize_filename(self, filename: str) -> str:
        return ''.join(
            char for char in filename
            if char.isalnum() or char in SAFE_FILENAME_CHARS
        ).strip()

    def _expected_output_path(self, input_file: Path, output_format: str) -> Path:
        output_filename = f'{input_file.stem}.{output_format}'
        return self.output_dir / self._sanitize_filename(output_filename)

    def _build_soffice_command(self, input_file: Path, output_format: str) -> List[str]:
        return [
            SOFFICE_EXECUTABLE,
            SOFFICE_HEADLESS_FLAG,
            SOFFICE_CONVERT_TO_FLAG, output_format,
            SOFFICE_OUTDIR_FLAG, str(self.output_dir),
            str(input_file),
        ]

    def _run_soffice(self, input_file: Path, output_format: str) -> None:
        subprocess.run(
            self._build_soffice_command(input_file, output_format),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def _find_converted_file(self, input_file: Path, output_format: str) -> Optional[Path]:
        expected_path = self._expected_output_path(input_file, output_format)
        if expected_path.exists():
            return expected_path
        # ``soffice`` may have written the unsanitized file name instead.
        fallback_path = self.output_dir / f'{input_file.stem}.{output_format}'
        if fallback_path.exists():
            return fallback_path
        return None

    @staticmethod
    def _iter_input_files(input_dir: Path) -> Iterator[Path]:
        for entry in input_dir.iterdir():
            if entry.is_file():
                yield entry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def convert_file(self, input_path: str, output_format: str) -> Optional[str]:
        """Convert one file, returning the output path or ``None`` on failure."""
        if output_format not in self.SUPPORTED_FORMATS:
            _print_error(f'Unsupported format: {output_format}')
            return None

        input_file = Path(input_path)
        if not input_file.exists():
            _print_error(f'Input file not found: {input_path}')
            return None

        try:
            self._run_soffice(input_file, output_format)
            converted_path = self._find_converted_file(input_file, output_format)
            return str(converted_path) if converted_path is not None else None
        except subprocess.CalledProcessError as e:
            _print_error(f'Conversion failed: {e.stderr}')
            return None
        except Exception as e:
            _print_error(f'Unexpected error: {e}')
            return None

    def batch_convert(self, input_dir: str, output_format: str) -> list:
        """Convert every file in ``input_dir``, returning the output paths."""
        input_dir = Path(input_dir)
        if not input_dir.exists():
            _print_error(f'Input directory not found: {input_dir}')
            return []

        converted_files = []
        for file in self._iter_input_files(input_dir):
            result = self.convert_file(str(file), output_format)
            if result:
                converted_files.append(result)
        return converted_files


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def _add_convert_subcommand(subparsers: argparse._SubParsersAction) -> None:
    single_parser = subparsers.add_parser(CONVERT_COMMAND, help='Convert single file')
    single_parser.add_argument('input_file', help='Path to input file')
    single_parser.add_argument(
        'format',
        help='Output format',
        choices=DocumentConverter.SUPPORTED_FORMATS,
    )


def _add_batch_subcommand(subparsers: argparse._SubParsersAction) -> None:
    batch_parser = subparsers.add_parser(
        BATCH_COMMAND, help='Convert all files in directory'
    )
    batch_parser.add_argument('input_dir', help='Path to input directory')
    batch_parser.add_argument(
        'format',
        help='Output format',
        choices=DocumentConverter.SUPPORTED_FORMATS,
    )


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Document Conversion Tool')
    subparsers = parser.add_subparsers(dest='command', required=True)
    _add_convert_subcommand(subparsers)
    _add_batch_subcommand(subparsers)
    return parser


def _run_convert_command(converter: DocumentConverter, args: argparse.Namespace) -> int:
    result = converter.convert_file(args.input_file, args.format)
    if not result:
        return EXIT_FAILURE
    print(f'File converted successfully: {result}')
    return EXIT_SUCCESS


def _run_batch_command(converter: DocumentConverter, args: argparse.Namespace) -> int:
    results = converter.batch_convert(args.input_dir, args.format)
    if not results:
        _print_error('No files were converted')
        return EXIT_FAILURE
    print(f'Converted {len(results)} files:')
    for file in results:
        print(f'- {file}')
    return EXIT_SUCCESS


_COMMAND_HANDLERS = {
    CONVERT_COMMAND: _run_convert_command,
    BATCH_COMMAND: _run_batch_command,
}


def main():
    """Entry point for the document conversion command-line interface."""
    parser = _build_argument_parser()
    args = parser.parse_args()

    converter = DocumentConverter()
    exit_code = _COMMAND_HANDLERS[args.command](converter, args)
    if exit_code != EXIT_SUCCESS:
        sys.exit(exit_code)


if __name__ == '__main__':
    main()
