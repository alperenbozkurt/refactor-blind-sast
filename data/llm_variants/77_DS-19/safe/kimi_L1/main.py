"""Interactive command-line DNS lookup tool.

Runs ``dig`` queries for common record types, stores the results in
timestamped text files and lets the user list and view previous results.
"""

import os
import subprocess
import sys
from datetime import datetime


class DNSLookupTool:
    """Perform DNS lookups with ``dig`` and manage the saved result files."""

    def __init__(self, output_dir='dns_results'):
        self.output_dir = output_dir
        self.supported_lookups = ['A', 'MX', 'NS', 'TXT', 'CNAME']
        self.create_output_dir()

    def create_output_dir(self):
        """Create the output directory if it does not already exist."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_domain(self, domain):
        """Reject empty or malformed domains and shell metacharacters."""
        if not domain or '.' not in domain:
            raise ValueError('Invalid domain format')
        if any(char in domain for char in ';&|<>$()'):
            raise ValueError('Invalid characters in domain')

    def validate_record_type(self, record_type):
        """Reject record types that are not in ``supported_lookups``."""
        if record_type not in self.supported_lookups:
            raise ValueError(f'Unsupported record type: {record_type}')

    def generate_filename(self, domain, lookup_type):
        """Build a filesystem-safe, timestamped result filename."""
        safe_domain = ''.join(c for c in domain if c.isalnum() or c in '.-')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{safe_domain}_{lookup_type}_{timestamp}.txt'

    def perform_lookup(self, domain, lookup_type='A'):
        """Run a ``dig`` lookup and save the short output to a new file.

        Returns the path of the file the results were written to.
        """
        self.validate_domain(domain)
        self.validate_record_type(lookup_type)

        output_file = os.path.join(
            self.output_dir, self.generate_filename(domain, lookup_type)
        )

        try:
            with open(output_file, 'w') as f:
                subprocess.run(
                    ['dig', domain, lookup_type, '+short'],
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
        """Return the names of all result files in the output directory."""
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
    """Run the interactive menu loop until the user chooses to exit."""
    dns_tool = DNSLookupTool()

    while True:
        print_menu()
        choice = input('Enter your choice: ')

        if choice == '1':
            domain = input('Domain to lookup: ')
            lookup_type = input('Record type (A/MX/NS/TXT/CNAME): ').upper()
            try:
                dns_tool.perform_lookup(domain, lookup_type)
            except Exception as e:
                print(f'Error: {e}')

        elif choice == '2':
            results = dns_tool.list_lookup_results()
            print('Available results:')
            for result in results:
                print(f'- {result}')

        elif choice == '3':
            filename = input('Enter result filename: ')
            try:
                print(dns_tool.view_results(filename))
            except Exception as e:
                print(f'Error: {e}')

        elif choice == '4':
            print('Exiting...')
            break

        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
