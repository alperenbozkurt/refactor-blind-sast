import subprocess
import argparse
import sys
import re
from typing import List, Optional, Dict

DEFAULT_NAMESERVER = '8.8.8.8'
DIG_BINARY = 'dig'
DIG_SHORT_FLAG = '+short'
DOMAIN_PATTERN = '^([a-z0-9]+(-[a-z0-9]+)*\\.)+[a-z]{2,}$'
_DOMAIN_REGEX = re.compile(DOMAIN_PATTERN, re.IGNORECASE)

RECORD_TYPE_A = 'A'
RECORD_TYPE_MX = 'MX'
NONE_FOUND_MESSAGE = 'None found'

COMMAND_A = 'a'
COMMAND_MX = 'mx'
COMMAND_CUSTOM = 'custom'


def _log_error(message: str) -> None:
    print(message, file=sys.stderr)


def _non_empty_stripped_lines(text: str) -> List[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _format_records(records: List[str]) -> str:
    return ', '.join(records) if records else NONE_FOUND_MESSAGE


class DNSTool:
    VALID_QUERY_TYPES = {'A', 'AAAA', 'MX', 'TXT', 'CNAME', 'NS', 'SOA', 'PTR', 'SRV'}

    def __init__(self, nameserver: str=DEFAULT_NAMESERVER):
        self.nameserver = nameserver
        self.cache: Dict[str, str] = {}

    # ----- validation -----

    def validate_domain(self, domain: str) -> bool:
        return _DOMAIN_REGEX.match(domain) is not None

    def validate_query_type(self, query_type: str) -> bool:
        return query_type.upper() in self.VALID_QUERY_TYPES

    def _check_domain(self, domain: str) -> bool:
        """Validate a domain, reporting to stderr if invalid."""
        if not self.validate_domain(domain):
            _log_error(f'Invalid domain: {domain}')
            return False
        return True

    def _check_query_type(self, query_type: str) -> bool:
        """Validate a query type, reporting to stderr if invalid."""
        if not self.validate_query_type(query_type):
            _log_error(f'Invalid query type: {query_type}')
            return False
        return True

    # ----- command execution -----

    def _build_command(self, domain: str, record_type: str) -> List[str]:
        return [DIG_BINARY, f'@{self.nameserver}', domain, record_type, DIG_SHORT_FLAG]

    def _query_records(self, domain: str, record_type: str) -> List[str]:
        """Run a checked dig query and return its non-empty output lines."""
        if not self._check_domain(domain):
            return []
        try:
            cmd = self._build_command(domain, record_type)
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return _non_empty_stripped_lines(result.stdout)
        except subprocess.CalledProcessError as e:
            _log_error(f'Query failed: {e.stderr}')
            return []

    # ----- public API -----

    def query_a_record(self, domain: str) -> List[str]:
        return self._query_records(domain, RECORD_TYPE_A)

    def query_mx_records(self, domain: str) -> List[str]:
        return self._query_records(domain, RECORD_TYPE_MX)

    def custom_query(self, domain: str, query_type: str) -> Optional[str]:
        if not self._check_domain(domain):
            return None
        if not self._check_query_type(query_type):
            return None
        try:
            cmd = self._build_command(domain, query_type.upper())
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            return result.stdout.strip() if result.stdout else None
        except Exception as e:
            _log_error(f'Query failed: {e}')
            return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='DNS Query Tool')
    parser.add_argument('--server', default=DEFAULT_NAMESERVER, help='DNS server to use')
    subparsers = parser.add_subparsers(dest='command', required=True)
    a_parser = subparsers.add_parser(COMMAND_A, help='Query A records')
    a_parser.add_argument('domain', help='Domain to query')
    mx_parser = subparsers.add_parser(COMMAND_MX, help='Query MX records')
    mx_parser.add_argument('domain', help='Domain to query')
    custom_parser = subparsers.add_parser(COMMAND_CUSTOM, help='Custom DNS query')
    custom_parser.add_argument('domain', help='Domain to query')
    custom_parser.add_argument('type', help='Query type (A, MX, TXT, etc.)')
    return parser


def _handle_a(tool: DNSTool, args: argparse.Namespace) -> None:
    records = tool.query_a_record(args.domain)
    print('A records:', _format_records(records))


def _handle_mx(tool: DNSTool, args: argparse.Namespace) -> None:
    records = tool.query_mx_records(args.domain)
    print('MX records:', _format_records(records))


def _handle_custom(tool: DNSTool, args: argparse.Namespace) -> None:
    result = tool.custom_query(args.domain, args.type)
    print(f'{args.type} record:', result if result else NONE_FOUND_MESSAGE)


_COMMAND_HANDLERS = {
    COMMAND_A: _handle_a,
    COMMAND_MX: _handle_mx,
    COMMAND_CUSTOM: _handle_custom,
}


def main():
    parser = _build_parser()
    args = parser.parse_args()
    tool = DNSTool(args.server)
    handler = _COMMAND_HANDLERS.get(args.command)
    if handler is not None:
        handler(tool, args)


if __name__ == '__main__':
    main()
