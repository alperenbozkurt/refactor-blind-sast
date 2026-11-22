"""Command-line DNS lookup tool.

Provides the :class:`DNSLookupTool` class for running ``dig`` queries and
storing their output, plus a small interactive CLI.

The public API (module-level names, classes, method signatures and the
command-line interface) is unchanged; the internals have been reorganised
into named constants, an immutable configuration object and small helper
functions.
"""

import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = 'dns_results'
DEFAULT_RECORD_TYPE = 'A'
SUPPORTED_RECORD_TYPES = ('A', 'MX', 'NS', 'TXT', 'CNAME')

DOMAIN_REQUIRED_CHAR = '.'
FORBIDDEN_DOMAIN_CHARS = ';&|<>$()'
SAFE_DOMAIN_EXTRA_CHARS = '.-'

TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
RESULTS_FILE_EXTENSION = '.txt'

DIG_EXECUTABLE = 'dig'
DIG_SHORT_FLAG = '+short'

ERROR_INVALID_DOMAIN_FORMAT = 'Invalid domain format'
ERROR_INVALID_DOMAIN_CHARS = 'Invalid characters in domain'
ERROR_INVALID_FILENAME = 'Invalid filename'
ERROR_RESULT_NOT_FOUND = 'Result file not found'

MENU_LINES = (
    '\nDNS Lookup Tool:',
    '1. Perform DNS lookup',
    '2. List previous lookups',
    '3. View lookup results',
    '4. Exit',
)

PROMPT_CHOICE = 'Enter your choice: '
PROMPT_DOMAIN = 'Domain to lookup: '
PROMPT_RECORD_TYPE = 'Record type (A/MX/NS/TXT/CNAME): '
PROMPT_FILENAME = 'Enter result filename: '

CHOICE_LOOKUP = '1'
CHOICE_LIST = '2'
CHOICE_VIEW = '3'
CHOICE_EXIT = '4'

MSG_AVAILABLE_RESULTS = 'Available results:'
MSG_EXITING = 'Exiting...'
MSG_INVALID_CHOICE = 'Invalid choice. Please try again.'


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DNSLookupConfig:
    """Immutable settings used by :class:`DNSLookupTool`."""

    output_dir: str = DEFAULT_OUTPUT_DIR
    record_types: tuple = SUPPORTED_RECORD_TYPES
    timestamp_format: str = TIMESTAMP_FORMAT
    results_extension: str = RESULTS_FILE_EXTENSION
    dig_executable: str = DIG_EXECUTABLE
    dig_short_flag: str = DIG_SHORT_FLAG


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _contains_any(text, chars):
    """Return True if any character from *chars* appears in *text*."""
    return any(char in text for char in chars)


def _sanitize_domain(domain):
    """Keep only alphanumeric characters, dots and hyphens."""
    return ''.join(
        c for c in domain if c.isalnum() or c in SAFE_DOMAIN_EXTRA_CHARS
    )


def _current_timestamp(fmt):
    """Return the current time formatted with *fmt*."""
    return datetime.now().strftime(fmt)


def _is_valid_result_filename(filename, extension):
    """Return True for result file names without path separators."""
    return (
        filename.endswith(extension)
        and '/' not in filename
        and '\\' not in filename
    )


def _build_dig_command(domain, lookup_type, config):
    """Build the ``dig`` command line for *domain* and *lookup_type*."""
    return [config.dig_executable, domain, lookup_type, config.dig_short_flag]


def _read_text_file(filepath):
    """Read and return the entire contents of a text file."""
    with open(filepath, 'r') as f:
        return f.read()


# ---------------------------------------------------------------------------
# Core class
# ---------------------------------------------------------------------------

class DNSLookupTool:

    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR):
        self.config = DNSLookupConfig(output_dir=output_dir)
        self.output_dir = output_dir
        self.supported_lookups = list(self.config.record_types)
        self.create_output_dir()

    def create_output_dir(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_domain(self, domain):
        if not domain or DOMAIN_REQUIRED_CHAR not in domain:
            raise ValueError(ERROR_INVALID_DOMAIN_FORMAT)
        if _contains_any(domain, FORBIDDEN_DOMAIN_CHARS):
            raise ValueError(ERROR_INVALID_DOMAIN_CHARS)

    def validate_record_type(self, record_type):
        if record_type not in self.supported_lookups:
            raise ValueError(f'Unsupported record type: {record_type}')

    def generate_filename(self, domain, lookup_type):
        safe_domain = _sanitize_domain(domain)
        timestamp = _current_timestamp(self.config.timestamp_format)
        extension = self.config.results_extension
        return f'{safe_domain}_{lookup_type}_{timestamp}{extension}'

    def perform_lookup(self, domain, lookup_type=DEFAULT_RECORD_TYPE):
        self.validate_domain(domain)
        self.validate_record_type(lookup_type)
        output_file = os.path.join(
            self.output_dir, self.generate_filename(domain, lookup_type)
        )
        try:
            with open(output_file, 'w') as f:
                subprocess.run(
                    _build_dig_command(domain, lookup_type, self.config),
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
        return [
            f
            for f in os.listdir(self.output_dir)
            if f.endswith(self.config.results_extension)
        ]

    def view_results(self, filename):
        if not _is_valid_result_filename(filename, self.config.results_extension):
            raise ValueError(ERROR_INVALID_FILENAME)
        filepath = os.path.join(self.output_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(ERROR_RESULT_NOT_FOUND)
        return _read_text_file(filepath)


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def print_menu():
    for line in MENU_LINES:
        print(line)
    print(f"Supported record types: {', '.join(DNSLookupTool().supported_lookups)}")


def _handle_lookup(dns_tool):
    domain = input(PROMPT_DOMAIN)
    lookup_type = input(PROMPT_RECORD_TYPE).upper()
    try:
        dns_tool.perform_lookup(domain, lookup_type)
    except Exception as e:
        print(f'Error: {e}')


def _handle_list(dns_tool):
    results = dns_tool.list_lookup_results()
    print(MSG_AVAILABLE_RESULTS)
    for result in results:
        print(f'- {result}')


def _handle_view(dns_tool):
    filename = input(PROMPT_FILENAME)
    try:
        print(dns_tool.view_results(filename))
    except Exception as e:
        print(f'Error: {e}')


def main():
    dns_tool = DNSLookupTool()
    while True:
        print_menu()
        choice = input(PROMPT_CHOICE)
        if choice == CHOICE_LOOKUP:
            _handle_lookup(dns_tool)
        elif choice == CHOICE_LIST:
            _handle_list(dns_tool)
        elif choice == CHOICE_VIEW:
            _handle_view(dns_tool)
        elif choice == CHOICE_EXIT:
            print(MSG_EXITING)
            break
        else:
            print(MSG_INVALID_CHOICE)


if __name__ == '__main__':
    main()
