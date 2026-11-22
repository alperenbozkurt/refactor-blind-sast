"""Interactive DNS lookup tool.

Provides a small command-line interface around the ``dig`` utility and
stores lookup results as timestamped text files.
"""

import os
import subprocess
import sys
from datetime import datetime


class DNSLookupTool:
    """Perform DNS lookups and manage the saved result files."""

    SUPPORTED_LOOKUPS = ['A', 'MX', 'NS', 'TXT', 'CNAME']
    INVALID_DOMAIN_CHARS = frozenset(';&|<>$()')
    TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

    def __init__(self, output_dir='dns_results'):
        self.output_dir = output_dir
        self.supported_lookups = list(self.SUPPORTED_LOOKUPS)
        self.create_output_dir()

    def create_output_dir(self):
        """Create the output directory if it does not exist yet."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_domain(self, domain):
        """Ensure the domain has a valid format and no dangerous characters."""
        if not domain or '.' not in domain:
            raise ValueError('Invalid domain format')
        if any(char in domain for char in self.INVALID_DOMAIN_CHARS):
            raise ValueError('Invalid characters in domain')

    def validate_record_type(self, record_type):
        """Ensure the requested record type is supported."""
        if record_type not in self.supported_lookups:
            raise ValueError(f'Unsupported record type: {record_type}')

    def generate_filename(self, domain, lookup_type):
        """Build a safe, timestamped filename for a lookup result."""
        safe_domain = ''.join(c for c in domain if c.isalnum() or c in '.-')
        timestamp = datetime.now().strftime(self.TIMESTAMP_FORMAT)
        return f'{safe_domain}_{lookup_type}_{timestamp}.txt'

    def perform_lookup(self, domain, lookup_type='A'):
        """Run ``dig`` for the domain and save the output to a file."""
        self.validate_domain(domain)
        self.validate_record_type(lookup_type)
        output_file = os.path.join(
            self.output_dir, self.generate_filename(domain, lookup_type)
        )
        command = ['dig', domain, lookup_type, '+short']
        try:
            with open(output_file, 'w') as f:
                subprocess.run(
                    command,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                )
            print(f'Results saved to {output_file}')
            return output_file
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'DNS lookup failed: {e.stderr.strip()}')
        except Exception as e:
            raise RuntimeError(f'Error during DNS lookup: {str(e)}')

    def list_lookup_results(self):
        """Return the names of all saved result files."""
        return [f for f in os.listdir(self.output_dir) if f.endswith('.txt')]

    def view_results(self, filename):
        """Return the contents of a previously saved result file."""
        if not filename.endswith('.txt') or '/' in filename or '\\' in filename:
            raise ValueError('Invalid filename')
        filepath = os.path.join(self.output_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError('Result file not found')
        with open(filepath, 'r') as f:
            return f.read()


def print_menu():
    """Print the main menu and the supported record types."""
    print('\nDNS Lookup Tool:')
    print('1. Perform DNS lookup')
    print('2. List previous lookups')
    print('3. View lookup results')
    print('4. Exit')
    print(f"Supported record types: {', '.join(DNSLookupTool().supported_lookups)}")


def main():
    """Run the interactive command-line interface."""
    dns_tool = DNSLookupTool()

    def handle_lookup():
        domain = input('Domain to lookup: ')
        lookup_type = input('Record type (A/MX/NS/TXT/CNAME): ').upper()
        try:
            dns_tool.perform_lookup(domain, lookup_type)
        except Exception as e:
            print(f'Error: {e}')

    def handle_list_results():
        results = dns_tool.list_lookup_results()
        print('Available results:')
        for result in results:
            print(f'- {result}')

    def handle_view_results():
        filename = input('Enter result filename: ')
        try:
            print(dns_tool.view_results(filename))
        except Exception as e:
            print(f'Error: {e}')

    handlers = {
        '1': handle_lookup,
        '2': handle_list_results,
        '3': handle_view_results,
    }

    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '4':
            print('Exiting...')
            break
        handler = handlers.get(choice)
        if handler is None:
            print('Invalid choice. Please try again.')
        else:
            handler()


if __name__ == '__main__':
    main()
