import subprocess
import sys
import argparse
import socket
import re  # noqa: F401  (kept to preserve module-level names)
import shlex  # noqa: F401  (kept to preserve module-level names)
from typing import List, Optional  # noqa: F401

PORT_SCAN_TIMEOUT_SECONDS = 1


class NetworkDiagnostics:
    """Run basic network diagnostics against a single target host."""

    def __init__(self, target_host: str):
        self.target_host = target_host
        self.validate_host()

    def validate_host(self) -> bool:
        """Ensure the target resolves; exit the program otherwise."""
        try:
            socket.gethostbyname(self.target_host)
            return True
        except socket.gaierror:
            print(f'Error: Unable to resolve {self.target_host}')
            sys.exit(1)

    @staticmethod
    def _run_command(command: List[str]) -> str:
        """Run a command (without a shell) and return its stdout."""
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout

    def ping_host(self, count: int = 4) -> str:
        try:
            return self._run_command(['ping', '-c', str(count), self.target_host])
        except Exception as e:
            return str(e)

    def trace_route(self) -> str:
        try:
            return self._run_command(['traceroute', self.target_host])
        except Exception as e:
            return str(e)

    def dns_lookup(self, record_type: str = 'A') -> List[str]:
        try:
            output = self._run_command(['dig', '+short', self.target_host, record_type])
            return output.splitlines()
        except Exception as e:
            print(f'DNS lookup failed: {e}')
            return []

    def _is_port_open(self, port: int) -> bool:
        """Return True if a TCP connection to the given port succeeds."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(PORT_SCAN_TIMEOUT_SECONDS)
        result = sock.connect_ex((self.target_host, port))
        sock.close()
        return result == 0

    def port_scan(self, ports: str) -> dict:
        try:
            open_ports = []
            # Ports are parsed lazily so scanning proceeds until an invalid
            # entry is encountered.
            for port in map(int, ports.split(',')):
                if self._is_port_open(port):
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
