import subprocess
import sys
import argparse
import socket
import re
from typing import Callable, Dict, List, Optional

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
DEFAULT_PING_COUNT = 4
DEFAULT_RECORD_TYPE = 'A'
PORT_SCAN_TIMEOUT_SECONDS = 1
PORT_SEPARATOR = ','
CONNECT_SUCCESS = 0

CMD_PING = 'ping'
CMD_TRACEROUTE = 'traceroute'
CMD_DNS = 'dns'
CMD_SCAN = 'scan'

ERROR_INVALID_PORTS = 'Invalid port numbers'
ERROR_UNRESOLVED_TEMPLATE = 'Error: Unable to resolve {host}'


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _run_shell_command(command: str) -> str:
    """Run a shell command, returning decoded output even on non-zero exit."""
    try:
        output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
        return output.decode()
    except subprocess.CalledProcessError as e:
        return e.output.decode()


def _is_port_open(host: str, port: int, timeout: float = PORT_SCAN_TIMEOUT_SECONDS) -> bool:
    """Return True if a TCP connection to host:port succeeds."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == CONNECT_SUCCESS
    finally:
        sock.close()


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
            print(ERROR_UNRESOLVED_TEMPLATE.format(host=self.target_host))
            sys.exit(1)

    def ping_host(self, count: int = DEFAULT_PING_COUNT) -> str:
        return _run_shell_command(f'ping -c {count} {self.target_host}')

    def trace_route(self) -> str:
        return _run_shell_command(f'traceroute {self.target_host}')

    def dns_lookup(self, record_type: str = DEFAULT_RECORD_TYPE) -> List[str]:
        try:
            output = subprocess.check_output(
                ['dig', '+short', self.target_host, record_type],
                stderr=subprocess.STDOUT,
            )
            return output.decode().splitlines()
        except subprocess.CalledProcessError:
            return []

    def port_scan(self, ports: str) -> dict:
        try:
            open_ports = []
            # map() is lazy: ports are parsed and scanned one at a time.
            for port in map(int, ports.split(PORT_SEPARATOR)):
                if _is_port_open(self.target_host, port):
                    open_ports.append(str(port))
            return {'open_ports': open_ports}
        except ValueError:
            return {'error': ERROR_INVALID_PORTS}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _build_parser() -> argparse.ArgumentParser:
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
    return parser


def parse_args() -> argparse.Namespace:
    return _build_parser().parse_args()


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


COMMAND_HANDLERS: Dict[str, Callable[[NetworkDiagnostics, argparse.Namespace], None]] = {
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
