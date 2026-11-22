import argparse
import re
import socket
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DEFAULT_PING_COUNT = 4
DEFAULT_DNS_RECORD_TYPE = 'A'
SOCKET_TIMEOUT_SECONDS = 1

CMD_PING = 'ping'
CMD_TRACEROUTE = 'traceroute'
CMD_DNS = 'dns'
CMD_SCAN = 'scan'

PING_COMMAND_TEMPLATE = 'ping -c {count} {host}'
TRACEROUTE_COMMAND_TEMPLATE = 'traceroute {host}'
DIG_COMMAND = 'dig'
DIG_SHORT_FLAG = '+short'

ERROR_INVALID_PORTS = 'Invalid port numbers'
OPEN_PORTS_LABEL = 'Open ports:'


@dataclass(frozen=True)
class DiagnosticsConfig:
    """Immutable, tunable defaults for the diagnostics tool."""

    ping_count: int = DEFAULT_PING_COUNT
    dns_record_type: str = DEFAULT_DNS_RECORD_TYPE
    socket_timeout: int = SOCKET_TIMEOUT_SECONDS


CONFIG = DiagnosticsConfig()


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------

def _run_shell_command(command: str) -> str:
    """Run *command* via the shell and return its combined output as text.

    The output is returned even when the command exits with a non-zero
    status, mirroring the original tool's behaviour.
    """
    try:
        output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
        return output.decode()
    except subprocess.CalledProcessError as exc:
        return exc.output.decode()


def _capture_command_output(command_args: List[str]) -> Optional[str]:
    """Run *command_args* without a shell.

    Returns the decoded output on success, or ``None`` on non-zero exit.
    """
    try:
        return subprocess.check_output(command_args, stderr=subprocess.STDOUT).decode()
    except subprocess.CalledProcessError:
        return None


def _parse_port_list(ports: str) -> List[int]:
    """Convert a comma-separated port string into a list of integers."""
    return [int(port) for port in ports.split(',')]


def _print_scan_result(result: dict) -> None:
    """Render a port-scan result dictionary to stdout."""
    if 'error' in result:
        print(result['error'])
    else:
        print(OPEN_PORTS_LABEL, ', '.join(result['open_ports']))


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

class NetworkDiagnostics:

    def __init__(self, target_host: str):
        self.target_host = target_host
        self.config = CONFIG
        self.validate_host()

    def validate_host(self) -> bool:
        try:
            socket.gethostbyname(self.target_host)
            return True
        except socket.gaierror:
            print(f'Error: Unable to resolve {self.target_host}')
            sys.exit(1)

    def ping_host(self, count: int = DEFAULT_PING_COUNT) -> str:
        command = PING_COMMAND_TEMPLATE.format(count=count, host=self.target_host)
        return _run_shell_command(command)

    def trace_route(self) -> str:
        command = TRACEROUTE_COMMAND_TEMPLATE.format(host=self.target_host)
        return _run_shell_command(command)

    def dns_lookup(self, record_type: str = DEFAULT_DNS_RECORD_TYPE) -> List[str]:
        output = _capture_command_output(
            [DIG_COMMAND, DIG_SHORT_FLAG, self.target_host, record_type]
        )
        if output is None:
            return []
        return output.splitlines()

    def port_scan(self, ports: str) -> dict:
        try:
            open_ports = [
                str(port)
                for port in _parse_port_list(ports)
                if self._is_port_open(port)
            ]
        except ValueError:
            return {'error': ERROR_INVALID_PORTS}
        return {'open_ports': open_ports}

    def _is_port_open(self, port: int) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(self.config.socket_timeout)
            return sock.connect_ex((self.target_host, port)) == 0
        finally:
            sock.close()


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Network Diagnostics Tool')
    parser.add_argument('host', help='Target hostname or IP address')
    subparsers = parser.add_subparsers(dest='command', required=True)

    ping_parser = subparsers.add_parser(CMD_PING)
    ping_parser.add_argument('-c', type=int, default=CONFIG.ping_count, help='Packet count')

    subparsers.add_parser(CMD_TRACEROUTE)

    dns_parser = subparsers.add_parser(CMD_DNS)
    dns_parser.add_argument('-t', default=CONFIG.dns_record_type, help='Record type')

    scan_parser = subparsers.add_parser(CMD_SCAN)
    scan_parser.add_argument('ports', help='Comma-separated port list')

    return parser


def parse_args() -> argparse.Namespace:
    return _build_parser().parse_args()


def main() -> None:
    args = parse_args()
    diag = NetworkDiagnostics(args.host)
    if args.command == CMD_PING:
        print(diag.ping_host(args.c))
    elif args.command == CMD_TRACEROUTE:
        print(diag.trace_route())
    elif args.command == CMD_DNS:
        print('\n'.join(diag.dns_lookup(args.t)))
    elif args.command == CMD_SCAN:
        _print_scan_result(diag.port_scan(args.ports))


if __name__ == '__main__':
    main()
