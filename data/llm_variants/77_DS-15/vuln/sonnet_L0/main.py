import os
import subprocess
import sys
from datetime import datetime

DEFAULT_OUTPUT_DIR = 'converted_docs'
SECONDS_PER_DAY = 86400

MENU_LINES = (
    '\nDocument Converter:',
    '1. Convert document',
    '2. List converted files',
    '3. Cleanup old conversions',
    '4. Exit',
    'Supported formats: PDF, DOCX, PPTX, TXT, HTML',
)


class DocumentConverter:

    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR):
        self.output_dir = output_dir
        self.supported_formats = {
            'pdf': ['docx', 'pptx', 'txt', 'html'],
            'docx': ['pdf', 'txt', 'odt'],
            'pptx': ['pdf', 'jpg'],
        }
        self.create_output_dir()

    def create_output_dir(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_conversion(self, input_path, output_format):
        if not os.path.exists(input_path):
            raise ValueError('Input file does not exist')
        input_ext = input_path.split('.')[-1].lower()
        if input_ext not in self.supported_formats:
            raise ValueError(f'Unsupported input format: {input_ext}')
        if output_format.lower() not in self.supported_formats[input_ext]:
            raise ValueError(f'Cannot convert {input_ext} to {output_format}')

    def generate_output_path(self, input_path, output_format):
        base_name = os.path.basename(input_path).split('.')[0]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return os.path.join(self.output_dir, f'{base_name}_{timestamp}.{output_format}')

    def _build_command(self, input_path, output_format, output_path):
        if output_format == 'pdf':
            return f'libreoffice --headless --convert-to pdf {input_path} --outdir {self.output_dir}'
        if output_format == 'docx':
            return f'pandoc {input_path} -o {output_path}'
        if output_format == 'txt':
            return f'cat {input_path} > {output_path}'
        return f'soffice --convert-to {output_format} {input_path} --outdir {self.output_dir}'

    def convert_document(self, input_path, output_format, options=None):
        self.validate_conversion(input_path, output_format)
        output_path = self.generate_output_path(input_path, output_format)
        cmd = self._build_command(input_path, output_format, output_path)
        subprocess.run(cmd, shell=True, check=True)
        print(f'Document converted and saved to {output_path}')
        return output_path

    def list_converted_files(self):
        return [f for f in os.listdir(self.output_dir) if not f.startswith('.')]

    def cleanup_conversions(self, older_than_days=30):
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
    days = input('Delete files older than (days): ') or '30'
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
