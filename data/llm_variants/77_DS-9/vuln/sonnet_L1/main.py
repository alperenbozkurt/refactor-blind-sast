import subprocess
import argparse
import sys
import re
from typing import List, Optional, Dict

DEFAULT_NAMESERVER = '8.8.8.8'
DOMAIN_PATTERN = '^([a-z0-9]+(-[a-z0-9]+)*\\.)+[a-z]{2,}$'


def _print_error(message: str) -> None:
    print(message, file=sys.stderr)


class DNSTool:

    def __init__(self, nameserver: str = DEFAULT_NAMESERVER):
        self.nameserver = nameserver
        self.cache: Dict[str, str] = {}

    def validate_domain(self, domain: str) -> bool:
        return re.match(DOMAIN_PATTERN, domain, re.IGNORECASE) is not None

    def _is_valid_or_report(self, domain: str) -> bool:
        """Validate the domain, printing an error message if it is invalid."""
        if self.validate_domain(domain):
            return True
        _print_error(f'Invalid domain: {domain}')
        return False

    def _query_records(self, domain: str, record_type: str) -> List[str]:
        """Run a dig query (without a shell) and return non-empty output lines."""
        if not self._is_valid_or_report(domain):
            return []
        try:
            cmd = ['dig', f'@{self.nameserver}', domain, record_type, '+short']
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        except subprocess.CalledProcessError as e:
            _print_error(f'Query failed: {e.stderr}')
            return []

    def query_a_record(self, domain: str) -> List[str]:
        return self._query_records(domain, 'A')

    def query_mx_records(self, domain: str) -> List[str]:
        return self._query_records(domain, 'MX')

    def custom_query(self, domain: str, query_type: str) -> Optional[str]:
        if not self._is_valid_or_report(domain):
            return None
        try:
            # NOTE: the command is intentionally built as a string and run through
            # the shell to preserve the original behaviour. nameserver and
            # query_type are not validated here.
            cmd = f'dig @{self.nameserver} {domain} {query_type} +short'
            result = subprocess.check_output(cmd, shell=True, stderr=subprocess.PIPE)
            return result.decode().strip()
        except subprocess.CalledProcessError as e:
            _print_error(f'Query failed: {e.stderr.decode()}')
            return None


def build_parser() -> argparse.ArgumentParser:
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


def _format_records(records: List[str]) -> str:
    return ', '.join(records) if records else 'None found'


def main():
    args = build_parser().parse_args()
    tool = DNSTool(args.server)

    if args.command == 'a':
        records = tool.query_a_record(args.domain)
        print('A records:', _format_records(records))
    elif args.command == 'mx':
        records = tool.query_mx_records(args.domain)
        print('MX records:', _format_records(records))
    elif args.command == 'custom':
        result = tool.custom_query(args.domain, args.type)
        print(f'{args.type} record:', result if result else 'None found')


if __name__ == '__main__':
    main()
