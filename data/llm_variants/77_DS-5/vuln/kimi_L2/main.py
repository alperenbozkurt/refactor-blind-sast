"""System monitoring tool.

Provides disk-usage checks, process lookups and persistent metric logging,
exposed both through the :class:`SystemMonitor` class and a command-line
interface.
"""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

HISTORY_FILE_NAME = 'monitor_history.json'
LOG_SUCCESS_MESSAGE = 'Metric logged successfully'
JSON_INDENT = 2

COMMAND_DISK = 'disk'
COMMAND_PROCESS = 'process'
COMMAND_LOG = 'log'
COMMAND_HISTORY = 'history'

# Field positions in ``ps aux`` output.
PS_USER_FIELD = 0
PS_PID_FIELD = 1
PS_CPU_FIELD = 2
PS_MEM_FIELD = 3
PS_COMMAND_FIELD_START = 10


@dataclass(frozen=True)
class MonitorConfig:
    """Configuration values for :class:`SystemMonitor`."""

    history_file: str = HISTORY_FILE_NAME


# ---------------------------------------------------------------------------
# Subprocess and output-parsing helpers
# ---------------------------------------------------------------------------

def _run_command(command, shell: bool = False) -> str:
    """Run *command* and return its decoded standard output."""
    return subprocess.check_output(command, shell=shell).decode()


def _build_process_search_command(process_name: str) -> str:
    """Build the shell pipeline used to find processes matching a name."""
    return f"ps aux | grep '{process_name}' | grep -v grep"


def _parse_df_output(output: str) -> Dict:
    """Turn ``df -h`` output into a header -> value mapping."""
    lines = output.split('\n')
    headers = lines[0].split()
    values = lines[1].split()
    return dict(zip(headers, values))


def _parse_ps_line(line: str) -> Dict:
    """Parse a single ``ps aux`` output line into a process description."""
    parts = line.split()
    return {
        'user': parts[PS_USER_FIELD],
        'pid': parts[PS_PID_FIELD],
        'cpu': parts[PS_CPU_FIELD],
        'mem': parts[PS_MEM_FIELD],
        'command': ' '.join(parts[PS_COMMAND_FIELD_START:]),
    }


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------

class SystemMonitor:

    def __init__(self):
        self._config = MonitorConfig()
        self.history_file = self._config.history_file
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

    def check_disk_usage(self, path: str='/') -> Dict:
        try:
            output = _run_command(['df', '-h', path])
            return _parse_df_output(output)
        except subprocess.CalledProcessError as e:
            return {'error': str(e)}

    def check_process(self, process_name: str) -> Dict:
        try:
            output = _run_command(_build_process_search_command(process_name), shell=True)
            processes = [
                _parse_ps_line(line)
                for line in output.split('\n')
                if line.strip()
            ]
            return {'processes': processes}
        except subprocess.CalledProcessError:
            return {'processes': []}

    def log_metric(self, metric_name: str, value: float):
        entry = {'timestamp': datetime.now().isoformat(), 'value': value}
        self.history.setdefault(metric_name, []).append(entry)
        self._save_history()

    def get_metric_history(self, metric_name: str) -> List[Dict]:
        return self.history.get(metric_name, [])


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='System Monitoring Tool')
    subparsers = parser.add_subparsers(dest='command', required=True)

    disk_parser = subparsers.add_parser(COMMAND_DISK)
    disk_parser.add_argument('--path', default='/', help='Path to check disk usage')

    process_parser = subparsers.add_parser(COMMAND_PROCESS)
    process_parser.add_argument('name', help='Process name to check')

    log_parser = subparsers.add_parser(COMMAND_LOG)
    log_parser.add_argument('metric', help='Metric name to log')
    log_parser.add_argument('value', type=float, help='Metric value')

    history_parser = subparsers.add_parser(COMMAND_HISTORY)
    history_parser.add_argument('metric', help='Metric name to view history')

    return parser


def _print_json(data) -> None:
    print(json.dumps(data, indent=JSON_INDENT))


def _handle_disk_command(args, monitor: SystemMonitor) -> None:
    _print_json(monitor.check_disk_usage(args.path))


def _handle_process_command(args, monitor: SystemMonitor) -> None:
    _print_json(monitor.check_process(args.name))


def _handle_log_command(args, monitor: SystemMonitor) -> None:
    monitor.log_metric(args.metric, args.value)
    print(LOG_SUCCESS_MESSAGE)


def _handle_history_command(args, monitor: SystemMonitor) -> None:
    _print_json(monitor.get_metric_history(args.metric))


_COMMAND_HANDLERS = {
    COMMAND_DISK: _handle_disk_command,
    COMMAND_PROCESS: _handle_process_command,
    COMMAND_LOG: _handle_log_command,
    COMMAND_HISTORY: _handle_history_command,
}


def main():
    args = _build_argument_parser().parse_args()
    monitor = SystemMonitor()
    _COMMAND_HANDLERS[args.command](args, monitor)


if __name__ == '__main__':
    main()
