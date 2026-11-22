import os
import subprocess
import sys
from datetime import datetime

DEFAULT_OUTPUT_DIR = 'converted_docs'
DEFAULT_CLEANUP_DAYS = 30
SECONDS_PER_DAY = 86400
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

SUPPORTED_FORMATS = {
    'pdf': ['docx', 'pptx', 'txt', 'html'],
    'docx': ['pdf', 'txt', 'odt'],
    'pptx': ['pdf', 'jpg'],
}

MENU_LINES = (
    '\nDocument Converter:',
    '1. Convert document',
    '2. List converted files',
    '3. Cleanup old conversions',
    '4. Exit',
    'Supported formats: PDF, DOCX, PPTX, TXT, HTML',
)


def _copy_supported_formats():
    """Return a fresh, independent copy of the supported-format mapping."""
    return {src: list(targets) for src, targets in SUPPORTED_FORMATS.items()}


def _extract_extension(path):
    return path.split('.')[-1].lower()


def _extract_base_name(path):
    return os.path.basename(path).split('.')[0]


def _run_command(command):
    subprocess.run(command, check=True, stderr=subprocess.PIPE)


class DocumentConverter:

    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR):
        self.output_dir = output_dir
        self.supported_formats = _copy_supported_formats()
        self.create_output_dir()

    def create_output_dir(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_conversion(self, input_path, output_format):
        if not os.path.exists(input_path):
            raise ValueError('Input file does not exist')
        input_ext = _extract_extension(input_path)
        if input_ext not in self.supported_formats:
            raise ValueError(f'Unsupported input format: {input_ext}')
        if output_format.lower() not in self.supported_formats[input_ext]:
            raise ValueError(f'Cannot convert {input_ext} to {output_format}')

    def generate_output_path(self, input_path, output_format):
        base_name = _extract_base_name(input_path)
        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        return os.path.join(self.output_dir, f'{base_name}_{timestamp}.{output_format}')

    # -- conversion strategies -------------------------------------------------

    def _convert_to_pdf(self, input_path, output_path):
        _run_command(['libreoffice', '--headless', '--convert-to', 'pdf',
                      input_path, '--outdir', self.output_dir])

    def _convert_to_docx(self, input_path, output_path):
        _run_command(['pandoc', input_path, '-o', output_path])

    def _convert_to_txt(self, input_path, output_path):
        with open(input_path, 'r') as infile, open(output_path, 'w') as outfile:
            outfile.write(infile.read())

    def _convert_with_soffice(self, input_path, output_format):
        _run_command(['soffice', '--convert-to', output_format,
                      input_path, '--outdir', self.output_dir])

    def _dispatch_conversion(self, input_path, output_format, output_path):
        if output_format == 'pdf':
            self._convert_to_pdf(input_path, output_path)
        elif output_format == 'docx':
            self._convert_to_docx(input_path, output_path)
        elif output_format == 'txt':
            self._convert_to_txt(input_path, output_path)
        else:
            self._convert_with_soffice(input_path, output_format)

    def convert_document(self, input_path, output_format, options=None):
        self.validate_conversion(input_path, output_format)
        output_path = self.generate_output_path(input_path, output_format)
        try:
            self._dispatch_conversion(input_path, output_format, output_path)
            print(f'Document converted and saved to {output_path}')
            return output_path
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Conversion failed: {e.stderr.decode().strip()}')
        except Exception as e:
            raise RuntimeError(f'Error during conversion: {str(e)}')

    def list_converted_files(self):
        return [f for f in os.listdir(self.output_dir) if not f.startswith('.')]

    def cleanup_conversions(self, older_than_days=DEFAULT_CLEANUP_DAYS):
        cutoff = datetime.now().timestamp() - older_than_days * SECONDS_PER_DAY
        for filename in os.listdir(self.output_dir):
            filepath = os.path.join(self.output_dir, filename)
            if os.path.getmtime(filepath) < cutoff:
                os.remove(filepath)
                print(f'Removed old conversion: {filename}')


def print_menu():
    for line in MENU_LINES:
        print(line)


def _handle_convert(converter):
    input_path = input('Input file path: ')
    output_format = input('Output format: ')
    try:
        converter.convert_document(input_path, output_format.lower())
    except Exception as e:
        print(f'Error: {e}')


def _handle_list(converter):
    files = converter.list_converted_files()
    print('Converted files:')
    for f in files:
        print(f'- {f}')


def _handle_cleanup(converter):
    days = input('Delete files older than (days): ') or str(DEFAULT_CLEANUP_DAYS)
    converter.cleanup_conversions(int(days))


def main():
    converter = DocumentConverter()
    handlers = {
        '1': _handle_convert,
        '2': _handle_list,
        '3': _handle_cleanup,
    }
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice in handlers:
            handlers[choice](converter)
        elif choice == '4':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
