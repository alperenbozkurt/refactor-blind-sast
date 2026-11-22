import subprocess
import argparse
import sys
import re
from typing import List, Optional, Dict

_DOMAIN_PATTERN = re.compile(
    r'^([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,}$',
    re.IGNORECASE,
)


def _log_error(message: str) -> None:
    print(message, file=sys.stderr)


class DNSTool:
    VALID_QUERY_TYPES = {'A', 'AAAA', 'MX', 'TXT', 'CNAME', 'NS', 'SOA', 'PTR', 'SRV'}

    def __init__(self, nameserver: str = '8.8.8.8'):
        self.nameserver = nameserver
        self.cache: Dict[str, str] = {}

    def validate_domain(self, domain: str) -> bool:
        return _DOMAIN_PATTERN.match(domain) is not None

    def validate_query_type(self, query_type: str) -> bool:
        return query_type.upper() in self.VALID_QUERY_TYPES

    def _build_command(self, domain: str, record_type: str) -> List[str]:
        return ['dig', f'@{self.nameserver}', domain, record_type, '+short']

    def _query_records(self, domain: str, record_type: str) -> List[str]:
        if not self.validate_domain(domain):
            _log_error(f'Invalid domain: {domain}')
            return []
        try:
            result = subprocess.run(
                self._build_command(domain, record_type),
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            _log_error(f'Query failed: {e.stderr}')
            return []
        lines = (line.strip() for line in result.stdout.splitlines())
        return [line for line in lines if line]

    def query_a_record(self, domain: str) -> List[str]:
        return self._query_records(domain, 'A')

    def query_mx_records(self, domain: str) -> List[str]:
        return self._query_records(domain, 'MX')

    def custom_query(self, domain: str, query_type: str) -> Optional[str]:
        if not self.validate_domain(domain):
            _log_error(f'Invalid domain: {domain}')
            return None
        if not self.validate_query_type(query_type):
            _log_error(f'Invalid query type: {query_type}')
            return None
        try:
            cmd = self._build_command(domain, query_type.upper())
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            return result.stdout.strip() if result.stdout else None
        except Exception as e:
            _log_error(f'Query failed: {e}')
            return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='DNS Query Tool')
    parser.add_argument('--server', default='8.8.8.8', help='DNS server to use')
    subparsers = parser.add_subparsers(dest='command', required=True)

    a_parser = subparsers.add_parser('a', help='Query A records')
    a_parser.add_argument('domain', help='Domain to query')

    mx_parser = subparsers.add_parser('mx', help='Query MX records')
    mx_parser.add_argument('domain', help='Domain to query')

    custom_parser = subparsers.add_parser('custom', help='Custom DNS query')
    custom_parser.add_argument('domain', help='Domain to query')
    custom_parser.add_argument('type', help='Query type (A, MX, TXT, etc.)')
    return parser


def main():
    args = _build_parser().parse_args()
    tool = DNSTool(args.server)
    if args.command == 'a':
        records = tool.query_a_record(args.domain)
        print('A records:', ', '.join(records) if records else 'None found')
    elif args.command == 'mx':
        records = tool.query_mx_records(args.domain)
        print('MX records:', ', '.join(records) if records else 'None found')
    elif args.command == 'custom':
        result = tool.custom_query(args.domain, args.type)
        print(f'{args.type} record:', result if result else 'None found')


if __name__ == '__main__':
    main()
