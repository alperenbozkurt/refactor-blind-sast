import os
import subprocess
import sys
from datetime import datetime


class DNSLookupTool:
    """Run DNS lookups with dig and store the results on disk."""

    def __init__(self, output_dir='dns_results'):
        self.output_dir = output_dir
        self.supported_lookups = ['A', 'MX', 'NS', 'TXT', 'CNAME', 'custom']
        self.create_output_dir()

    def create_output_dir(self):
        """Create the output directory if it does not exist yet."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_domain(self, domain):
        """Reject empty domains and domains without a dot."""
        if not domain or '.' not in domain:
            raise ValueError('Invalid domain format')

    def generate_filename(self, domain, lookup_type):
        """Build a timestamped result filename for a lookup."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{domain}_{lookup_type}_{timestamp}.txt'

    def perform_lookup(self, domain, lookup_type='A', custom_type=None):
        """Run a dig lookup and write the short output to a result file."""
        self.validate_domain(domain)
        output_file = os.path.join(self.output_dir, self.generate_filename(domain, lookup_type))
        record_type = self._resolve_record_type(lookup_type, custom_type)
        cmd = f'dig {domain} {record_type} +short > {output_file}'
        subprocess.run(cmd, shell=True, check=True)
        print(f'Results saved to {output_file}')
        return output_file

    def _resolve_record_type(self, lookup_type, custom_type):
        """Return the record type to query, validating custom lookups."""
        if lookup_type == 'custom':
            if not custom_type:
                raise ValueError('Custom type required')
            return custom_type
        return lookup_type

    def list_lookup_results(self):
        """Return the names of all result files in the output directory."""
        return [f for f in os.listdir(self.output_dir) if f.endswith('.txt')]

    def view_results(self, filename):
        """Return the contents of a stored result file."""
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


def _handle_lookup(dns_tool):
    domain = input('Domain to lookup: ')
    lookup_type = input('Record type (A/MX/NS/TXT/CNAME/custom): ')
    custom_type = None
    if lookup_type == 'custom':
        custom_type = input('Enter custom record type: ')
    try:
        dns_tool.perform_lookup(domain, lookup_type, custom_type)
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
    handlers = {
        '1': _handle_lookup,
        '2': _handle_list_results,
        '3': _handle_view_results,
    }
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '4':
            print('Exiting...')
            break
        handler = handlers.get(choice)
        if handler:
            handler(dns_tool)
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
