"""Simple system monitoring tool.

Provides disk-usage and process checks along with a JSON-backed history
of logged metric values, exposed through a command-line interface.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from typing import Dict, List, Optional


class SystemMonitor:
    """Collect system metrics and persist a history of logged values."""

    def __init__(self):
        self.history_file = 'monitor_history.json'
        self.history = self._load_history()

    def _load_history(self) -> Dict:
        """Load the metric history from disk.

        Returns an empty mapping if the history file does not exist or
        cannot be decoded.
        """
        try:
            with open(self.history_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_history(self):
        """Persist the current metric history to disk."""
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f)

    def check_disk_usage(self, path: str = '/') -> Dict:
        """Return disk-usage information for ``path`` as reported by ``df -h``."""
        try:
            output = subprocess.check_output(['df', '-h', path]).decode()
            lines = output.split('\n')
            headers = lines[0].split()
            values = lines[1].split()
            return dict(zip(headers, values))
        except subprocess.CalledProcessError as error:
            return {'error': str(error)}

    def check_process(self, process_name: str) -> Dict:
        """Return a list of running processes matching ``process_name``."""
        # Column positions in the output of `ps aux`.
        USER_COL, PID_COL, CPU_COL, MEM_COL = 0, 1, 2, 3
        COMMAND_START_COL = 10

        command = f"ps aux | grep '{process_name}' | grep -v grep"
        try:
            output = subprocess.check_output(command, shell=True).decode()
        except subprocess.CalledProcessError:
            return {'processes': []}

        processes = []
        for line in output.split('\n'):
            if not line.strip():
                continue
            parts = line.split()
            processes.append({
                'user': parts[USER_COL],
                'pid': parts[PID_COL],
                'cpu': parts[CPU_COL],
                'mem': parts[MEM_COL],
                'command': ' '.join(parts[COMMAND_START_COL:]),
            })
        return {'processes': processes}

    def log_metric(self, metric_name: str, value: float):
        """Append ``value`` to the history of ``metric_name`` and save it."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'value': value,
        }
        self.history.setdefault(metric_name, []).append(entry)
        self._save_history()

    def get_metric_history(self, metric_name: str) -> List[Dict]:
        """Return the recorded history for ``metric_name``."""
        return self.history.get(metric_name, [])


def main():
    """Parse command-line arguments and run the requested monitoring action."""
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

    args = parser.parse_args()
    monitor = SystemMonitor()

    if args.command == 'disk':
        result = monitor.check_disk_usage(args.path)
        print(json.dumps(result, indent=2))
    elif args.command == 'process':
        result = monitor.check_process(args.name)
        print(json.dumps(result, indent=2))
    elif args.command == 'log':
        monitor.log_metric(args.metric, args.value)
        print('Metric logged successfully')
    elif args.command == 'history':
        history = monitor.get_metric_history(args.metric)
        print(json.dumps(history, indent=2))


if __name__ == '__main__':
    main()
