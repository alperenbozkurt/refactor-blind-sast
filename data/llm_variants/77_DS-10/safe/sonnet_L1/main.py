import subprocess
import argparse
import sys
import re
from typing import Optional, Dict, List

IP_PATTERN = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
IFCONFIG_INET_PATTERN = re.compile(r'inet (\d+\.\d+\.\d+\.\d+)')
KERNEL_PARAM_PATTERN = re.compile(r'^[a-zA-Z0-9_.-]+$')

DEFAULT_INTERFACE = 'eth0'
DEFAULT_NETMASK = '255.255.255.0'
DEFAULT_SYSCTL_PATH = '/proc/sys/net/ipv4/'


def _print_error(message: str) -> None:
    print(message, file=sys.stderr)


class NetworkConfigurator:

    def __init__(self, interface: str = DEFAULT_INTERFACE):
        self.interface = interface
        self.sysctl_path = DEFAULT_SYSCTL_PATH

    def validate_ip(self, ip: str) -> bool:
        return IP_PATTERN.match(ip) is not None

    def get_current_config(self) -> Dict[str, str]:
        config = {}
        try:
            result = subprocess.run(
                ['ifconfig', self.interface],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                config['interface'] = self.interface
                ip_match = IFCONFIG_INET_PATTERN.search(result.stdout)
                if ip_match:
                    config['ip'] = ip_match.group(1)
        except Exception:
            pass
        return config

    def set_static_ip(self, ip: str, netmask: str = DEFAULT_NETMASK) -> bool:
        if not self.validate_ip(ip) or not self.validate_ip(netmask):
            _print_error('Invalid IP address format')
            return False
        try:
            subprocess.run(
                ['ifconfig', self.interface, ip, 'netmask', netmask],
                check=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            _print_error(f'Failed to set IP: {e}')
            return False

    def configure_kernel_param(self, param: str, value: str) -> bool:
        try:
            if not KERNEL_PARAM_PATTERN.match(param):
                _print_error('Invalid parameter name')
                return False
            param_path = f"{self.sysctl_path}{param.replace('.', '/')}"
            with open(param_path, 'w') as f:
                f.write(value)
            return True
        except FileNotFoundError:
            _print_error(f'Parameter not found: {param}')
            return False
        except PermissionError:
            _print_error(f'Permission denied when writing to {param}')
            return False
        except Exception as e:
            _print_error(f'Failed to configure parameter: {e}')
            return False

    def apply_routing_rules(self, rules: List[str]) -> bool:
        try:
            for rule in rules:
                subprocess.run(['ip', 'route', 'add'] + rule.split(), check=True)
            return True
        except subprocess.CalledProcessError as e:
            _print_error(f'Failed to apply routing rules: {e}')
            return False


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Network Configuration Tool')
    parser.add_argument('--interface', default=DEFAULT_INTERFACE,
                        help='Network interface to configure')
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
    print(f"Interface: {config.get('interface', 'N/A')}")
    print(f"IP Address: {config.get('ip', 'N/A')}")


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
    args = _build_parser().parse_args()
    configurator = NetworkConfigurator(args.interface)
    handler = COMMAND_HANDLERS.get(args.command)
    if handler is not None:
        handler(configurator, args)


if __name__ == '__main__':
    main()
