import os
import subprocess
import sys  # noqa: F401  (kept to preserve the original module-level namespace)
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = 'converted_docs'
DEFAULT_CLEANUP_DAYS = 30
SECONDS_PER_DAY = 86400
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

SUPPORTED_FORMATS = {
    'pdf': ['docx', 'pptx', 'txt', 'html'],
    'docx': ['pdf', 'txt', 'odt'],
    'pptx': ['pdf', 'jpg'],
}

CHOICE_CONVERT = '1'
CHOICE_LIST = '2'
CHOICE_CLEANUP = '3'
CHOICE_EXIT = '4'

MENU_LINES = (
    '',
    'Document Converter:',
    '1. Convert document',
    '2. List converted files',
    '3. Cleanup old conversions',
    '4. Exit',
    'Supported formats: PDF, DOCX, PPTX, TXT, HTML',
)

PROMPT_CHOICE = 'Enter your choice: '
PROMPT_INPUT_PATH = 'Input file path: '
PROMPT_OUTPUT_FORMAT = 'Output format: '
PROMPT_CLEANUP_DAYS = 'Delete files older than (days): '


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _extract_extension(path):
    """Return the lowercased extension portion of *path*."""
    return path.split('.')[-1].lower()


def _current_timestamp():
    """Return the current time formatted for output filenames."""
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _run_command(command):
    """Run an external conversion command, capturing stderr."""
    subprocess.run(command, check=True, stderr=subprocess.PIPE)


def _pdf_command(input_path, output_dir):
    return ['libreoffice', '--headless', '--convert-to', 'pdf',
            input_path, '--outdir', output_dir]


def _docx_command(input_path, output_path):
    return ['pandoc', input_path, '-o', output_path]


def _generic_command(output_format, input_path, output_dir):
    return ['soffice', '--convert-to', output_format,
            input_path, '--outdir', output_dir]


def _copy_as_text(input_path, output_path):
    """Copy a file verbatim, producing the plain-text output."""
    with open(input_path, 'r') as infile, open(output_path, 'w') as outfile:
        outfile.write(infile.read())


# ---------------------------------------------------------------------------
# Core converter
# ---------------------------------------------------------------------------

class DocumentConverter:

    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR):
        self.output_dir = output_dir
        self.supported_formats = {
            fmt: list(targets) for fmt, targets in SUPPORTED_FORMATS.items()
        }
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
        base_name = os.path.basename(input_path).split('.')[0]
        filename = f'{base_name}_{_current_timestamp()}.{output_format}'
        return os.path.join(self.output_dir, filename)

    def convert_document(self, input_path, output_format, options=None):
        self.validate_conversion(input_path, output_format)
        output_path = self.generate_output_path(input_path, output_format)
        try:
            self._run_conversion(input_path, output_path, output_format)
            print(f'Document converted and saved to {output_path}')
            return output_path
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Conversion failed: {e.stderr.decode().strip()}')
        except Exception as e:
            raise RuntimeError(f'Error during conversion: {str(e)}')

    def _run_conversion(self, input_path, output_path, output_format):
        """Dispatch to the appropriate backend for *output_format*."""
        if output_format == 'pdf':
            _run_command(_pdf_command(input_path, self.output_dir))
        elif output_format == 'docx':
            _run_command(_docx_command(input_path, output_path))
        elif output_format == 'txt':
            _copy_as_text(input_path, output_path)
        else:
            _run_command(_generic_command(output_format, input_path,
                                          self.output_dir))

    def list_converted_files(self):
        return [f for f in os.listdir(self.output_dir)
                if not f.startswith('.')]

    def cleanup_conversions(self, older_than_days=DEFAULT_CLEANUP_DAYS):
        cutoff = datetime.now().timestamp() - older_than_days * SECONDS_PER_DAY
        for filename in os.listdir(self.output_dir):
            filepath = os.path.join(self.output_dir, filename)
            if os.path.getmtime(filepath) < cutoff:
                os.remove(filepath)
                print(f'Removed old conversion: {filename}')


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def print_menu():
    for line in MENU_LINES:
        print(line)


def _handle_convert(converter):
    input_path = input(PROMPT_INPUT_PATH)
    output_format = input(PROMPT_OUTPUT_FORMAT)
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
    days = input(PROMPT_CLEANUP_DAYS) or str(DEFAULT_CLEANUP_DAYS)
    converter.cleanup_conversions(int(days))


def main():
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
        else:
            handler(converter)


if __name__ == '__main__':
    main()
