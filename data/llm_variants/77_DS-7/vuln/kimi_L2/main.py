"""Document conversion tool with a command-line interface.

Wraps a headless LibreOffice (``soffice``) process to convert documents
between formats, either one file at a time or in batch over a directory.
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterator, Optional


DEFAULT_OUTPUT_DIR = 'converted'
SOFFICE_EXECUTABLE = 'soffice'
SAFE_FILENAME_CHARS = (' ', '.', '_')

CONVERT_COMMAND = 'convert'
BATCH_COMMAND = 'batch'


def _print_error(message: str) -> None:
    """Write *message* to standard error."""
    print(message, file=sys.stderr)


class DocumentConverter:
    """Convert documents to other formats using headless LibreOffice."""

    SUPPORTED_FORMATS = ['pdf', 'docx', 'odt', 'txt']

    def __init__(self, output_dir: str = DEFAULT_OUTPUT_DIR):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def _sanitize_filename(self, filename: str) -> str:
        return ''.join(
            c for c in filename if c.isalnum() or c in SAFE_FILENAME_CHARS
        ).strip()

    def _build_soffice_command(self, input_path: str, output_format: str) -> str:
        """Build the shell command used to perform a single conversion."""
        return (
            f'{SOFFICE_EXECUTABLE} --headless --convert-to {output_format} '
            f"--outdir {self.output_dir} '{input_path}'"
        )

    def _run_conversion(self, input_path: str, output_format: str) -> None:
        """Run the conversion command, raising on a non-zero exit status."""
        subprocess.run(
            self._build_soffice_command(input_path, output_format),
            shell=True,
            check=True,
            capture_output=True,
        )

    def _locate_output_file(
        self, input_file: Path, output_format: str
    ) -> Optional[str]:
        """Return the path of the produced file, or ``None`` if it is missing."""
        output_filename = f'{input_file.stem}.{output_format}'
        output_path = str(self.output_dir / self._sanitize_filename(output_filename))
        if Path(output_path).exists():
            return output_path
        alt_output = str(self.output_dir / output_filename)
        if Path(alt_output).exists():
            return alt_output
        return None

    def convert_file(self, input_path: str, output_format: str) -> Optional[str]:
        """Convert a single file, returning the output path or ``None``."""
        if output_format not in self.SUPPORTED_FORMATS:
            _print_error(f'Unsupported format: {output_format}')
            return None
        input_file = Path(input_path)
        if not input_file.exists():
            _print_error(f'Input file not found: {input_path}')
            return None
        try:
            self._run_conversion(input_path, output_format)
        except subprocess.CalledProcessError as e:
            _print_error(f'Conversion failed: {e.stderr.decode()}')
            return None
        return self._locate_output_file(input_file, output_format)

    def _iter_input_files(self, input_dir: Path) -> Iterator[Path]:
        """Yield the regular files contained directly in *input_dir*."""
        for file in input_dir.iterdir():
            if file.is_file():
                yield file

    def batch_convert(self, input_dir: str, output_format: str) -> list:
        """Convert every regular file in *input_dir* to *output_format*."""
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


def _build_argument_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the command-line interface."""
    parser = argparse.ArgumentParser(description='Document Conversion Tool')
    subparsers = parser.add_subparsers(dest='command', required=True)

    single_parser = subparsers.add_parser(
        CONVERT_COMMAND, help='Convert single file'
    )
    single_parser.add_argument('input_file', help='Path to input file')
    single_parser.add_argument(
        'format', help='Output format', choices=DocumentConverter.SUPPORTED_FORMATS
    )

    batch_parser = subparsers.add_parser(
        BATCH_COMMAND, help='Convert all files in directory'
    )
    batch_parser.add_argument('input_dir', help='Path to input directory')
    batch_parser.add_argument(
        'format', help='Output format', choices=DocumentConverter.SUPPORTED_FORMATS
    )

    return parser


def _handle_convert(converter: DocumentConverter, args: argparse.Namespace) -> None:
    """Run the ``convert`` subcommand."""
    result = converter.convert_file(args.input_file, args.format)
    if result:
        print(f'File converted successfully: {result}')
    else:
        sys.exit(1)


def _handle_batch(converter: DocumentConverter, args: argparse.Namespace) -> None:
    """Run the ``batch`` subcommand."""
    results = converter.batch_convert(args.input_dir, args.format)
    if results:
        print(f'Converted {len(results)} files:')
        for file in results:
            print(f'- {file}')
    else:
        _print_error('No files were converted')
        sys.exit(1)


def main():
    parser = _build_argument_parser()
    args = parser.parse_args()
    converter = DocumentConverter()
    if args.command == CONVERT_COMMAND:
        _handle_convert(converter, args)
    elif args.command == BATCH_COMMAND:
        _handle_batch(converter, args)


if __name__ == '__main__':
    main()
