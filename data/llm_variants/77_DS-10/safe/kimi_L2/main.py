import subprocess
import argparse
import sys
import re
from typing import Optional, Dict, List

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

DEFAULT_INTERFACE = 'eth0'
DEFAULT_NETMASK = '255.255.255.0'
SYSCTL_BASE_PATH = '/proc/sys/net/ipv4/'

IP_ADDRESS_PATTERN = '^(\\d{1,3}\\.){3}\\d{1,3}$'
INET_ADDRESS_PATTERN = 'inet (\\d+\\.\\d+\\.\\d+\\.\\d+)'
KERNEL_PARAM_NAME_PATTERN = '^[a-zA-Z0-9_.-]+$'

IFCONFIG_EXECUTABLE = 'ifconfig'
IP_EXECUTABLE = 'ip'

COMMAND_SHOW = 'show'
COMMAND_IP = 'ip'
COMMAND_SYSCTL = 'sysctl'
COMMAND_ROUTE = 'route'


def _print_error(message: str) -> None:
    """Print an error message to standard error."""
    print(message, file=sys.stderr)


class NetworkConfigurator:
    """Configure network interfaces, kernel parameters and routing rules."""

    def __init__(self, interface: str='eth0'):
        self.interface = interface
        self.sysctl_path = SYSCTL_BASE_PATH

    def validate_ip(self, ip: str) -> bool:
        return re.match(IP_ADDRESS_PATTERN, ip) is not None

    def get_current_config(self) -> Dict[str, str]:
        config = {}
        try:
            result = subprocess.run(
                [IFCONFIG_EXECUTABLE, self.interface],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                config['interface'] = self.interface
                ip = self._extract_ip_address(result.stdout)
                if ip is not None:
                    config['ip'] = ip
        except Exception:
            pass
        return config

    def set_static_ip(self, ip: str, netmask: str='255.255.255.0') -> bool:
        if not self.validate_ip(ip) or not self.validate_ip(netmask):
            _print_error('Invalid IP address format')
            return False
        try:
            subprocess.run(
                [IFCONFIG_EXECUTABLE, self.interface, ip, 'netmask', netmask],
                check=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            _print_error(f'Failed to set IP: {e}')
            return False

    def configure_kernel_param(self, param: str, value: str) -> bool:
        try:
            if not self._is_valid_param_name(param):
                _print_error('Invalid parameter name')
                return False
            with open(self._kernel_param_path(param), 'w') as f:
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
                self._add_routing_rule(rule)
            return True
        except subprocess.CalledProcessError as e:
            _print_error(f'Failed to apply routing rules: {e}')
            return False

    # -- internal helpers ----------------------------------------------------

    @staticmethod
    def _extract_ip_address(ifconfig_output: str) -> Optional[str]:
        match = re.search(INET_ADDRESS_PATTERN, ifconfig_output)
        return match.group(1) if match else None

    @staticmethod
    def _is_valid_param_name(param: str) -> bool:
        return re.match(KERNEL_PARAM_NAME_PATTERN, param) is not None

    def _kernel_param_path(self, param: str) -> str:
        return f"{self.sysctl_path}{param.replace('.', '/')}"

    @staticmethod
    def _add_routing_rule(rule: str) -> None:
        subprocess.run([IP_EXECUTABLE, 'route', 'add'] + rule.split(), check=True)


# ---------------------------------------------------------------------------
# Command-line interface helpers
# ---------------------------------------------------------------------------

def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Network Configuration Tool')
    parser.add_argument(
        '--interface',
        default=DEFAULT_INTERFACE,
        help='Network interface to configure',
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    subparsers.add_parser(COMMAND_SHOW, help='Show current configuration')

    ip_parser = subparsers.add_parser(COMMAND_IP, help='Set static IP address')
    ip_parser.add_argument('address', help='IP address to set')
    ip_parser.add_argument(
        '--netmask',
        default=DEFAULT_NETMASK,
        help='Network mask',
    )

    sysctl_parser = subparsers.add_parser(
        COMMAND_SYSCTL, help='Configure kernel parameter'
    )
    sysctl_parser.add_argument('parameter', help='Parameter name')
    sysctl_parser.add_argument('value', help='Parameter value')

    route_parser = subparsers.add_parser(COMMAND_ROUTE, help='Add routing rule')
    route_parser.add_argument('rules', nargs='+', help='Routing rules to add')

    return parser


def _report_outcome(label: str, success: bool) -> None:
    print(label, 'succeeded' if success else 'failed')


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


_COMMAND_HANDLERS = {
    COMMAND_SHOW: _handle_show,
    COMMAND_IP: _handle_ip,
    COMMAND_SYSCTL: _handle_sysctl,
    COMMAND_ROUTE: _handle_route,
}


def main():
    parser = _build_argument_parser()
    args = parser.parse_args()
    configurator = NetworkConfigurator(args.interface)
    _COMMAND_HANDLERS[args.command](configurator, args)


if __name__ == '__main__':
    main()
