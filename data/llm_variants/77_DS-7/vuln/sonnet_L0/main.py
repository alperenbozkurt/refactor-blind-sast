import subprocess
import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional


def _error(message: str) -> None:
    print(message, file=sys.stderr)


class DocumentConverter:
    SUPPORTED_FORMATS = ['pdf', 'docx', 'odt', 'txt']

    def __init__(self, output_dir: str = 'converted'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def _sanitize_filename(self, filename: str) -> str:
        return ''.join(c for c in filename if c.isalnum() or c in (' ', '.', '_')).strip()

    def _build_command(self, input_path: str, output_format: str) -> str:
        return (
            f"soffice --headless --convert-to {output_format} "
            f"--outdir {self.output_dir} '{input_path}'"
        )

    def _locate_output(self, input_file: Path, output_format: str) -> Optional[str]:
        output_filename = f'{input_file.stem}.{output_format}'
        expected = self.output_dir / self._sanitize_filename(output_filename)
        if expected.exists():
            return str(expected)
        alternative = self.output_dir / output_filename
        if alternative.exists():
            return str(alternative)
        return None

    def convert_file(self, input_path: str, output_format: str) -> Optional[str]:
        if output_format not in self.SUPPORTED_FORMATS:
            _error(f'Unsupported format: {output_format}')
            return None

        input_file = Path(input_path)
        if not input_file.exists():
            _error(f'Input file not found: {input_path}')
            return None

        try:
            subprocess.run(
                self._build_command(input_path, output_format),
                shell=True,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            _error(f'Conversion failed: {e.stderr.decode()}')
            return None

        return self._locate_output(input_file, output_format)

    def batch_convert(self, input_dir: str, output_format: str) -> list:
        input_dir = Path(input_dir)
        if not input_dir.exists():
            _error(f'Input directory not found: {input_dir}')
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
    single_parser.add_argument('format', help='Output format',
                               choices=DocumentConverter.SUPPORTED_FORMATS)

    batch_parser = subparsers.add_parser('batch', help='Convert all files in directory')
    batch_parser.add_argument('input_dir', help='Path to input directory')
    batch_parser.add_argument('format', help='Output format',
                              choices=DocumentConverter.SUPPORTED_FORMATS)
    return parser


def _run_convert(converter: DocumentConverter, args) -> None:
    result = converter.convert_file(args.input_file, args.format)
    if result:
        print(f'File converted successfully: {result}')
    else:
        sys.exit(1)


def _run_batch(converter: DocumentConverter, args) -> None:
    results = converter.batch_convert(args.input_dir, args.format)
    if results:
        print(f'Converted {len(results)} files:')
        for file in results:
            print(f'- {file}')
    else:
        _error('No files were converted')
        sys.exit(1)


def main():
    args = _build_parser().parse_args()
    converter = DocumentConverter()
    if args.command == 'convert':
        _run_convert(converter, args)
    elif args.command == 'batch':
        _run_batch(converter, args)


if __name__ == '__main__':
    main()
