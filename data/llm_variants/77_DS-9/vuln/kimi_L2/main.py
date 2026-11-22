import argparse
import re
import subprocess
import sys
from typing import Callable, Dict, List, Optional

DEFAULT_NAMESERVER = '8.8.8.8'
DIG_EXECUTABLE = 'dig'
SHORT_ANSWER_FLAG = '+short'
RECORD_TYPE_A = 'A'
RECORD_TYPE_MX = 'MX'
NO_RECORDS_MESSAGE = 'None found'

DOMAIN_PATTERN = re.compile(
    r'^([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,}$', re.IGNORECASE
)


def _print_error(message: str) -> None:
    print(message, file=sys.stderr)


class DNSTool:

    def __init__(self, nameserver: str = DEFAULT_NAMESERVER):
        self.nameserver = nameserver
        self.cache: Dict[str, str] = {}

    def validate_domain(self, domain: str) -> bool:
        return DOMAIN_PATTERN.match(domain) is not None

    def query_a_record(self, domain: str) -> List[str]:
        return self._query_short_records(domain, RECORD_TYPE_A)

    def query_mx_records(self, domain: str) -> List[str]:
        return self._query_short_records(domain, RECORD_TYPE_MX)

    def custom_query(self, domain: str, query_type: str) -> Optional[str]:
        if not self.validate_domain(domain):
            _print_error(f'Invalid domain: {domain}')
            return None
        try:
            cmd = f'{DIG_EXECUTABLE} @{self.nameserver} {domain} {query_type} {SHORT_ANSWER_FLAG}'
            result = subprocess.check_output(cmd, shell=True, stderr=subprocess.PIPE)
            return result.decode().strip()
        except subprocess.CalledProcessError as e:
            _print_error(f'Query failed: {e.stderr.decode()}')
            return None

    def _query_short_records(self, domain: str, query_type: str) -> List[str]:
        if not self.validate_domain(domain):
            _print_error(f'Invalid domain: {domain}')
            return []
        try:
            return self._run_dig_short(domain, query_type)
        except subprocess.CalledProcessError as e:
            _print_error(f'Query failed: {e.stderr}')
            return []

    def _run_dig_short(self, domain: str, query_type: str) -> List[str]:
        cmd = [DIG_EXECUTABLE, f'@{self.nameserver}', domain, query_type, SHORT_ANSWER_FLAG]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='DNS Query Tool')
    parser.add_argument('--server', default=DEFAULT_NAMESERVER, help='DNS server to use')
    subparsers = parser.add_subparsers(dest='command', required=True)

    a_parser = subparsers.add_parser('a', help='Query A records')
    a_parser.add_argument('domain', help='Domain to query')

    mx_parser = subparsers.add_parser('mx', help='Query MX records')
    mx_parser.add_argument('domain', help='Domain to query')

    custom_parser = subparsers.add_parser('custom', help='Custom DNS query')
    custom_parser.add_argument('domain', help='Domain to query')
    custom_parser.add_argument('type', help='Query type (A, MX, TXT, etc.)')

    return parser


def _handle_a_command(tool: DNSTool, args: argparse.Namespace) -> None:
    records = tool.query_a_record(args.domain)
    print('A records:', ', '.join(records) if records else NO_RECORDS_MESSAGE)


def _handle_mx_command(tool: DNSTool, args: argparse.Namespace) -> None:
    records = tool.query_mx_records(args.domain)
    print('MX records:', ', '.join(records) if records else NO_RECORDS_MESSAGE)


def _handle_custom_command(tool: DNSTool, args: argparse.Namespace) -> None:
    result = tool.custom_query(args.domain, args.type)
    print(f'{args.type} record:', result if result else NO_RECORDS_MESSAGE)


_COMMAND_HANDLERS: Dict[str, Callable[[DNSTool, argparse.Namespace], None]] = {
    'a': _handle_a_command,
    'mx': _handle_mx_command,
    'custom': _handle_custom_command,
}


def main():
    args = _build_argument_parser().parse_args()
    tool = DNSTool(args.server)
    _COMMAND_HANDLERS[args.command](tool, args)


if __name__ == '__main__':
    main()
