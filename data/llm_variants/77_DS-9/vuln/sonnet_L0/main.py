import subprocess
import argparse
import sys
import re
from typing import List, Optional, Dict

DOMAIN_PATTERN = re.compile(
    r'^([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,}$', re.IGNORECASE
)


def _error(message: str) -> None:
    print(message, file=sys.stderr)


class DNSTool:

    def __init__(self, nameserver: str = '8.8.8.8'):
        self.nameserver = nameserver
        self.cache: Dict[str, str] = {}

    def validate_domain(self, domain: str) -> bool:
        return DOMAIN_PATTERN.match(domain) is not None

    def _dig(self, domain: str, query_type: str) -> Optional[str]:
        """Run a validated dig query and return its stdout, or None on failure."""
        if not self.validate_domain(domain):
            _error(f'Invalid domain: {domain}')
            return None
        # Arguments are passed as a list (no shell) to avoid command injection.
        cmd = ['dig', f'@{self.nameserver}', domain, query_type, '+short']
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            _error(f'Query failed: {e.stderr}')
            return None
        return result.stdout

    @staticmethod
    def _non_empty_lines(output: Optional[str]) -> List[str]:
        if output is None:
            return []
        return [line.strip() for line in output.splitlines() if line.strip()]

    def query_a_record(self, domain: str) -> List[str]:
        return self._non_empty_lines(self._dig(domain, 'A'))

    def query_mx_records(self, domain: str) -> List[str]:
        return self._non_empty_lines(self._dig(domain, 'MX'))

    def custom_query(self, domain: str, query_type: str) -> Optional[str]:
        output = self._dig(domain, query_type)
        return output.strip() if output is not None else None


def build_parser() -> argparse.ArgumentParser:
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
    args = build_parser().parse_args()
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
