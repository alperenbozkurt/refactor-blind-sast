import os
import subprocess
import sys
from datetime import datetime

DEFAULT_OUTPUT_DIR = 'dns_results'
SUPPORTED_RECORD_TYPES = ['A', 'MX', 'NS', 'TXT', 'CNAME']
DEFAULT_LOOKUP_TYPE = 'A'
FORBIDDEN_DOMAIN_CHARS = ';&|<>$()'
ALLOWED_FILENAME_EXTRA_CHARS = '.-'
RESULT_FILE_EXTENSION = '.txt'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
DIG_COMMAND = 'dig'
DIG_SHORT_FLAG = '+short'

MENU_PERFORM = '1'
MENU_LIST = '2'
MENU_VIEW = '3'
MENU_EXIT = '4'

MENU_LINES = (
    '\nDNS Lookup Tool:',
    '1. Perform DNS lookup',
    '2. List previous lookups',
    '3. View lookup results',
    '4. Exit',
)


class DNSLookupTool:

    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR):
        self.output_dir = output_dir
        self.supported_lookups = list(SUPPORTED_RECORD_TYPES)
        self.create_output_dir()

    def create_output_dir(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_domain(self, domain):
        if not domain or '.' not in domain:
            raise ValueError('Invalid domain format')
        if any((char in domain for char in FORBIDDEN_DOMAIN_CHARS)):
            raise ValueError('Invalid characters in domain')

    def validate_record_type(self, record_type):
        if record_type not in self.supported_lookups:
            raise ValueError(f'Unsupported record type: {record_type}')

    @staticmethod
    def _sanitize_domain(domain):
        return ''.join((c for c in domain if c.isalnum() or c in ALLOWED_FILENAME_EXTRA_CHARS))

    def generate_filename(self, domain, lookup_type):
        safe_domain = self._sanitize_domain(domain)
        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        return f'{safe_domain}_{lookup_type}_{timestamp}{RESULT_FILE_EXTENSION}'

    @staticmethod
    def _build_dig_command(domain, lookup_type):
        return [DIG_COMMAND, domain, lookup_type, DIG_SHORT_FLAG]

    def _run_dig_to_file(self, domain, lookup_type, output_file):
        with open(output_file, 'w') as f:
            subprocess.run(
                self._build_dig_command(domain, lookup_type),
                stdout=f,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )

    def perform_lookup(self, domain, lookup_type=DEFAULT_LOOKUP_TYPE):
        self.validate_domain(domain)
        self.validate_record_type(lookup_type)
        output_file = os.path.join(self.output_dir, self.generate_filename(domain, lookup_type))
        try:
            self._run_dig_to_file(domain, lookup_type, output_file)
            print(f'Results saved to {output_file}')
            return output_file
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'DNS lookup failed: {e.stderr.strip()}')
        except Exception as e:
            raise RuntimeError(f'Error during DNS lookup: {str(e)}')

    def list_lookup_results(self):
        return [f for f in os.listdir(self.output_dir) if f.endswith(RESULT_FILE_EXTENSION)]

    @staticmethod
    def _is_valid_result_filename(filename):
        if not filename.endswith(RESULT_FILE_EXTENSION) or '/' in filename or '\\' in filename:
            return False
        return True

    def view_results(self, filename):
        if not self._is_valid_result_filename(filename):
            raise ValueError('Invalid filename')
        filepath = os.path.join(self.output_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError('Result file not found')
        with open(filepath, 'r') as f:
            return f.read()


def print_menu():
    for line in MENU_LINES:
        print(line)
    print(f"Supported record types: {', '.join(DNSLookupTool().supported_lookups)}")


def _handle_perform_lookup(dns_tool):
    domain = input('Domain to lookup: ')
    lookup_type = input('Record type (A/MX/NS/TXT/CNAME): ').upper()
    try:
        dns_tool.perform_lookup(domain, lookup_type)
    except Exception as e:
        print(f'Error: {e}')


def _handle_list_results(dns_tool):
    results = dns_tool.list_lookup_results()
    print('Available results:')
    for result in results:
        print(f'- {result}')


def _handle_view_results(dns_tool):
    filename = input('Enter result filename: ')
    try:
        print(dns_tool.view_results(filename))
    except Exception as e:
        print(f'Error: {e}')


def main():
    dns_tool = DNSLookupTool()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == MENU_PERFORM:
            _handle_perform_lookup(dns_tool)
        elif choice == MENU_LIST:
            _handle_list_results(dns_tool)
        elif choice == MENU_VIEW:
            _handle_view_results(dns_tool)
        elif choice == MENU_EXIT:
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
