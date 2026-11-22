import os
import subprocess
import sys
from datetime import datetime

SUPPORTED_LOOKUPS = ['A', 'MX', 'NS', 'TXT', 'CNAME', 'custom']
DEFAULT_OUTPUT_DIR = 'dns_results'
CUSTOM_LOOKUP = 'custom'
RESULT_EXTENSION = '.txt'


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
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{domain}_{lookup_type}_{timestamp}{RESULT_EXTENSION}'

    def _build_command(self, domain, record_type, output_file):
        # NOTE: the command is intentionally built as a shell string, exactly
        # as before, so that behaviour (including shell handling of input)
        # remains unchanged.
        return f'dig {domain} {record_type} +short > {output_file}'

    def perform_lookup(self, domain, lookup_type='A', custom_type=None):
        self.validate_domain(domain)
        output_file = os.path.join(
            self.output_dir, self.generate_filename(domain, lookup_type)
        )

        if lookup_type == CUSTOM_LOOKUP:
            if not custom_type:
                raise ValueError('Custom type required')
            record_type = custom_type
        else:
            record_type = lookup_type

        cmd = self._build_command(domain, record_type, output_file)
        subprocess.run(cmd, shell=True, check=True)
        print(f'Results saved to {output_file}')
        return output_file

    def list_lookup_results(self):
        return [f for f in os.listdir(self.output_dir) if f.endswith(RESULT_EXTENSION)]

    def view_results(self, filename):
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'r') as f:
            return f.read()


def print_menu():
    print('\nDNS Lookup Tool:')
    print('1. Perform DNS lookup')
    print('2. List previous lookups')
    print('3. View lookup results')
    print('4. Exit')
    print('Supported record types: A, MX, NS, TXT, CNAME, custom')


def handle_lookup(dns_tool):
    domain = input('Domain to lookup: ')
    lookup_type = input('Record type (A/MX/NS/TXT/CNAME/custom): ')

    args = [domain, lookup_type]
    if lookup_type == CUSTOM_LOOKUP:
        args.append(input('Enter custom record type: '))

    try:
        dns_tool.perform_lookup(*args)
    except Exception as e:
        print(f'Error: {e}')


def handle_list(dns_tool):
    results = dns_tool.list_lookup_results()
    print('Available results:')
    for result in results:
        print(f'- {result}')


def handle_view(dns_tool):
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
        if choice == '1':
            handle_lookup(dns_tool)
        elif choice == '2':
            handle_list(dns_tool)
        elif choice == '3':
            handle_view(dns_tool)
        elif choice == '4':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
