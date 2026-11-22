"""A simple command-line DNS query tool built on top of ``dig``."""

import argparse
import re
import subprocess
import sys
from typing import Dict, List, Optional

DEFAULT_NAMESERVER = '8.8.8.8'
DOMAIN_PATTERN = r'^([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,}$'


class DNSTool:
    """Perform DNS queries against a configurable nameserver."""

    def __init__(self, nameserver: str = DEFAULT_NAMESERVER):
        self.nameserver = nameserver
        self.cache: Dict[str, str] = {}

    def validate_domain(self, domain: str) -> bool:
        return re.match(DOMAIN_PATTERN, domain, re.IGNORECASE) is not None

    def _validate_or_report(self, domain: str) -> bool:
        """Return True if *domain* is valid; otherwise report it and return False."""
        if self.validate_domain(domain):
            return True
        print(f'Invalid domain: {domain}', file=sys.stderr)
        return False

    def _run_dig(self, domain: str, query_type: str) -> List[str]:
        """Run ``dig`` and return the stripped, non-empty output lines."""
        cmd = ['dig', f'@{self.nameserver}', domain, query_type, '+short']
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def _query_records(self, domain: str, query_type: str) -> List[str]:
        """Validate *domain* and query records of *query_type*."""
        if not self._validate_or_report(domain):
            return []
        try:
            return self._run_dig(domain, query_type)
        except subprocess.CalledProcessError as e:
            print(f'Query failed: {e.stderr}', file=sys.stderr)
            return []

    def query_a_record(self, domain: str) -> List[str]:
        return self._query_records(domain, 'A')

    def query_mx_records(self, domain: str) -> List[str]:
        return self._query_records(domain, 'MX')

    def custom_query(self, domain: str, query_type: str) -> Optional[str]:
        if not self._validate_or_report(domain):
            return None
        try:
            cmd = f'dig @{self.nameserver} {domain} {query_type} +short'
            result = subprocess.check_output(cmd, shell=True, stderr=subprocess.PIPE)
            return result.decode().strip()
        except subprocess.CalledProcessError as e:
            print(f'Query failed: {e.stderr.decode()}', file=sys.stderr)
            return None


def main():
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
