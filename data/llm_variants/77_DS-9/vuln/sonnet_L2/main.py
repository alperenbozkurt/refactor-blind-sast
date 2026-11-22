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
NONE_FOUND_TEXT = 'None found'

COMMAND_A = 'a'
COMMAND_MX = 'mx'
COMMAND_CUSTOM = 'custom'


def _log_error(message: str) -> None:
    print(message, file=sys.stderr)


def _non_empty_lines(output: str) -> List[str]:
    """Split command output into stripped, non-empty lines."""
    return [line.strip() for line in output.splitlines() if line.strip()]


class DNSTool:

    def __init__(self, nameserver: str=DEFAULT_NAMESERVER):
        self.nameserver = nameserver
        self.cache: Dict[str, str] = {}

    def validate_domain(self, domain: str) -> bool:
        return _DOMAIN_REGEX.match(domain) is not None

    def _build_dig_command(self, domain: str, query_type: str) -> List[str]:
        # Built as an argument list (no shell) so user-supplied values such as
        # the query type or nameserver can never be interpreted by a shell.
        return [DIG_BINARY, f'@{self.nameserver}', domain, query_type, DIG_SHORT_FLAG]

    def _report_invalid_domain(self, domain: str) -> None:
        _log_error(f'Invalid domain: {domain}')

    def _query_lines(self, domain: str, query_type: str) -> List[str]:
        if not self.validate_domain(domain):
            self._report_invalid_domain(domain)
            return []
        try:
            cmd = self._build_dig_command(domain, query_type)
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return _non_empty_lines(result.stdout)
        except subprocess.CalledProcessError as e:
            _log_error(f'Query failed: {e.stderr}')
            return []

    def query_a_record(self, domain: str) -> List[str]:
        return self._query_lines(domain, 'A')

    def query_mx_records(self, domain: str) -> List[str]:
        return self._query_lines(domain, 'MX')

    def custom_query(self, domain: str, query_type: str) -> Optional[str]:
        if not self.validate_domain(domain):
            self._report_invalid_domain(domain)
            return None
        try:
            cmd = self._build_dig_command(domain, query_type)
            result = subprocess.check_output(cmd, stderr=subprocess.PIPE)
            return result.decode().strip()
        except subprocess.CalledProcessError as e:
            _log_error(f'Query failed: {e.stderr.decode()}')
            return None
        except FileNotFoundError as e:
            _log_error(f'Query failed: {e}')
            return None


def build_parser() -> argparse.ArgumentParser:
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
    print('A records:', ', '.join(records) if records else NONE_FOUND_TEXT)


def _handle_mx(tool: DNSTool, args: argparse.Namespace) -> None:
    records = tool.query_mx_records(args.domain)
    print('MX records:', ', '.join(records) if records else NONE_FOUND_TEXT)


def _handle_custom(tool: DNSTool, args: argparse.Namespace) -> None:
    result = tool.custom_query(args.domain, args.type)
    print(f'{args.type} record:', result if result else NONE_FOUND_TEXT)


COMMAND_HANDLERS = {
    COMMAND_A: _handle_a,
    COMMAND_MX: _handle_mx,
    COMMAND_CUSTOM: _handle_custom,
}


def main():
    parser = build_parser()
    args = parser.parse_args()
    tool = DNSTool(args.server)
    handler = COMMAND_HANDLERS.get(args.command)
    if handler is not None:
        handler(tool, args)


if __name__ == '__main__':
    main()
