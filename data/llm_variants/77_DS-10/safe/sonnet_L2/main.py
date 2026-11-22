import subprocess
import argparse
import sys
import re
from typing import Optional, Dict, List

DEFAULT_INTERFACE = 'eth0'
DEFAULT_NETMASK = '255.255.255.0'
DEFAULT_SYSCTL_PATH = '/proc/sys/net/ipv4/'

IP_VALIDATION_PATTERN = '^(\\d{1,3}\\.){3}\\d{1,3}$'
IFCONFIG_IP_PATTERN = 'inet (\\d+\\.\\d+\\.\\d+\\.\\d+)'
KERNEL_PARAM_PATTERN = '^[a-zA-Z0-9_.-]+$'

_IP_REGEX = re.compile(IP_VALIDATION_PATTERN)
_IFCONFIG_IP_REGEX = re.compile(IFCONFIG_IP_PATTERN)
_KERNEL_PARAM_REGEX = re.compile(KERNEL_PARAM_PATTERN)

NOT_AVAILABLE = 'N/A'


def _error(message: str) -> None:
    """Print an error message to stderr."""
    print(message, file=sys.stderr)


class NetworkConfigurator:

    def __init__(self, interface: str=DEFAULT_INTERFACE):
        self.interface = interface
        self.sysctl_path = DEFAULT_SYSCTL_PATH

    def validate_ip(self, ip: str) -> bool:
        return _IP_REGEX.match(ip) is not None

    def _kernel_param_path(self, param: str) -> str:
        return f"{self.sysctl_path}{param.replace('.', '/')}"

    def get_current_config(self) -> Dict[str, str]:
        config = {}
        try:
            result = subprocess.run(['ifconfig', self.interface], capture_output=True, text=True)
            if result.returncode == 0:
                config['interface'] = self.interface
                ip_match = _IFCONFIG_IP_REGEX.search(result.stdout)
                if ip_match:
                    config['ip'] = ip_match.group(1)
        except Exception:
            pass
        return config

    def set_static_ip(self, ip: str, netmask: str=DEFAULT_NETMASK) -> bool:
        if not self.validate_ip(ip) or not self.validate_ip(netmask):
            _error('Invalid IP address format')
            return False
        try:
            subprocess.run(['ifconfig', self.interface, ip, 'netmask', netmask], check=True)
            return True
        except subprocess.CalledProcessError as e:
            _error(f'Failed to set IP: {e}')
            return False

    def configure_kernel_param(self, param: str, value: str) -> bool:
        try:
            if not _KERNEL_PARAM_REGEX.match(param):
                _error('Invalid parameter name')
                return False
            param_path = self._kernel_param_path(param)
            with open(param_path, 'w') as f:
                f.write(value)
            return True
        except FileNotFoundError:
            _error(f'Parameter not found: {param}')
            return False
        except PermissionError:
            _error(f'Permission denied when writing to {param}')
            return False
        except Exception as e:
            _error(f'Failed to configure parameter: {e}')
            return False

    def apply_routing_rules(self, rules: List[str]) -> bool:
        try:
            for rule in rules:
                subprocess.run(['ip', 'route', 'add'] + rule.split(), check=True)
            return True
        except subprocess.CalledProcessError as e:
            _error(f'Failed to apply routing rules: {e}')
            return False


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Network Configuration Tool')
    parser.add_argument('--interface', default=DEFAULT_INTERFACE, help='Network interface to configure')
    subparsers = parser.add_subparsers(dest='command', required=True)

    subparsers.add_parser('show', help='Show current configuration')

    ip_parser = subparsers.add_parser('ip', help='Set static IP address')
    ip_parser.add_argument('address', help='IP address to set')
    ip_parser.add_argument('--netmask', default=DEFAULT_NETMASK, help='Network mask')

    sysctl_parser = subparsers.add_parser('sysctl', help='Configure kernel parameter')
    sysctl_parser.add_argument('parameter', help='Parameter name')
    sysctl_parser.add_argument('value', help='Parameter value')

    route_parser = subparsers.add_parser('route', help='Add routing rule')
    route_parser.add_argument('rules', nargs='+', help='Routing rules to add')
    return parser


def _report_result(label: str, success: bool) -> None:
    print(label, 'succeeded' if success else 'failed')


def _handle_show(configurator: NetworkConfigurator, args: argparse.Namespace) -> None:
    config = configurator.get_current_config()
    print(f"Interface: {config.get('interface', NOT_AVAILABLE)}")
    print(f"IP Address: {config.get('ip', NOT_AVAILABLE)}")


def _handle_ip(configurator: NetworkConfigurator, args: argparse.Namespace) -> None:
    success = configurator.set_static_ip(args.address, args.netmask)
    _report_result('IP configuration', success)


def _handle_sysctl(configurator: NetworkConfigurator, args: argparse.Namespace) -> None:
    success = configurator.configure_kernel_param(args.parameter, args.value)
    _report_result('Parameter configuration', success)


def _handle_route(configurator: NetworkConfigurator, args: argparse.Namespace) -> None:
    success = configurator.apply_routing_rules(args.rules)
    _report_result('Routing configuration', success)


COMMAND_HANDLERS = {
    'show': _handle_show,
    'ip': _handle_ip,
    'sysctl': _handle_sysctl,
    'route': _handle_route,
}


def main():
    parser = _build_parser()
    args = parser.parse_args()
    configurator = NetworkConfigurator(args.interface)
    handler = COMMAND_HANDLERS.get(args.command)
    if handler is not None:
        handler(configurator, args)


if __name__ == '__main__':
    main()
