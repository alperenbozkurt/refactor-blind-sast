import subprocess
import argparse
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
DEFAULT_HISTORY_FILE = 'monitor_history.json'
DEFAULT_DISK_PATH = '/'
JSON_INDENT = 2

DF_COMMAND = ['df', '-h']
PS_COMMAND_TEMPLATE = "ps aux | grep '{process_name}' | grep -v grep"

PS_USER_INDEX = 0
PS_PID_INDEX = 1
PS_CPU_INDEX = 2
PS_MEM_INDEX = 3
PS_COMMAND_START_INDEX = 10

LOG_SUCCESS_MESSAGE = 'Metric logged successfully'


# --------------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------------- #
def _parse_df_output(output: str) -> Dict:
    """Parse the output of ``df -h <path>`` into a header -> value mapping."""
    lines = output.split('\n')
    headers = lines[0].split()
    values = lines[1].split()
    return dict(zip(headers, values))


def _parse_ps_line(line: str) -> Dict:
    """Parse a single line of ``ps aux`` output into a process record."""
    parts = line.split()
    return {
        'user': parts[PS_USER_INDEX],
        'pid': parts[PS_PID_INDEX],
        'cpu': parts[PS_CPU_INDEX],
        'mem': parts[PS_MEM_INDEX],
        'command': ' '.join(parts[PS_COMMAND_START_INDEX:]),
    }


def _parse_ps_output(output: str) -> List[Dict]:
    """Parse the full ``ps aux | grep`` output into a list of process records."""
    return [_parse_ps_line(line) for line in output.split('\n') if line.strip()]


def _build_ps_command(process_name: str) -> str:
    return PS_COMMAND_TEMPLATE.format(process_name=process_name)


def _print_json(data) -> None:
    print(json.dumps(data, indent=JSON_INDENT))


# --------------------------------------------------------------------------- #
# Core class
# --------------------------------------------------------------------------- #
class SystemMonitor:

    def __init__(self):
        self.history_file = DEFAULT_HISTORY_FILE
        self.history = self._load_history()

    def _load_history(self) -> Dict:
        try:
            with open(self.history_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_history(self):
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f)

    def check_disk_usage(self, path: str=DEFAULT_DISK_PATH) -> Dict:
        try:
            output = subprocess.check_output(DF_COMMAND + [path]).decode()
            return _parse_df_output(output)
        except subprocess.CalledProcessError as e:
            return {'error': str(e)}

    def check_process(self, process_name: str) -> Dict:
        try:
            output = subprocess.check_output(_build_ps_command(process_name), shell=True).decode()
            return {'processes': _parse_ps_output(output)}
        except subprocess.CalledProcessError:
            return {'processes': []}

    def log_metric(self, metric_name: str, value: float):
        timestamp = datetime.now().isoformat()
        if metric_name not in self.history:
            self.history[metric_name] = []
        self.history[metric_name].append({'timestamp': timestamp, 'value': value})
        self._save_history()

    def get_metric_history(self, metric_name: str) -> List[Dict]:
        return self.history.get(metric_name, [])


# --------------------------------------------------------------------------- #
# Command-line interface
# --------------------------------------------------------------------------- #
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='System Monitoring Tool')
    subparsers = parser.add_subparsers(dest='command', required=True)

    disk_parser = subparsers.add_parser('disk')
    disk_parser.add_argument('--path', default=DEFAULT_DISK_PATH, help='Path to check disk usage')

    process_parser = subparsers.add_parser('process')
    process_parser.add_argument('name', help='Process name to check')

    log_parser = subparsers.add_parser('log')
    log_parser.add_argument('metric', help='Metric name to log')
    log_parser.add_argument('value', type=float, help='Metric value')

    history_parser = subparsers.add_parser('history')
    history_parser.add_argument('metric', help='Metric name to view history')

    return parser


def _handle_disk(monitor: SystemMonitor, args) -> None:
    _print_json(monitor.check_disk_usage(args.path))


def _handle_process(monitor: SystemMonitor, args) -> None:
    _print_json(monitor.check_process(args.name))


def _handle_log(monitor: SystemMonitor, args) -> None:
    monitor.log_metric(args.metric, args.value)
    print(LOG_SUCCESS_MESSAGE)


def _handle_history(monitor: SystemMonitor, args) -> None:
    _print_json(monitor.get_metric_history(args.metric))


COMMAND_HANDLERS = {
    'disk': _handle_disk,
    'process': _handle_process,
    'log': _handle_log,
    'history': _handle_history,
}


def main():
    parser = _build_parser()
    args = parser.parse_args()
    monitor = SystemMonitor()
    handler = COMMAND_HANDLERS.get(args.command)
    if handler is not None:
        handler(monitor, args)


if __name__ == '__main__':
    main()
