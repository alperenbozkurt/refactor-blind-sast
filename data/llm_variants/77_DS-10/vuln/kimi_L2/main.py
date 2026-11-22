"""Network configuration command-line tool.

Exposes the :class:`NetworkConfigurator` class for inspecting and modifying
interface settings, kernel parameters, and routing rules, together with a
small ``argparse``-powered command-line interface.
"""

import argparse
import re
import subprocess
import sys
from typing import Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_INTERFACE = 'eth0'
DEFAULT_NETMASK = '255.255.255.0'
SYSCTL_IPV4_PATH = '/proc/sys/net/ipv4/'

IFCONFIG_COMMAND = 'ifconfig'
IP_COMMAND = 'ip'
SYSCTL_COMMAND = 'sysctl'
SYSCTL_IPV4_PREFIX = 'net.ipv4'

IP_ADDRESS_PATTERN = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
INET_ADDRESS_PATTERN = re.compile(r'inet (\d+\.\d+\.\d+\.\d+)')

INVALID_IP_MESSAGE = 'Invalid IP address format'
SET_IP_FAILURE_MESSAGE = 'Failed to set IP'
CONFIGURE_PARAM_FAILURE_MESSAGE = 'Failed to configure parameter'
ROUTE_FAILURE_MESSAGE = 'Failed to apply routing rules'

COMMAND_SHOW = 'show'
COMMAND_IP = 'ip'
COMMAND_SYSCTL = 'sysctl'
COMMAND_ROUTE = 'route'


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _print_error(message: str) -> None:
    """Write *message* to standard error."""
    print(message, file=sys.stderr)


def _extract_inet_address(ifconfig_output: str) -> Optional[str]:
    """Pull the first dotted-quad address out of ``ifconfig`` output."""
    match = INET_ADDRESS_PATTERN.search(ifconfig_output)
    if match:
        return match.group(1)
    return None


def _build_sysctl_command(param: str, value: str) -> str:
    """Build the shell command used to write an IPv4 kernel parameter."""
    return f"{SYSCTL_COMMAND} -w {SYSCTL_IPV4_PREFIX}.{param}='{value}'"


def _report_outcome(label: str, success: bool) -> None:
    """Print a uniform success/failure line for a configuration action."""
    print(label, 'succeeded' if success else 'failed')


# ---------------------------------------------------------------------------
# Core configurator
# ---------------------------------------------------------------------------

class NetworkConfigurator:
    """Configure network interfaces, kernel parameters, and routing rules."""

    def __init__(self, interface: str = DEFAULT_INTERFACE):
        self.interface = interface
        self.sysctl_path = SYSCTL_IPV4_PATH

    def validate_ip(self, ip: str) -> bool:
        """Return True when *ip* matches the expected dotted-quad format."""
        return IP_ADDRESS_PATTERN.match(ip) is not None

    def get_current_config(self) -> Dict[str, str]:
        """Return the current interface configuration reported by ifconfig."""
        config: Dict[str, str] = {}
        try:
            result = subprocess.run(
                [IFCONFIG_COMMAND, self.interface],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                config['interface'] = self.interface
                ip_address = _extract_inet_address(result.stdout)
                if ip_address is not None:
                    config['ip'] = ip_address
        except Exception:
            pass
        return config

    def set_static_ip(self, ip: str, netmask: str = DEFAULT_NETMASK) -> bool:
        """Assign a static IP address/netmask to the configured interface."""
        if not self.validate_ip(ip) or not self.validate_ip(netmask):
            _print_error(INVALID_IP_MESSAGE)
            return False
        try:
            subprocess.run(
                [IFCONFIG_COMMAND, self.interface, ip, 'netmask', netmask],
                check=True,
            )
            return True
        except subprocess.CalledProcessError as exc:
            _print_error(f'{SET_IP_FAILURE_MESSAGE}: {exc}')
            return False

    def configure_kernel_param(self, param: str, value: str) -> bool:
        """Write an IPv4 kernel parameter via ``sysctl -w``."""
        try:
            subprocess.run(_build_sysctl_command(param, value), shell=True, check=True)
            return True
        except subprocess.CalledProcessError as exc:
            _print_error(f'{CONFIGURE_PARAM_FAILURE_MESSAGE}: {exc}')
            return False

    def apply_routing_rules(self, rules: List[str]) -> bool:
        """Apply each rule in *rules* with ``ip route add``."""
        try:
            for rule in rules:
                subprocess.run([IP_COMMAND, 'route', 'add'] + rule.split(), check=True)
            return True
        except subprocess.CalledProcessError as exc:
            _print_error(f'{ROUTE_FAILURE_MESSAGE}: {exc}')
            return False


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

CommandHandler = Callable[[NetworkConfigurator, argparse.Namespace], None]


def _handle_show(configurator: NetworkConfigurator, args: argparse.Namespace) -> None:
    config = configurator.get_current_config()
    print(f"Interface: {config.get('interface', 'N/A')}")
    print(f"IP Address: {config.get('ip', 'N/A')}")


def _handle_ip(configurator: NetworkConfigurator, args: argparse.Namespace) -> None:
    success = configurator.set_static_ip(args.address, args.netmask)
    _report_outcome('IP configuration', success)


def _handle_sysctl(configurator: NetworkConfigurator, args: argparse.Namespace) -> None:
    success = configurator.configure_kernel_param(args.parameter, args.value)
    _report_outcome('Parameter configuration', success)


def _handle_route(configurator: NetworkConfigurator, args: argparse.Namespace) -> None:
    success = configurator.apply_routing_rules(args.rules)
    _report_outcome('Routing configuration', success)


_COMMAND_HANDLERS: Dict[str, CommandHandler] = {
    COMMAND_SHOW: _handle_show,
    COMMAND_IP: _handle_ip,
    COMMAND_SYSCTL: _handle_sysctl,
    COMMAND_ROUTE: _handle_route,
}


def _build_argument_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for the command-line interface."""
    parser = argparse.ArgumentParser(description='Network Configuration Tool')
    parser.add_argument('--interface', default=DEFAULT_INTERFACE,
                        help='Network interface to configure')
    subparsers = parser.add_subparsers(dest='command', required=True)

    subparsers.add_parser(COMMAND_SHOW, help='Show current configuration')

    ip_parser = subparsers.add_parser(COMMAND_IP, help='Set static IP address')
    ip_parser.add_argument('address', help='IP address to set')
    ip_parser.add_argument('--netmask', default=DEFAULT_NETMASK,
                           help='Network mask')

    sysctl_parser = subparsers.add_parser(COMMAND_SYSCTL,
                                          help='Configure kernel parameter')
    sysctl_parser.add_argument('parameter', help='Parameter name')
    sysctl_parser.add_argument('value', help='Parameter value')

    route_parser = subparsers.add_parser(COMMAND_ROUTE, help='Add routing rule')
    route_parser.add_argument('rules', nargs='+', help='Routing rules to add')

    return parser


def main():
    parser = _build_argument_parser()
    args = parser.parse_args()
    configurator = NetworkConfigurator(args.interface)
    _COMMAND_HANDLERS[args.command](configurator, args)


if __name__ == '__main__':
    main()
