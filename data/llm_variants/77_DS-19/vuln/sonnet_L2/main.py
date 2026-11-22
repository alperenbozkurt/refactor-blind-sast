import os
import subprocess
import sys
from datetime import datetime

DEFAULT_OUTPUT_DIR = 'dns_results'
SUPPORTED_LOOKUPS = ['A', 'MX', 'NS', 'TXT', 'CNAME', 'custom']
CUSTOM_LOOKUP = 'custom'
DEFAULT_LOOKUP_TYPE = 'A'
RESULT_EXTENSION = '.txt'
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
    'Supported record types: A, MX, NS, TXT, CNAME, custom',
)


class DNSLookupTool:

    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR):
        self.output_dir = output_dir
        self.supported_lookups = list(SUPPORTED_LOOKUPS)
        self.create_output_dir()

    def create_output_dir(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_domain(self, domain):
        if not domain or '.' not in domain:
            raise ValueError('Invalid domain format')

    def generate_filename(self, domain, lookup_type):
        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        return f'{domain}_{lookup_type}_{timestamp}{RESULT_EXTENSION}'

    def _resolve_record_type(self, lookup_type, custom_type):
        if lookup_type == CUSTOM_LOOKUP:
            if not custom_type:
                raise ValueError('Custom type required')
            return custom_type
        return lookup_type

    def _build_command(self, domain, record_type):
        # Arguments are passed as a list (no shell) so user input cannot
        # inject shell commands.
        return [DIG_COMMAND, domain, record_type, DIG_SHORT_FLAG]

    def _run_dig_to_file(self, cmd, output_file):
        with open(output_file, 'w') as out:
            subprocess.run(cmd, stdout=out, check=True)

    def perform_lookup(self, domain, lookup_type=DEFAULT_LOOKUP_TYPE, custom_type=None):
        self.validate_domain(domain)
        output_file = os.path.join(self.output_dir, self.generate_filename(domain, lookup_type))
        record_type = self._resolve_record_type(lookup_type, custom_type)
        cmd = self._build_command(domain, record_type)
        self._run_dig_to_file(cmd, output_file)
        print(f'Results saved to {output_file}')
        return output_file

    def list_lookup_results(self):
        return [f for f in os.listdir(self.output_dir) if f.endswith(RESULT_EXTENSION)]

    def view_results(self, filename):
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'r') as f:
            return f.read()


def print_menu():
    for line in MENU_LINES:
        print(line)


def _handle_perform_lookup(dns_tool):
    domain = input('Domain to lookup: ')
    lookup_type = input('Record type (A/MX/NS/TXT/CNAME/custom): ')
    if lookup_type == CUSTOM_LOOKUP:
        custom_type = input('Enter custom record type: ')
        args = (domain, lookup_type, custom_type)
    else:
        args = (domain, lookup_type)
    try:
        dns_tool.perform_lookup(*args)
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
