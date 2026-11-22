import subprocess
import argparse
import sys
import re
from typing import Optional, Dict, List

_IP_PATTERN = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
_INET_PATTERN = re.compile(r'inet (\d+\.\d+\.\d+\.\d+)')


def _log_error(message: str) -> None:
    print(message, file=sys.stderr)


class NetworkConfigurator:

    def __init__(self, interface: str = 'eth0'):
        self.interface = interface
        self.sysctl_path = '/proc/sys/net/ipv4/'

    def validate_ip(self, ip: str) -> bool:
        return _IP_PATTERN.match(ip) is not None

    def get_current_config(self) -> Dict[str, str]:
        config: Dict[str, str] = {}
        try:
            result = subprocess.run(
                ['ifconfig', self.interface], capture_output=True, text=True
            )
            if result.returncode == 0:
                config['interface'] = self.interface
                ip_match = _INET_PATTERN.search(result.stdout)
                if ip_match:
                    config['ip'] = ip_match.group(1)
        except Exception:
            pass
        return config

    def set_static_ip(self, ip: str, netmask: str = '255.255.255.0') -> bool:
        if not (self.validate_ip(ip) and self.validate_ip(netmask)):
            _log_error('Invalid IP address format')
            return False
        try:
            subprocess.run(
                ['ifconfig', self.interface, ip, 'netmask', netmask], check=True
            )
            return True
        except subprocess.CalledProcessError as e:
            _log_error(f'Failed to set IP: {e}')
            return False

    def configure_kernel_param(self, param: str, value: str) -> bool:
        try:
            # Argument list instead of a shell string: same command for normal
            # input, but avoids shell command injection.
            subprocess.run(
                ['sysctl', '-w', f'net.ipv4.{param}={value}'], check=True
            )
            return True
        except subprocess.CalledProcessError as e:
            _log_error(f'Failed to configure parameter: {e}')
            return False

    def apply_routing_rules(self, rules: List[str]) -> bool:
        try:
            for rule in rules:
                subprocess.run(['ip', 'route', 'add', *rule.split()], check=True)
            return True
        except subprocess.CalledProcessError as e:
            _log_error(f'Failed to apply routing rules: {e}')
            return False


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Network Configuration Tool')
    parser.add_argument('--interface', default='eth0',
                        help='Network interface to configure')
    subparsers = parser.add_subparsers(dest='command', required=True)

    subparsers.add_parser('show', help='Show current configuration')

    ip_parser = subparsers.add_parser('ip', help='Set static IP address')
    ip_parser.add_argument('address', help='IP address to set')
    ip_parser.add_argument('--netmask', default='255.255.255.0',
                           help='Network mask')

    sysctl_parser = subparsers.add_parser('sysctl',
                                          help='Configure kernel parameter')
    sysctl_parser.add_argument('parameter', help='Parameter name')
    sysctl_parser.add_argument('value', help='Parameter value')

    route_parser = subparsers.add_parser('route', help='Add routing rule')
    route_parser.add_argument('rules', nargs='+', help='Routing rules to add')

    return parser


def _report(label: str, success: bool) -> None:
    print(label, 'succeeded' if success else 'failed')


def _handle_show(configurator: NetworkConfigurator, args) -> None:
    config = configurator.get_current_config()
    print(f"Interface: {config.get('interface', 'N/A')}")
    print(f"IP Address: {config.get('ip', 'N/A')}")


def _handle_ip(configurator: NetworkConfigurator, args) -> None:
    _report('IP configuration',
            configurator.set_static_ip(args.address, args.netmask))


def _handle_sysctl(configurator: NetworkConfigurator, args) -> None:
    _report('Parameter configuration',
            configurator.configure_kernel_param(args.parameter, args.value))


def _handle_route(configurator: NetworkConfigurator, args) -> None:
    _report('Routing configuration',
            configurator.apply_routing_rules(args.rules))


_HANDLERS = {
    'show': _handle_show,
    'ip': _handle_ip,
    'sysctl': _handle_sysctl,
    'route': _handle_route,
}


def main():
    args = _build_parser().parse_args()
    configurator = NetworkConfigurator(args.interface)
    handler = _HANDLERS.get(args.command)
    if handler:
        handler(configurator, args)


if __name__ == '__main__':
    main()
