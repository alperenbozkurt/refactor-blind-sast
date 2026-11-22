"""Command-line system monitoring tool.

Provides disk usage and process inspection commands, along with a small
JSON-backed store for logging named metrics and reviewing their history.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from typing import Dict, List, Optional


class SystemMonitor:
    """Collect system metrics and maintain a JSON-backed metric history."""

    def __init__(self):
        self.history_file = 'monitor_history.json'
        self.history = self._load_history()

    def _load_history(self) -> Dict:
        """Load metric history from disk, or return an empty mapping."""
        try:
            with open(self.history_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_history(self):
        """Write the current metric history to disk."""
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f)

    def check_disk_usage(self, path: str = '/') -> Dict:
        """Return disk usage for *path* as reported by ``df -h``."""
        try:
            output = subprocess.check_output(['df', '-h', path]).decode()
            lines = output.split('\n')
            headers = lines[0].split()
            values = lines[1].split()
            return dict(zip(headers, values))
        except subprocess.CalledProcessError as e:
            return {'error': str(e)}

    def check_process(self, process_name: str) -> Dict:
        """Return details for processes matching *process_name*."""
        try:
            pids = self._find_matching_pids(process_name)
            if not pids:
                return {'processes': []}
            return {'processes': self._collect_process_info(pids)}
        except subprocess.CalledProcessError:
            return {'processes': []}
        except Exception as e:
            return {'error': str(e)}

    def _find_matching_pids(self, process_name: str) -> List[str]:
        """Return PIDs whose full command line matches *process_name*."""
        pgrep_cmd = ['pgrep', '-f', process_name]
        pgrep_result = subprocess.run(
            pgrep_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        return pgrep_result.stdout.split()

    def _collect_process_info(self, pids: List[str]) -> List[Dict]:
        """Return user/pid/cpu/mem/command info for each PID in *pids*."""
        ps_cmd = ['ps', '-o', 'user,pid,pcpu,pmem,command', '-p', ','.join(pids)]
        ps_result = subprocess.run(
            ps_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        processes = []
        for line in ps_result.stdout.split('\n')[1:]:
            if line.strip():
                processes.append(self._parse_process_line(line))
        return processes

    @staticmethod
    def _parse_process_line(line: str) -> Dict:
        """Parse a single line of ``ps`` output into a process info dict."""
        parts = line.split(maxsplit=4)
        return {
            'user': parts[0],
            'pid': parts[1],
            'cpu': parts[2],
            'mem': parts[3],
            'command': parts[4] if len(parts) > 4 else '',
        }

    def log_metric(self, metric_name: str, value: float):
        """Record *value* under *metric_name* with the current timestamp."""
        entry = {'timestamp': datetime.now().isoformat(), 'value': value}
        self.history.setdefault(metric_name, []).append(entry)
        self._save_history()

    def get_metric_history(self, metric_name: str) -> List[Dict]:
        """Return all recorded entries for *metric_name*."""
        return self.history.get(metric_name, [])


def _build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the monitoring CLI."""
    parser = argparse.ArgumentParser(description='System Monitoring Tool')
    subparsers = parser.add_subparsers(dest='command', required=True)

    disk_parser = subparsers.add_parser('disk')
    disk_parser.add_argument('--path', default='/', help='Path to check disk usage')

    process_parser = subparsers.add_parser('process')
    process_parser.add_argument('name', help='Process name to check')

    log_parser = subparsers.add_parser('log')
    log_parser.add_argument('metric', help='Metric name to log')
    log_parser.add_argument('value', type=float, help='Metric value')

    history_parser = subparsers.add_parser('history')
    history_parser.add_argument('metric', help='Metric name to view history')

    return parser


def _print_json(data):
    """Pretty-print *data* as JSON to stdout."""
    print(json.dumps(data, indent=2))


def main():
    parser = _build_parser()
    args = parser.parse_args()
    monitor = SystemMonitor()

    if args.command == 'disk':
        _print_json(monitor.check_disk_usage(args.path))
    elif args.command == 'process':
        _print_json(monitor.check_process(args.name))
    elif args.command == 'log':
        monitor.log_metric(args.metric, args.value)
        print('Metric logged successfully')
    elif args.command == 'history':
        _print_json(monitor.get_metric_history(args.metric))


if __name__ == '__main__':
    main()
