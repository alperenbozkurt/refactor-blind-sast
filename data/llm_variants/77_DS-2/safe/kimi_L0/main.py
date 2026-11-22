import argparse
import re
import shlex
import socket
import subprocess
import sys
from typing import List, Optional


class NetworkDiagnostics:
    """Perform basic network diagnostics against a target host."""

    CONNECT_TIMEOUT = 1

    def __init__(self, target_host: str):
        self.target_host = target_host
        self.validate_host()

    def validate_host(self) -> bool:
        """Resolve the target host, exiting with an error if it fails."""
        try:
            socket.gethostbyname(self.target_host)
            return True
        except socket.gaierror:
            print(f'Error: Unable to resolve {self.target_host}')
            sys.exit(1)

    @staticmethod
    def _run_command(command: List[str]) -> str:
        """Run an external command and return its stdout, or the error text."""
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, check=False
            )
            return result.stdout
        except Exception as e:
            return str(e)

    def ping_host(self, count: int = 4) -> str:
        return self._run_command(['ping', '-c', str(count), self.target_host])

    def trace_route(self) -> str:
        return self._run_command(['traceroute', self.target_host])

    def dns_lookup(self, record_type: str = 'A') -> List[str]:
        try:
            output = subprocess.run(
                ['dig', '+short', self.target_host, record_type],
                capture_output=True,
                text=True,
                check=False,
            )
            return output.stdout.splitlines()
        except Exception as e:
            print(f'DNS lookup failed: {e}')
            return []

    def port_scan(self, ports: str) -> dict:
        try:
            open_ports = []
            for port in map(int, ports.split(',')):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(self.CONNECT_TIMEOUT)
                    if sock.connect_ex((self.target_host, port)) == 0:
                        open_ports.append(str(port))
            return {'open_ports': open_ports}
        except ValueError:
            return {'error': 'Invalid port numbers'}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Network Diagnostics Tool')
    parser.add_argument('host', help='Target hostname or IP address')
    subparsers = parser.add_subparsers(dest='command', required=True)

    ping_parser = subparsers.add_parser('ping')
    ping_parser.add_argument('-c', type=int, default=4, help='Packet count')

    subparsers.add_parser('traceroute')

    dns_parser = subparsers.add_parser('dns')
    dns_parser.add_argument('-t', default='A', help='Record type')

    scan_parser = subparsers.add_parser('scan')
    scan_parser.add_argument('ports', help='Comma-separated port list')

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    diag = NetworkDiagnostics(args.host)
    if args.command == 'ping':
        print(diag.ping_host(args.c))
    elif args.command == 'traceroute':
        print(diag.trace_route())
    elif args.command == 'dns':
        print('\n'.join(diag.dns_lookup(args.t)))
    elif args.command == 'scan':
        result = diag.port_scan(args.ports)
        if 'error' in result:
            print(result['error'])
        else:
            print('Open ports:', ', '.join(result['open_ports']))


if __name__ == '__main__':
    main()
