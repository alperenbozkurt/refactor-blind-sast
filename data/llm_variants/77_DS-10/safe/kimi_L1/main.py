"""Command-line tool for inspecting and configuring network settings."""

import argparse
import re
import subprocess
import sys
from typing import Dict, List, Optional

DEFAULT_INTERFACE = 'eth0'
DEFAULT_NETMASK = '255.255.255.0'
SYSCTL_BASE_PATH = '/proc/sys/net/ipv4/'

_IFCONFIG_COMMAND = 'ifconfig'
_IP_ROUTE_ADD_COMMAND = ['ip', 'route', 'add']

_IP_ADDRESS_PATTERN = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
_INET_ADDRESS_PATTERN = re.compile(r'inet (\d+\.\d+\.\d+\.\d+)')
_PARAM_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_.-]+$')


class NetworkConfigurator:
    """Configure a network interface, kernel parameters and routing rules."""

    def __init__(self, interface: str=DEFAULT_INTERFACE):
        self.interface = interface
        self.sysctl_path = SYSCTL_BASE_PATH

    def validate_ip(self, ip: str) -> bool:
        """Return True if ``ip`` is formatted as a dotted-quad IPv4 address."""
        return _IP_ADDRESS_PATTERN.match(ip) is not None

    def get_current_config(self) -> Dict[str, str]:
        """Return the interface's current configuration, if it can be read."""
        config: Dict[str, str] = {}
        try:
            result = subprocess.run(
                [_IFCONFIG_COMMAND, self.interface],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                config['interface'] = self.interface
                ip_match = _INET_ADDRESS_PATTERN.search(result.stdout)
                if ip_match:
                    config['ip'] = ip_match.group(1)
        except Exception:
            pass
        return config

    def set_static_ip(self, ip: str, netmask: str=DEFAULT_NETMASK) -> bool:
        """Assign ``ip``/``netmask`` to the interface; return True on success."""
        if not self.validate_ip(ip) or not self.validate_ip(netmask):
            print('Invalid IP address format', file=sys.stderr)
            return False
        try:
            subprocess.run(
                [_IFCONFIG_COMMAND, self.interface, ip, 'netmask', netmask],
                check=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f'Failed to set IP: {e}', file=sys.stderr)
            return False

    def configure_kernel_param(self, param: str, value: str) -> bool:
        """Write ``value`` to the kernel parameter ``param`` via /proc/sys."""
        try:
            # Validation stays inside the try block so unexpected errors
            # (e.g. a non-string ``param``) are reported consistently.
            if not _PARAM_NAME_PATTERN.match(param):
                print('Invalid parameter name', file=sys.stderr)
                return False
            param_path = f"{self.sysctl_path}{param.replace('.', '/')}"
            with open(param_path, 'w') as f:
                f.write(value)
            return True
        except FileNotFoundError:
            print(f'Parameter not found: {param}', file=sys.stderr)
            return False
        except PermissionError:
            print(f'Permission denied when writing to {param}', file=sys.stderr)
            return False
        except Exception as e:
            print(f'Failed to configure parameter: {e}', file=sys.stderr)
            return False

    def apply_routing_rules(self, rules: List[str]) -> bool:
        """Apply each rule with ``ip route add``; return True if all succeed."""
        try:
            for rule in rules:
                subprocess.run(_IP_ROUTE_ADD_COMMAND + rule.split(), check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f'Failed to apply routing rules: {e}', file=sys.stderr)
            return False


def _build_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(description='Network Configuration Tool')
    parser.add_argument('--interface', default=DEFAULT_INTERFACE,
                        help='Network interface to configure')

    subparsers = parser.add_subparsers(dest='command', required=True)

    subparsers.add_parser('show', help='Show current configuration')

    ip_parser = subparsers.add_parser('ip', help='Set static IP address')
    ip_parser.add_argument('address', help='IP address to set')
    ip_parser.add_argument('--netmask', default=DEFAULT_NETMASK,
                           help='Network mask')

    sysctl_parser = subparsers.add_parser('sysctl',
                                          help='Configure kernel parameter')
    sysctl_parser.add_argument('parameter', help='Parameter name')
    sysctl_parser.add_argument('value', help='Parameter value')

    route_parser = subparsers.add_parser('route', help='Add routing rule')
    route_parser.add_argument('rules', nargs='+', help='Routing rules to add')

    return parser


def main():
    parser = _build_argument_parser()
    args = parser.parse_args()

    configurator = NetworkConfigurator(args.interface)

    if args.command == 'show':
        config = configurator.get_current_config()
        print(f"Interface: {config.get('interface', 'N/A')}")
        print(f"IP Address: {config.get('ip', 'N/A')}")
    elif args.command == 'ip':
        success = configurator.set_static_ip(args.address, args.netmask)
        print(f"IP configuration {'succeeded' if success else 'failed'}")
    elif args.command == 'sysctl':
        success = configurator.configure_kernel_param(args.parameter, args.value)
        print(f"Parameter configuration {'succeeded' if success else 'failed'}")
    elif args.command == 'route':
        success = configurator.apply_routing_rules(args.rules)
        print(f"Routing configuration {'succeeded' if success else 'failed'}")


if __name__ == '__main__':
    main()
