import subprocess
import sys
import argparse
import socket
import re
import shlex
from typing import List, Optional

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
PING_BINARY = 'ping'
TRACEROUTE_BINARY = 'traceroute'
DIG_BINARY = 'dig'

DEFAULT_PING_COUNT = 4
DEFAULT_RECORD_TYPE = 'A'
SOCKET_TIMEOUT_SECONDS = 1
PORT_SEPARATOR = ','

INVALID_PORTS_MESSAGE = 'Invalid port numbers'

CMD_PING = 'ping'
CMD_TRACEROUTE = 'traceroute'
CMD_DNS = 'dns'
CMD_SCAN = 'scan'


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _run_command(command: List[str]) -> str:
    """Run an external command and return its captured stdout."""
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return result.stdout


def _parse_ports(ports: str):
    """Lazily convert a comma-separated port string into integers."""
    return map(int, ports.split(PORT_SEPARATOR))


def _is_port_open(host: str, port: int) -> bool:
    """Return True if a TCP connection to host:port succeeds."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(SOCKET_TIMEOUT_SECONDS)
    result = sock.connect_ex((host, port))
    is_open = result == 0
    sock.close()
    return is_open


# --------------------------------------------------------------------------- #
# Core class
# --------------------------------------------------------------------------- #
class NetworkDiagnostics:

    def __init__(self, target_host: str):
        self.target_host = target_host
        self.validate_host()

    def validate_host(self) -> bool:
        try:
            socket.gethostbyname(self.target_host)
            return True
        except socket.gaierror:
            print(f'Error: Unable to resolve {self.target_host}')
            sys.exit(1)

    def ping_host(self, count: int = DEFAULT_PING_COUNT) -> str:
        try:
            return _run_command([PING_BINARY, '-c', str(count), self.target_host])
        except Exception as e:
            return str(e)

    def trace_route(self) -> str:
        try:
            return _run_command([TRACEROUTE_BINARY, self.target_host])
        except Exception as e:
            return str(e)

    def dns_lookup(self, record_type: str = DEFAULT_RECORD_TYPE) -> List[str]:
        try:
            output = _run_command([DIG_BINARY, '+short', self.target_host, record_type])
            return output.splitlines()
        except Exception as e:
            print(f'DNS lookup failed: {e}')
            return []

    def port_scan(self, ports: str) -> dict:
        try:
            open_ports = []
            for port in _parse_ports(ports):
                if _is_port_open(self.target_host, port):
                    open_ports.append(str(port))
            return {'open_ports': open_ports}
        except ValueError:
            return {'error': INVALID_PORTS_MESSAGE}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Network Diagnostics Tool')
    parser.add_argument('host', help='Target hostname or IP address')
    subparsers = parser.add_subparsers(dest='command', required=True)

    ping_parser = subparsers.add_parser(CMD_PING)
    ping_parser.add_argument('-c', type=int, default=DEFAULT_PING_COUNT, help='Packet count')

    subparsers.add_parser(CMD_TRACEROUTE)

    dns_parser = subparsers.add_parser(CMD_DNS)
    dns_parser.add_argument('-t', default=DEFAULT_RECORD_TYPE, help='Record type')

    scan_parser = subparsers.add_parser(CMD_SCAN)
    scan_parser.add_argument('ports', help='Comma-separated port list')

    return parser.parse_args()


def _handle_ping(diag: NetworkDiagnostics, args: argparse.Namespace) -> None:
    print(diag.ping_host(args.c))


def _handle_traceroute(diag: NetworkDiagnostics, args: argparse.Namespace) -> None:
    print(diag.trace_route())


def _handle_dns(diag: NetworkDiagnostics, args: argparse.Namespace) -> None:
    print('\n'.join(diag.dns_lookup(args.t)))


def _handle_scan(diag: NetworkDiagnostics, args: argparse.Namespace) -> None:
    result = diag.port_scan(args.ports)
    if 'error' in result:
        print(result['error'])
    else:
        print('Open ports:', ', '.join(result['open_ports']))


COMMAND_HANDLERS = {
    CMD_PING: _handle_ping,
    CMD_TRACEROUTE: _handle_traceroute,
    CMD_DNS: _handle_dns,
    CMD_SCAN: _handle_scan,
}


def main() -> None:
    args = parse_args()
    diag = NetworkDiagnostics(args.host)
    handler = COMMAND_HANDLERS.get(args.command)
    if handler is not None:
        handler(diag, args)


if __name__ == '__main__':
    main()
