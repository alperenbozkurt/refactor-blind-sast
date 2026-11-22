"""Command line DNS query tool built on top of the ``dig`` utility."""

import argparse
import re
import subprocess
import sys
from typing import List, Optional, Dict

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DEFAULT_NAMESERVER = '8.8.8.8'
DIG_EXECUTABLE = 'dig'
SHORT_OUTPUT_FLAG = '+short'
DOMAIN_PATTERN = r'^([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,}$'

CLI_DESCRIPTION = 'DNS Query Tool'

ERROR_INVALID_DOMAIN = 'Invalid domain: {}'
ERROR_INVALID_QUERY_TYPE = 'Invalid query type: {}'
ERROR_QUERY_FAILED = 'Query failed: {}'
NO_RECORDS_MESSAGE = 'None found'


# ---------------------------------------------------------------------------
# Small helper functions
# ---------------------------------------------------------------------------

def _build_dig_command(nameserver: str, domain: str, record_type: str) -> List[str]:
    """Build the ``dig`` command line for a ``+short`` query."""
    return [DIG_EXECUTABLE, f'@{nameserver}', domain, record_type, SHORT_OUTPUT_FLAG]


def _report_error(message: str) -> None:
    """Write an error message to standard error."""
    print(message, file=sys.stderr)


def _parse_short_output(stdout: str) -> List[str]:
    """Turn ``dig +short`` output into a list of trimmed, non-empty lines."""
    return [line.strip() for line in stdout.splitlines() if line.strip()]


def _format_record_list(records: List[str]) -> str:
    """Render a record list for display, using a placeholder when empty."""
    return ', '.join(records) if records else NO_RECORDS_MESSAGE


# ---------------------------------------------------------------------------
# DNS tool
# ---------------------------------------------------------------------------

class DNSTool:
    """Validate and run DNS queries against a configurable nameserver."""

    VALID_QUERY_TYPES = {'A', 'AAAA', 'MX', 'TXT', 'CNAME', 'NS', 'SOA', 'PTR', 'SRV'}

    def __init__(self, nameserver: str = DEFAULT_NAMESERVER):
        self.nameserver = nameserver
        self.cache: Dict[str, str] = {}

    def validate_domain(self, domain: str) -> bool:
        return re.match(DOMAIN_PATTERN, domain, re.IGNORECASE) is not None

    def validate_query_type(self, query_type: str) -> bool:
        return query_type.upper() in self.VALID_QUERY_TYPES

    def query_a_record(self, domain: str) -> List[str]:
        return self._query_short_records(domain, 'A')

    def query_mx_records(self, domain: str) -> List[str]:
        return self._query_short_records(domain, 'MX')

    def custom_query(self, domain: str, query_type: str) -> Optional[str]:
        if not self.validate_domain(domain):
            _report_error(ERROR_INVALID_DOMAIN.format(domain))
            return None
        if not self.validate_query_type(query_type):
            _report_error(ERROR_INVALID_QUERY_TYPE.format(query_type))
            return None
        try:
            result = subprocess.run(
                _build_dig_command(self.nameserver, domain, query_type.upper()),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            return result.stdout.strip() if result.stdout else None
        except Exception as e:
            _report_error(ERROR_QUERY_FAILED.format(e))
            return None

    def _query_short_records(self, domain: str, record_type: str) -> List[str]:
        """Run a strict ``dig +short`` query and return the answer lines."""
        if not self.validate_domain(domain):
            _report_error(ERROR_INVALID_DOMAIN.format(domain))
            return []
        try:
            result = subprocess.run(
                _build_dig_command(self.nameserver, domain, record_type),
                capture_output=True,
                text=True,
                check=True,
            )
            return _parse_short_output(result.stdout)
        except subprocess.CalledProcessError as e:
            _report_error(ERROR_QUERY_FAILED.format(e.stderr))
            return []


# ---------------------------------------------------------------------------
# Command line interface
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for the command line interface."""
    parser = argparse.ArgumentParser(description=CLI_DESCRIPTION)
    parser.add_argument('--server', default=DEFAULT_NAMESERVER,
                        help='DNS server to use')
    subparsers = parser.add_subparsers(dest='command', required=True)

    a_parser = subparsers.add_parser('a', help='Query A records')
    a_parser.add_argument('domain', help='Domain to query')

    mx_parser = subparsers.add_parser('mx', help='Query MX records')
    mx_parser.add_argument('domain', help='Domain to query')

    custom_parser = subparsers.add_parser('custom', help='Custom DNS query')
    custom_parser.add_argument('domain', help='Domain to query')
    custom_parser.add_argument('type', help='Query type (A, MX, TXT, etc.)')

    return parser


def _run_a_command(tool: DNSTool, args: argparse.Namespace) -> None:
    records = tool.query_a_record(args.domain)
    print('A records:', _format_record_list(records))


def _run_mx_command(tool: DNSTool, args: argparse.Namespace) -> None:
    records = tool.query_mx_records(args.domain)
    print('MX records:', _format_record_list(records))


def _run_custom_command(tool: DNSTool, args: argparse.Namespace) -> None:
    result = tool.custom_query(args.domain, args.type)
    print(f'{args.type} record:', result if result else NO_RECORDS_MESSAGE)


_COMMAND_HANDLERS = {
    'a': _run_a_command,
    'mx': _run_mx_command,
    'custom': _run_custom_command,
}


def main():
    args = _build_parser().parse_args()
    tool = DNSTool(args.server)
    handler = _COMMAND_HANDLERS.get(args.command)
    if handler is not None:
        handler(tool, args)


if __name__ == '__main__':
    main()
