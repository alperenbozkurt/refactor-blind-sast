"""Interactive command-line DNS lookup tool.

Runs ``dig`` lookups for a domain and stores the results as timestamped
text files so they can be listed and reviewed later.
"""

import os
import subprocess
import sys
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = 'dns_results'
RESULTS_FILE_EXTENSION = '.txt'
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

CUSTOM_LOOKUP_TYPE = 'custom'
SUPPORTED_LOOKUP_TYPES = ('A', 'MX', 'NS', 'TXT', 'CNAME', CUSTOM_LOOKUP_TYPE)

DIG_COMMAND_TEMPLATE = 'dig {domain} {record_type} +short > {output_file}'
FILENAME_TEMPLATE = '{domain}_{lookup_type}_{timestamp}' + RESULTS_FILE_EXTENSION

ERROR_INVALID_DOMAIN = 'Invalid domain format'
ERROR_CUSTOM_TYPE_REQUIRED = 'Custom type required'

# ---------------------------------------------------------------------------
# Command-line interface text
# ---------------------------------------------------------------------------

CHOICE_LOOKUP = '1'
CHOICE_LIST_RESULTS = '2'
CHOICE_VIEW_RESULTS = '3'
CHOICE_EXIT = '4'

MENU_TITLE = '\nDNS Lookup Tool:'
MENU_ITEMS = (
    (CHOICE_LOOKUP, 'Perform DNS lookup'),
    (CHOICE_LIST_RESULTS, 'List previous lookups'),
    (CHOICE_VIEW_RESULTS, 'View lookup results'),
    (CHOICE_EXIT, 'Exit'),
)
SUPPORTED_LOOKUPS_LABEL = (
    'Supported record types: ' + ', '.join(SUPPORTED_LOOKUP_TYPES)
)

PROMPT_CHOICE = 'Enter your choice: '
PROMPT_DOMAIN = 'Domain to lookup: '
PROMPT_RECORD_TYPE = (
    'Record type (' + '/'.join(SUPPORTED_LOOKUP_TYPES) + '): '
)
PROMPT_CUSTOM_TYPE = 'Enter custom record type: '
PROMPT_RESULT_FILENAME = 'Enter result filename: '

MESSAGE_AVAILABLE_RESULTS = 'Available results:'
MESSAGE_EXITING = 'Exiting...'
MESSAGE_INVALID_CHOICE = 'Invalid choice. Please try again.'


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _build_dig_command(domain, record_type, output_file):
    """Build the shell command used to run a ``dig`` lookup."""
    return DIG_COMMAND_TEMPLATE.format(
        domain=domain,
        record_type=record_type,
        output_file=output_file,
    )


def _resolve_record_type(lookup_type, custom_type):
    """Return the record type to query, validating custom lookups."""
    if lookup_type == CUSTOM_LOOKUP_TYPE:
        if not custom_type:
            raise ValueError(ERROR_CUSTOM_TYPE_REQUIRED)
        return custom_type
    return lookup_type


def _read_text_file(filepath):
    """Return the full contents of a text file."""
    with open(filepath, 'r') as file_handle:
        return file_handle.read()


def _print_error(error):
    """Print an exception using the CLI's standard error format."""
    print(f'Error: {error}')


# ---------------------------------------------------------------------------
# DNS lookup tool
# ---------------------------------------------------------------------------

class DNSLookupTool:
    """Perform DNS lookups and manage the stored result files."""

    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR):
        self.output_dir = output_dir
        self.supported_lookups = list(SUPPORTED_LOOKUP_TYPES)
        self.create_output_dir()

    def create_output_dir(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_domain(self, domain):
        if not domain or '.' not in domain:
            raise ValueError(ERROR_INVALID_DOMAIN)

    def generate_filename(self, domain, lookup_type):
        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        return FILENAME_TEMPLATE.format(
            domain=domain,
            lookup_type=lookup_type,
            timestamp=timestamp,
        )

    def perform_lookup(self, domain, lookup_type='A', custom_type=None):
        self.validate_domain(domain)
        output_file = os.path.join(
            self.output_dir,
            self.generate_filename(domain, lookup_type),
        )
        record_type = _resolve_record_type(lookup_type, custom_type)
        command = _build_dig_command(domain, record_type, output_file)
        subprocess.run(command, shell=True, check=True)
        print(f'Results saved to {output_file}')
        return output_file

    def list_lookup_results(self):
        return [
            filename
            for filename in os.listdir(self.output_dir)
            if filename.endswith(RESULTS_FILE_EXTENSION)
        ]

    def view_results(self, filename):
        filepath = os.path.join(self.output_dir, filename)
        return _read_text_file(filepath)


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def print_menu():
    """Print the main menu."""
    print(MENU_TITLE)
    for choice, label in MENU_ITEMS:
        print(f'{choice}. {label}')
    print(SUPPORTED_LOOKUPS_LABEL)


def _handle_lookup(dns_tool):
    domain = input(PROMPT_DOMAIN)
    lookup_type = input(PROMPT_RECORD_TYPE)
    custom_type = None
    if lookup_type == CUSTOM_LOOKUP_TYPE:
        custom_type = input(PROMPT_CUSTOM_TYPE)
    try:
        dns_tool.perform_lookup(domain, lookup_type, custom_type)
    except Exception as error:
        _print_error(error)


def _handle_list_results(dns_tool):
    results = dns_tool.list_lookup_results()
    print(MESSAGE_AVAILABLE_RESULTS)
    for result in results:
        print(f'- {result}')


def _handle_view_results(dns_tool):
    filename = input(PROMPT_RESULT_FILENAME)
    try:
        print(dns_tool.view_results(filename))
    except Exception as error:
        _print_error(error)


def main():
    dns_tool = DNSLookupTool()
    handlers = {
        CHOICE_LOOKUP: _handle_lookup,
        CHOICE_LIST_RESULTS: _handle_list_results,
        CHOICE_VIEW_RESULTS: _handle_view_results,
    }
    while True:
        print_menu()
        choice = input(PROMPT_CHOICE)
        if choice == CHOICE_EXIT:
            print(MESSAGE_EXITING)
            break
        handler = handlers.get(choice)
        if handler is None:
            print(MESSAGE_INVALID_CHOICE)
        else:
            handler(dns_tool)


if __name__ == '__main__':
    main()
