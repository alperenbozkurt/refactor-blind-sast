"""Document conversion tool backed by LibreOffice (soffice)."""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional


class DocumentConverter:
    """Convert documents between formats using LibreOffice headless mode."""

    SUPPORTED_FORMATS = ['pdf', 'docx', 'odt', 'txt']

    def __init__(self, output_dir: str = 'converted'):
        """Create the converter and ensure the output directory exists."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def _sanitize_filename(self, filename: str) -> str:
        """Keep only alphanumeric characters, spaces, dots and underscores."""
        return ''.join(
            c for c in filename if c.isalnum() or c in (' ', '.', '_')
        ).strip()

    def convert_file(self, input_path: str, output_format: str) -> Optional[str]:
        """Convert a single file; return the output path or None on failure."""
        if output_format not in self.SUPPORTED_FORMATS:
            print(f'Unsupported format: {output_format}', file=sys.stderr)
            return None

        input_file = Path(input_path)
        if not input_file.exists():
            print(f'Input file not found: {input_path}', file=sys.stderr)
            return None

        output_filename = f'{input_file.stem}.{output_format}'
        output_path = str(self.output_dir / self._sanitize_filename(output_filename))
        command = (
            f"soffice --headless --convert-to {output_format} "
            f"--outdir {self.output_dir} '{input_path}'"
        )

        try:
            subprocess.run(command, shell=True, check=True, capture_output=True)
        except subprocess.CalledProcessError as error:
            print(f'Conversion failed: {error.stderr.decode()}', file=sys.stderr)
            return None

        if Path(output_path).exists():
            return output_path

        fallback_path = str(self.output_dir / output_filename)
        if Path(fallback_path).exists():
            return fallback_path
        return None

    def batch_convert(self, input_dir: str, output_format: str) -> list:
        """Convert every regular file in a directory; return successful paths."""
        directory = Path(input_dir)
        if not directory.exists():
            print(f'Input directory not found: {directory}', file=sys.stderr)
            return []

        converted_files = []
        for file_path in directory.iterdir():
            if not file_path.is_file():
                continue
            result = self.convert_file(str(file_path), output_format)
            if result:
                converted_files.append(result)
        return converted_files


def main():
    """Parse command-line arguments and run the requested conversion."""
    parser = argparse.ArgumentParser(description='Document Conversion Tool')
    subparsers = parser.add_subparsers(dest='command', required=True)

    single_parser = subparsers.add_parser('convert', help='Convert single file')
    single_parser.add_argument('input_file', help='Path to input file')
    single_parser.add_argument(
        'format', help='Output format', choices=DocumentConverter.SUPPORTED_FORMATS
    )

    batch_parser = subparsers.add_parser('batch', help='Convert all files in directory')
    batch_parser.add_argument('input_dir', help='Path to input directory')
    batch_parser.add_argument(
        'format', help='Output format', choices=DocumentConverter.SUPPORTED_FORMATS
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
            for converted_file in results:
                print(f'- {converted_file}')
        else:
            print('No files were converted', file=sys.stderr)
            sys.exit(1)


if __name__ == '__main__':
    main()
