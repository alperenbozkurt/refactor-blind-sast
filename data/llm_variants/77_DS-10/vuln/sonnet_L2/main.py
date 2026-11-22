import subprocess
import argparse
import sys
import re
from typing import Optional, Dict, List

DEFAULT_INTERFACE = 'eth0'
DEFAULT_NETMASK = '255.255.255.0'
SYSCTL_IPV4_PATH = '/proc/sys/net/ipv4/'

IP_VALIDATION_PATTERN = '^(\\d{1,3}\\.){3}\\d{1,3}$'
IFCONFIG_INET_PATTERN = 'inet (\\d+\\.\\d+\\.\\d+\\.\\d+)'

CMD_SHOW = 'show'
CMD_IP = 'ip'
CMD_SYSCTL = 'sysctl'
CMD_ROUTE = 'route'

NOT_AVAILABLE = 'N/A'


def _print_error(message: str) -> None:
    print(message, file=sys.stderr)


def _status_word(success: bool) -> str:
    return 'succeeded' if success else 'failed'


class NetworkConfigurator:

    def __init__(self, interface: str=DEFAULT_INTERFACE):
        self.interface = interface
        self.sysctl_path = SYSCTL_IPV4_PATH

    def validate_ip(self, ip: str) -> bool:
        return re.match(IP_VALIDATION_PATTERN, ip) is not None

    def _query_interface(self) -> 'subprocess.CompletedProcess':
        return subprocess.run(['ifconfig', self.interface], capture_output=True, text=True)

    @staticmethod
    def _extract_ip(ifconfig_output: str) -> Optional[str]:
        match = re.search(IFCONFIG_INET_PATTERN, ifconfig_output)
        return match.group(1) if match else None

    def get_current_config(self) -> Dict[str, str]:
        config = {}
        try:
            result = self._query_interface()
            if result.returncode == 0:
                config['interface'] = self.interface
                ip = self._extract_ip(result.stdout)
                if ip:
                    config['ip'] = ip
        except Exception:
            pass
        return config

    def set_static_ip(self, ip: str, netmask: str=DEFAULT_NETMASK) -> bool:
        if not self.validate_ip(ip) or not self.validate_ip(netmask):
            _print_error('Invalid IP address format')
            return False
        try:
            subprocess.run(['ifconfig', self.interface, ip, 'netmask', netmask], check=True)
            return True
        except subprocess.CalledProcessError as e:
            _print_error(f'Failed to set IP: {e}')
            return False

    @staticmethod
    def _build_sysctl_command(param: str, value: str) -> str:
        return f"sysctl -w net.ipv4.{param}='{value}'"

    def configure_kernel_param(self, param: str, value: str) -> bool:
        try:
            cmd = self._build_sysctl_command(param, value)
            subprocess.run(cmd, shell=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            _print_error(f'Failed to configure parameter: {e}')
            return False

    @staticmethod
    def _add_route(rule: str) -> None:
        subprocess.run(['ip', 'route', 'add'] + rule.split(), check=True)

    def apply_routing_rules(self, rules: List[str]) -> bool:
        try:
            for rule in rules:
                self._add_route(rule)
            return True
        except subprocess.CalledProcessError as e:
            _print_error(f'Failed to apply routing rules: {e}')
            return False


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Network Configuration Tool')
    parser.add_argument('--interface', default=DEFAULT_INTERFACE, help='Network interface to configure')
    subparsers = parser.add_subparsers(dest='command', required=True)

    subparsers.add_parser(CMD_SHOW, help='Show current configuration')

    ip_parser = subparsers.add_parser(CMD_IP, help='Set static IP address')
    ip_parser.add_argument('address', help='IP address to set')
    ip_parser.add_argument('--netmask', default=DEFAULT_NETMASK, help='Network mask')

    sysctl_parser = subparsers.add_parser(CMD_SYSCTL, help='Configure kernel parameter')
    sysctl_parser.add_argument('parameter', help='Parameter name')
    sysctl_parser.add_argument('value', help='Parameter value')

    route_parser = subparsers.add_parser(CMD_ROUTE, help='Add routing rule')
    route_parser.add_argument('rules', nargs='+', help='Routing rules to add')
    return parser


def _handle_show(configurator: NetworkConfigurator, args: argparse.Namespace) -> None:
    config = configurator.get_current_config()
    print(f"Interface: {config.get('interface', NOT_AVAILABLE)}")
    print(f"IP Address: {config.get('ip', NOT_AVAILABLE)}")


def _handle_ip(configurator: NetworkConfigurator, args: argparse.Namespace) -> None:
    success = configurator.set_static_ip(args.address, args.netmask)
    print('IP configuration', _status_word(success))


def _handle_sysctl(configurator: NetworkConfigurator, args: argparse.Namespace) -> None:
    success = configurator.configure_kernel_param(args.parameter, args.value)
    print('Parameter configuration', _status_word(success))


def _handle_route(configurator: NetworkConfigurator, args: argparse.Namespace) -> None:
    success = configurator.apply_routing_rules(args.rules)
    print('Routing configuration', _status_word(success))


COMMAND_HANDLERS = {
    CMD_SHOW: _handle_show,
    CMD_IP: _handle_ip,
    CMD_SYSCTL: _handle_sysctl,
    CMD_ROUTE: _handle_route,
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
