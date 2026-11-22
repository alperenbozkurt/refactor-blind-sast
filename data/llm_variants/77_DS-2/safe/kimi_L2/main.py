"""Network diagnostics command-line tool.

Provides ping, traceroute, DNS lookup and TCP port scanning against a
target host. The module is organised around the :class:`NetworkDiagnostics`
class, a set of shared helpers and named constants so it can be embedded
in a larger production codebase.
"""

import argparse
import re
import shlex
import socket
import subprocess
import sys
from typing import Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# CLI subcommand names
# ---------------------------------------------------------------------------

COMMAND_PING = 'ping'
COMMAND_TRACEROUTE = 'traceroute'
COMMAND_DNS = 'dns'
COMMAND_SCAN = 'scan'

# ---------------------------------------------------------------------------
# Defaults and tunables
# ---------------------------------------------------------------------------

DEFAULT_PING_COUNT = 4
DEFAULT_DNS_RECORD_TYPE = 'A'
PORT_SCAN_TIMEOUT_SECONDS = 1
EXIT_CODE_FAILURE = 1

# External tools invoked via subprocess.
PING_COMMAND = 'ping'
TRACEROUTE_COMMAND = 'traceroute'
DIG_COMMAND = 'dig'

# ---------------------------------------------------------------------------
# User-facing messages
# ---------------------------------------------------------------------------

ERROR_UNRESOLVABLE_HOST = 'Error: Unable to resolve {}'
ERROR_DNS_LOOKUP_FAILED = 'DNS lookup failed: {}'
ERROR_INVALID_PORT_NUMBERS = 'Invalid port numbers'
OPEN_PORTS_LABEL = 'Open ports:'

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _run_command(command: List[str]) -> subprocess.CompletedProcess:
    """Run *command*, capturing output without raising on non-zero exit."""
    return subprocess.run(command, capture_output=True, text=True, check=False)


class NetworkDiagnostics:
    """Run network diagnostic operations against a single target host."""

    def __init__(self, target_host: str):
        self.target_host = target_host
        self.validate_host()

    def validate_host(self) -> bool:
        """Resolve the target host, exiting with an error if unresolvable."""
        try:
            socket.gethostbyname(self.target_host)
            return True
        except socket.gaierror:
            print(ERROR_UNRESOLVABLE_HOST.format(self.target_host))
            sys.exit(EXIT_CODE_FAILURE)

    def ping_host(self, count: int = DEFAULT_PING_COUNT) -> str:
        """Ping the target host *count* times and return the raw output."""
        try:
            result = _run_command([PING_COMMAND, '-c', str(count), self.target_host])
            return result.stdout
        except Exception as e:
            return str(e)

    def trace_route(self) -> str:
        """Trace the network route to the target host."""
        try:
            result = _run_command([TRACEROUTE_COMMAND, self.target_host])
            return result.stdout
        except Exception as e:
            return str(e)

    def dns_lookup(self, record_type: str = DEFAULT_DNS_RECORD_TYPE) -> List[str]:
        """Return the DNS records of *record_type* for the target host."""
        try:
            output = _run_command([DIG_COMMAND, '+short', self.target_host, record_type])
            return output.stdout.splitlines()
        except Exception as e:
            print(ERROR_DNS_LOOKUP_FAILED.format(e))
            return []

    def port_scan(self, ports: str) -> dict:
        """Scan a comma-separated list of TCP ports on the target host."""
        try:
            open_ports = []
            for port in map(int, ports.split(',')):
                if self._is_port_open(port):
                    open_ports.append(str(port))
            return {'open_ports': open_ports}
        except ValueError:
            return {'error': ERROR_INVALID_PORT_NUMBERS}

    def _is_port_open(self, port: int) -> bool:
        """Return True when a TCP connection to *port* succeeds."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(PORT_SCAN_TIMEOUT_SECONDS)
            return sock.connect_ex((self.target_host, port)) == 0
        finally:
            sock.close()


def _build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for the command-line interface."""
    parser = argparse.ArgumentParser(description='Network Diagnostics Tool')
    parser.add_argument('host', help='Target hostname or IP address')
    subparsers = parser.add_subparsers(dest='command', required=True)

    ping_parser = subparsers.add_parser(COMMAND_PING)
    ping_parser.add_argument('-c', type=int, default=DEFAULT_PING_COUNT, help='Packet count')

    subparsers.add_parser(COMMAND_TRACEROUTE)

    dns_parser = subparsers.add_parser(COMMAND_DNS)
    dns_parser.add_argument('-t', default=DEFAULT_DNS_RECORD_TYPE, help='Record type')

    scan_parser = subparsers.add_parser(COMMAND_SCAN)
    scan_parser.add_argument('ports', help='Comma-separated port list')

    return parser


def parse_args() -> argparse.Namespace:
    """Parse and return the command-line arguments."""
    return _build_parser().parse_args()


def _print_port_scan_result(result: dict) -> None:
    """Print the outcome of a port scan."""
    if 'error' in result:
        print(result['error'])
    else:
        print(OPEN_PORTS_LABEL, ', '.join(result['open_ports']))


def main() -> None:
    """Entry point: parse arguments and run the requested diagnostic."""
    args = parse_args()
    diag = NetworkDiagnostics(args.host)

    handlers: Dict[str, Callable[[], None]] = {
        COMMAND_PING: lambda: print(diag.ping_host(args.c)),
        COMMAND_TRACEROUTE: lambda: print(diag.trace_route()),
        COMMAND_DNS: lambda: print('\n'.join(diag.dns_lookup(args.t))),
        COMMAND_SCAN: lambda: _print_port_scan_result(diag.port_scan(args.ports)),
    }
    handlers[args.command]()


if __name__ == '__main__':
    main()
