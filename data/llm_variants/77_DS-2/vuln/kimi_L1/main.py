"""Command-line network diagnostics tool."""

import argparse
import re
import socket
import subprocess
import sys
from typing import List, Optional


class NetworkDiagnostics:
    """Run network diagnostic commands against a single target host."""

    def __init__(self, target_host: str):
        self.target_host = target_host
        self.validate_host()

    def validate_host(self) -> bool:
        """Resolve the target host, exiting with an error if it cannot be resolved."""
        try:
            socket.gethostbyname(self.target_host)
            return True
        except socket.gaierror:
            print(f'Error: Unable to resolve {self.target_host}')
            sys.exit(1)

    def ping_host(self, count: int = 4) -> str:
        """Ping the target host `count` times and return the command output."""
        return self._run_shell_command(f'ping -c {count} {self.target_host}')

    def trace_route(self) -> str:
        """Trace the route to the target host and return the command output."""
        return self._run_shell_command(f'traceroute {self.target_host}')

    def dns_lookup(self, record_type: str = 'A') -> List[str]:
        """Look up DNS records of the given type for the target host."""
        try:
            output = subprocess.check_output(
                ['dig', '+short', self.target_host, record_type],
                stderr=subprocess.STDOUT,
            )
            return output.decode().splitlines()
        except subprocess.CalledProcessError:
            return []

    def port_scan(self, ports: str) -> dict:
        """Scan a comma-separated list of TCP ports and report the open ones."""
        try:
            open_ports = []
            for port in map(int, ports.split(',')):
                if self._is_port_open(port):
                    open_ports.append(str(port))
            return {'open_ports': open_ports}
        except ValueError:
            return {'error': 'Invalid port numbers'}

    def _run_shell_command(self, command: str) -> str:
        """Run a shell command and return its combined stdout/stderr output."""
        try:
            output = subprocess.check_output(
                command, shell=True, stderr=subprocess.STDOUT
            )
            return output.decode()
        except subprocess.CalledProcessError as exc:
            return exc.output.decode()

    def _is_port_open(self, port: int) -> bool:
        """Return True if a TCP connection to the given port succeeds."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((self.target_host, port))
        sock.close()
        return result == 0


def parse_args() -> argparse.Namespace:
    """Parse and return the command-line arguments."""
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
    """Entry point for the network diagnostics command-line interface."""
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
