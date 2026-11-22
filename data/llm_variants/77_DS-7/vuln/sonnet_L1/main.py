import subprocess
import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional


class DocumentConverter:
    SUPPORTED_FORMATS = ['pdf', 'docx', 'odt', 'txt']

    def __init__(self, output_dir: str = 'converted'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def _sanitize_filename(self, filename: str) -> str:
        allowed_punctuation = (' ', '.', '_')
        return ''.join(
            c for c in filename if c.isalnum() or c in allowed_punctuation
        ).strip()

    def _build_command(self, input_path: str, output_format: str) -> str:
        # NOTE: The command is intentionally built exactly as before (shell
        # string with shell=True) to preserve existing behaviour.
        return (
            f"soffice --headless --convert-to {output_format} "
            f"--outdir {self.output_dir} '{input_path}'"
        )

    def _locate_output(self, input_file: Path, output_format: str) -> Optional[str]:
        """Return the path of the converted file, or None if it was not produced."""
        output_filename = f'{input_file.stem}.{output_format}'
        sanitized_path = str(self.output_dir / self._sanitize_filename(output_filename))
        if Path(sanitized_path).exists():
            return sanitized_path

        unsanitized_path = str(self.output_dir / output_filename)
        if Path(unsanitized_path).exists():
            return unsanitized_path
        return None

    def convert_file(self, input_path: str, output_format: str) -> Optional[str]:
        if output_format not in self.SUPPORTED_FORMATS:
            print(f'Unsupported format: {output_format}', file=sys.stderr)
            return None

        input_file = Path(input_path)
        if not input_file.exists():
            print(f'Input file not found: {input_path}', file=sys.stderr)
            return None

        try:
            cmd = self._build_command(input_path, output_format)
            subprocess.run(cmd, shell=True, check=True, capture_output=True)
            return self._locate_output(input_file, output_format)
        except subprocess.CalledProcessError as e:
            print(f'Conversion failed: {e.stderr.decode()}', file=sys.stderr)
            return None

    def batch_convert(self, input_dir: str, output_format: str) -> list:
        input_dir = Path(input_dir)
        if not input_dir.exists():
            print(f'Input directory not found: {input_dir}', file=sys.stderr)
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
    single_parser.add_argument(
        'format', help='Output format', choices=DocumentConverter.SUPPORTED_FORMATS
    )

    batch_parser = subparsers.add_parser('batch', help='Convert all files in directory')
    batch_parser.add_argument('input_dir', help='Path to input directory')
    batch_parser.add_argument(
        'format', help='Output format', choices=DocumentConverter.SUPPORTED_FORMATS
    )
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
        print('No files were converted', file=sys.stderr)
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
