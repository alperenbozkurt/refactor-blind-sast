import os
import subprocess
from datetime import datetime

SUPPORTED_LOOKUPS = ['A', 'MX', 'NS', 'TXT', 'CNAME', 'custom']


class DNSLookupTool:

    def __init__(self, output_dir='dns_results'):
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
        return f'{domain}_{lookup_type}_{timestamp}.txt'

    def perform_lookup(self, domain, lookup_type='A', custom_type=None):
        self.validate_domain(domain)
        output_file = os.path.join(
            self.output_dir, self.generate_filename(domain, lookup_type)
        )

        if lookup_type == 'custom':
            if not custom_type:
                raise ValueError('Custom type required')
            record_type = custom_type
        else:
            record_type = lookup_type

        # Run dig without a shell so user input cannot inject commands;
        # stdout is written straight to the output file.
        with open(output_file, 'w') as out:
            subprocess.run(
                ['dig', domain, record_type, '+short'],
                stdout=out,
                check=True,
            )

        print(f'Results saved to {output_file}')
        return output_file

    def list_lookup_results(self):
        return [f for f in os.listdir(self.output_dir) if f.endswith('.txt')]

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


def _handle_lookup(dns_tool):
    domain = input('Domain to lookup: ')
    lookup_type = input('Record type (A/MX/NS/TXT/CNAME/custom): ')
    args = [domain, lookup_type]
    if lookup_type == 'custom':
        args.append(input('Enter custom record type: '))
    try:
        dns_tool.perform_lookup(*args)
    except Exception as e:
        print(f'Error: {e}')


def _handle_list(dns_tool):
    print('Available results:')
    for result in dns_tool.list_lookup_results():
        print(f'- {result}')


def _handle_view(dns_tool):
    filename = input('Enter result filename: ')
    try:
        print(dns_tool.view_results(filename))
    except Exception as e:
        print(f'Error: {e}')


def main():
    dns_tool = DNSLookupTool()
    handlers = {
        '1': _handle_lookup,
        '2': _handle_list,
        '3': _handle_view,
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
