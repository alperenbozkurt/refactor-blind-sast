"""Command-line system monitoring tool.

Provides disk-usage and process inspection commands along with a simple
JSON-file-backed metric history log.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

HISTORY_FILE_PATH = 'monitor_history.json'
DEFAULT_DISK_PATH = '/'

TOOL_DESCRIPTION = 'System Monitoring Tool'
LOG_SUCCESS_MESSAGE = 'Metric logged successfully'
JSON_OUTPUT_INDENT = 2

COMMAND_DISK = 'disk'
COMMAND_PROCESS = 'process'
COMMAND_LOG = 'log'
COMMAND_HISTORY = 'history'

DF_COMMAND = 'df'
DF_HUMAN_READABLE_FLAG = '-h'

PGREP_COMMAND = 'pgrep'
PGREP_FULL_COMMAND_MATCH_FLAG = '-f'

PS_COMMAND = 'ps'
PS_FORMAT_FLAG = '-o'
PS_PROCESS_COLUMNS = 'user,pid,pcpu,pmem,command'
PS_PID_SELECTION_FLAG = '-p'
PS_MAX_SPLIT = 4


# ---------------------------------------------------------------------------
# Parsing / formatting helpers
# ---------------------------------------------------------------------------

def _parse_df_output(output: str) -> Dict:
    """Turn the two-line ``df -h`` output into a header -> value mapping."""
    lines = output.split('\n')
    headers = lines[0].split()
    values = lines[1].split()
    return dict(zip(headers, values))


def _parse_ps_output(output: str) -> List[Dict]:
    """Turn ``ps`` output rows into a list of per-process dictionaries."""
    processes = []
    lines = output.split('\n')[1:]
    for line in lines:
        if line.strip():
            parts = line.split(maxsplit=PS_MAX_SPLIT)
            processes.append({
                'user': parts[0],
                'pid': parts[1],
                'cpu': parts[2],
                'mem': parts[3],
                'command': parts[4] if len(parts) > PS_MAX_SPLIT else '',
            })
    return processes


def _print_json(data: object) -> None:
    """Pretty-print *data* as JSON to stdout."""
    print(json.dumps(data, indent=JSON_OUTPUT_INDENT))


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------

class SystemMonitor:
    """Collects system metrics and persists a JSON metric history."""

    def __init__(self):
        self.history_file = HISTORY_FILE_PATH
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

    def check_disk_usage(self, path: str = DEFAULT_DISK_PATH) -> Dict:
        try:
            output = subprocess.check_output(
                [DF_COMMAND, DF_HUMAN_READABLE_FLAG, path]
            ).decode()
            return _parse_df_output(output)
        except subprocess.CalledProcessError as e:
            return {'error': str(e)}

    def check_process(self, process_name: str) -> Dict:
        try:
            pids = self._find_process_pids(process_name)
            if not pids:
                return {'processes': []}
            return {'processes': self._collect_process_info(pids)}
        except subprocess.CalledProcessError:
            return {'processes': []}
        except Exception as e:
            return {'error': str(e)}

    def _find_process_pids(self, process_name: str) -> List[str]:
        """Return the PIDs of every process matching *process_name*."""
        pgrep_cmd = [PGREP_COMMAND, PGREP_FULL_COMMAND_MATCH_FLAG, process_name]
        pgrep_result = subprocess.run(
            pgrep_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        return pgrep_result.stdout.split()

    def _collect_process_info(self, pids: List[str]) -> List[Dict]:
        """Return per-process details for *pids* via ``ps``."""
        ps_cmd = [
            PS_COMMAND,
            PS_FORMAT_FLAG,
            PS_PROCESS_COLUMNS,
            PS_PID_SELECTION_FLAG,
            ','.join(pids),
        ]
        ps_result = subprocess.run(
            ps_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        return _parse_ps_output(ps_result.stdout)

    def log_metric(self, metric_name: str, value: float):
        entry = {
            'timestamp': datetime.now().isoformat(),
            'value': value,
        }
        self.history.setdefault(metric_name, []).append(entry)
        self._save_history()

    def get_metric_history(self, metric_name: str) -> List[Dict]:
        return self.history.get(metric_name, [])


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=TOOL_DESCRIPTION)
    subparsers = parser.add_subparsers(dest='command', required=True)

    disk_parser = subparsers.add_parser(COMMAND_DISK)
    disk_parser.add_argument(
        '--path', default=DEFAULT_DISK_PATH, help='Path to check disk usage'
    )

    process_parser = subparsers.add_parser(COMMAND_PROCESS)
    process_parser.add_argument('name', help='Process name to check')

    log_parser = subparsers.add_parser(COMMAND_LOG)
    log_parser.add_argument('metric', help='Metric name to log')
    log_parser.add_argument('value', type=float, help='Metric value')

    history_parser = subparsers.add_parser(COMMAND_HISTORY)
    history_parser.add_argument('metric', help='Metric name to view history')

    return parser


def _handle_disk_command(monitor: SystemMonitor, args: argparse.Namespace) -> None:
    _print_json(monitor.check_disk_usage(args.path))


def _handle_process_command(monitor: SystemMonitor, args: argparse.Namespace) -> None:
    _print_json(monitor.check_process(args.name))


def _handle_log_command(monitor: SystemMonitor, args: argparse.Namespace) -> None:
    monitor.log_metric(args.metric, args.value)
    print(LOG_SUCCESS_MESSAGE)


def _handle_history_command(monitor: SystemMonitor, args: argparse.Namespace) -> None:
    _print_json(monitor.get_metric_history(args.metric))


_COMMAND_HANDLERS = {
    COMMAND_DISK: _handle_disk_command,
    COMMAND_PROCESS: _handle_process_command,
    COMMAND_LOG: _handle_log_command,
    COMMAND_HISTORY: _handle_history_command,
}


def main():
    args = _build_parser().parse_args()
    monitor = SystemMonitor()
    _COMMAND_HANDLERS[args.command](monitor, args)


if __name__ == '__main__':
    main()
