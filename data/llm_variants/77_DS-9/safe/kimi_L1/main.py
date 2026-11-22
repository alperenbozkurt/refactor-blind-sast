"""Command-line DNS query tool built on top of the ``dig`` utility."""

import argparse
import re
import subprocess
import sys
from typing import Dict, List, Optional


class DNSTool:
    """Perform DNS lookups against a chosen nameserver using ``dig``."""

    VALID_QUERY_TYPES = {'A', 'AAAA', 'MX', 'TXT', 'CNAME', 'NS', 'SOA', 'PTR', 'SRV'}

    _DOMAIN_PATTERN = re.compile(
        r'^([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,}$', re.IGNORECASE
    )

    def __init__(self, nameserver: str = '8.8.8.8'):
        self.nameserver = nameserver
        self.cache: Dict[str, str] = {}

    def validate_domain(self, domain: str) -> bool:
        """Return True if ``domain`` is a syntactically valid domain name."""
        return self._DOMAIN_PATTERN.match(domain) is not None

    def validate_query_type(self, query_type: str) -> bool:
        """Return True if ``query_type`` is a supported DNS record type."""
        return query_type.upper() in self.VALID_QUERY_TYPES

    def query_a_record(self, domain: str) -> List[str]:
        """Return the A records for ``domain`` (empty list on failure)."""
        return self._query_short_records(domain, 'A')

    def query_mx_records(self, domain: str) -> List[str]:
        """Return the MX records for ``domain`` (empty list on failure)."""
        return self._query_short_records(domain, 'MX')

    def custom_query(self, domain: str, query_type: str) -> Optional[str]:
        """Run a ``dig +short`` query for an arbitrary record type.

        Returns the stripped raw output, or ``None`` when the domain or
        query type is invalid, the query fails, or it produces no output.
        """
        if not self.validate_domain(domain):
            print(f'Invalid domain: {domain}', file=sys.stderr)
            return None
        if not self.validate_query_type(query_type):
            print(f'Invalid query type: {query_type}', file=sys.stderr)
            return None
        try:
            cmd = ['dig', f'@{self.nameserver}', domain, query_type.upper(), '+short']
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            return result.stdout.strip() if result.stdout else None
        except Exception as e:
            print(f'Query failed: {e}', file=sys.stderr)
            return None

    def _query_short_records(self, domain: str, record_type: str) -> List[str]:
        """Run a ``dig +short`` query and return its non-empty output lines."""
        if not self.validate_domain(domain):
            print(f'Invalid domain: {domain}', file=sys.stderr)
            return []
        try:
            cmd = ['dig', f'@{self.nameserver}', domain, record_type, '+short']
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        except subprocess.CalledProcessError as e:
            print(f'Query failed: {e.stderr}', file=sys.stderr)
            return []


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
