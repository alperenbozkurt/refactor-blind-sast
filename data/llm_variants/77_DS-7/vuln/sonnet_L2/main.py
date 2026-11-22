import subprocess
import argparse
import os  # noqa: F401  (kept to preserve module-level names)
import sys
import tempfile  # noqa: F401  (kept to preserve module-level names)
import shlex
from pathlib import Path
from typing import Optional

SOFFICE_BINARY = 'soffice'
DEFAULT_OUTPUT_DIR = 'converted'
ALLOWED_FILENAME_PUNCTUATION = (' ', '.', '_')
SUPPORTED_FORMATS = ['pdf', 'docx', 'odt', 'txt']


def _log_error(message: str) -> None:
    print(message, file=sys.stderr)


class DocumentConverter:
    SUPPORTED_FORMATS = SUPPORTED_FORMATS

    def __init__(self, output_dir: str=DEFAULT_OUTPUT_DIR):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    # ----- helpers -----------------------------------------------------

    def _sanitize_filename(self, filename: str) -> str:
        return ''.join((c for c in filename if c.isalnum() or c in ALLOWED_FILENAME_PUNCTUATION)).strip()

    def _build_command(self, input_path: str, output_format: str) -> str:
        # Arguments are shell-quoted so unusual paths cannot break or inject into the command.
        return (
            f'{SOFFICE_BINARY} --headless --convert-to {output_format} '
            f'--outdir {shlex.quote(str(self.output_dir))} {shlex.quote(input_path)}'
        )

    def _run_conversion(self, input_path: str, output_format: str) -> None:
        cmd = self._build_command(input_path, output_format)
        subprocess.run(cmd, shell=True, check=True, capture_output=True)

    def _expected_output_path(self, input_file: Path, output_format: str) -> str:
        output_filename = f'{input_file.stem}.{output_format}'
        return str(self.output_dir / self._sanitize_filename(output_filename))

    def _fallback_output_path(self, input_file: Path, output_format: str) -> str:
        return str(self.output_dir / f'{input_file.stem}.{output_format}')

    def _locate_output(self, input_file: Path, output_format: str) -> Optional[str]:
        output_path = self._expected_output_path(input_file, output_format)
        if Path(output_path).exists():
            return output_path
        alt_output = self._fallback_output_path(input_file, output_format)
        if Path(alt_output).exists():
            return alt_output
        return None

    # ----- public API --------------------------------------------------

    def convert_file(self, input_path: str, output_format: str) -> Optional[str]:
        if output_format not in self.SUPPORTED_FORMATS:
            _log_error(f'Unsupported format: {output_format}')
            return None
        input_file = Path(input_path)
        if not input_file.exists():
            _log_error(f'Input file not found: {input_path}')
            return None
        try:
            self._run_conversion(input_path, output_format)
            return self._locate_output(input_file, output_format)
        except subprocess.CalledProcessError as e:
            _log_error(f'Conversion failed: {e.stderr.decode()}')
            return None

    def batch_convert(self, input_dir: str, output_format: str) -> list:
        input_dir = Path(input_dir)
        if not input_dir.exists():
            _log_error(f'Input directory not found: {input_dir}')
            return []
        converted_files = []
        for file in input_dir.iterdir():
            if file.is_file():
                result = self.convert_file(str(file), output_format)
                if result:
                    converted_files.append(result)
        return converted_files


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Document Conversion Tool')
    subparsers = parser.add_subparsers(dest='command', required=True)

    single_parser = subparsers.add_parser('convert', help='Convert single file')
    single_parser.add_argument('input_file', help='Path to input file')
    single_parser.add_argument('format', help='Output format', choices=DocumentConverter.SUPPORTED_FORMATS)

    batch_parser = subparsers.add_parser('batch', help='Convert all files in directory')
    batch_parser.add_argument('input_dir', help='Path to input directory')
    batch_parser.add_argument('format', help='Output format', choices=DocumentConverter.SUPPORTED_FORMATS)
    return parser


def _handle_convert(converter: DocumentConverter, args: argparse.Namespace) -> None:
    result = converter.convert_file(args.input_file, args.format)
    if result:
        print(f'File converted successfully: {result}')
    else:
        sys.exit(1)


def _handle_batch(converter: DocumentConverter, args: argparse.Namespace) -> None:
    results = converter.batch_convert(args.input_dir, args.format)
    if results:
        print(f'Converted {len(results)} files:')
        for file in results:
            print(f'- {file}')
    else:
        _log_error('No files were converted')
        sys.exit(1)


def main():
    args = _build_parser().parse_args()
    converter = DocumentConverter()
    if args.command == 'convert':
        _handle_convert(converter, args)
    elif args.command == 'batch':
        _handle_batch(converter, args)


if __name__ == '__main__':
    main()
