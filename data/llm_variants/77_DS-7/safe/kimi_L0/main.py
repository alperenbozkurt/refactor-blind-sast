"""Command-line tool for converting documents using LibreOffice."""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional


class DocumentConverter:
    """Convert files between document formats via headless LibreOffice."""

    SUPPORTED_FORMATS = ['pdf', 'docx', 'odt', 'txt']

    _ALLOWED_FILENAME_CHARS = frozenset((' ', '.', '_'))

    def __init__(self, output_dir: str = 'converted'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def _sanitize_filename(self, filename: str) -> str:
        return ''.join(
            char
            for char in filename
            if char.isalnum() or char in self._ALLOWED_FILENAME_CHARS
        ).strip()

    def _build_soffice_command(self, input_file: Path, output_format: str) -> list:
        return [
            'soffice',
            '--headless',
            '--convert-to', output_format,
            '--outdir', str(self.output_dir),
            str(input_file),
        ]

    def convert_file(self, input_path: str, output_format: str) -> Optional[str]:
        if output_format not in self.SUPPORTED_FORMATS:
            print(f'Unsupported format: {output_format}', file=sys.stderr)
            return None

        input_file = Path(input_path)
        if not input_file.exists():
            print(f'Input file not found: {input_path}', file=sys.stderr)
            return None

        output_path = str(
            self.output_dir
            / self._sanitize_filename(f'{input_file.stem}.{output_format}')
        )

        try:
            subprocess.run(
                self._build_soffice_command(input_file, output_format),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if Path(output_path).exists():
                return output_path

            fallback_path = str(
                self.output_dir / f'{input_file.stem}.{output_format}'
            )
            if Path(fallback_path).exists():
                return fallback_path
            return None
        except subprocess.CalledProcessError as error:
            print(f'Conversion failed: {error.stderr}', file=sys.stderr)
            return None
        except Exception as error:
            print(f'Unexpected error: {error}', file=sys.stderr)
            return None

    def batch_convert(self, input_dir: str, output_format: str) -> list:
        directory = Path(input_dir)
        if not directory.exists():
            print(f'Input directory not found: {directory}', file=sys.stderr)
            return []

        converted_files = []
        for file in directory.iterdir():
            if not file.is_file():
                continue
            result = self.convert_file(str(file), output_format)
            if result:
                converted_files.append(result)
        return converted_files


def main():
    parser = argparse.ArgumentParser(description='Document Conversion Tool')
    subparsers = parser.add_subparsers(dest='command', required=True)

    single_parser = subparsers.add_parser('convert', help='Convert single file')
    single_parser.add_argument('input_file', help='Path to input file')
    single_parser.add_argument(
        'format',
        help='Output format',
        choices=DocumentConverter.SUPPORTED_FORMATS,
    )

    batch_parser = subparsers.add_parser(
        'batch', help='Convert all files in directory'
    )
    batch_parser.add_argument('input_dir', help='Path to input directory')
    batch_parser.add_argument(
        'format',
        help='Output format',
        choices=DocumentConverter.SUPPORTED_FORMATS,
    )

    args = parser.parse_args()
    converter = DocumentConverter()

    if args.command == 'convert':
        result = converter.convert_file(args.input_file, args.format)
        if result:
            print(f'File converted successfully: {result}')
        else:
            sys.exit(1)
    elif args.command == 'batch':
        results = converter.batch_convert(args.input_dir, args.format)
        if results:
            print(f'Converted {len(results)} files:')
            for file in results:
                print(f'- {file}')
        else:
            print('No files were converted', file=sys.stderr)
            sys.exit(1)


if __name__ == '__main__':
    main()
