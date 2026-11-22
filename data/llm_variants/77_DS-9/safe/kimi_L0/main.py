import argparse
import re
import subprocess
import sys
from typing import Dict, List, Optional


class DNSTool:
    VALID_QUERY_TYPES = {'A', 'AAAA', 'MX', 'TXT', 'CNAME', 'NS', 'SOA', 'PTR', 'SRV'}
    _DOMAIN_PATTERN = re.compile(r'^([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,}$', re.IGNORECASE)

    def __init__(self, nameserver: str = '8.8.8.8'):
        self.nameserver = nameserver
        self.cache: Dict[str, str] = {}

    def validate_domain(self, domain: str) -> bool:
        return self._DOMAIN_PATTERN.match(domain) is not None

    def validate_query_type(self, query_type: str) -> bool:
        return query_type.upper() in self.VALID_QUERY_TYPES

    def query_a_record(self, domain: str) -> List[str]:
        return self._query_records(domain, 'A')

    def query_mx_records(self, domain: str) -> List[str]:
        return self._query_records(domain, 'MX')

    def custom_query(self, domain: str, query_type: str) -> Optional[str]:
        if not self._require_valid_domain(domain):
            return None
        if not self.validate_query_type(query_type):
            print(f'Invalid query type: {query_type}', file=sys.stderr)
            return None
        try:
            result = subprocess.run(
                self._dig_command(domain, query_type.upper()),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            return result.stdout.strip() if result.stdout else None
        except Exception as e:
            print(f'Query failed: {e}', file=sys.stderr)
            return None

    def _query_records(self, domain: str, query_type: str) -> List[str]:
        if not self._require_valid_domain(domain):
            return []
        try:
            result = subprocess.run(
                self._dig_command(domain, query_type),
                capture_output=True,
                text=True,
                check=True,
            )
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        except subprocess.CalledProcessError as e:
            print(f'Query failed: {e.stderr}', file=sys.stderr)
            return []

    def _require_valid_domain(self, domain: str) -> bool:
        if not self.validate_domain(domain):
            print(f'Invalid domain: {domain}', file=sys.stderr)
            return False
        return True

    def _dig_command(self, domain: str, query_type: str) -> List[str]:
        return ['dig', f'@{self.nameserver}', domain, query_type, '+short']


def main():
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

    args = parser.parse_args()
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
