import subprocess
import argparse
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional

HISTORY_FILE = 'monitor_history.json'
JSON_INDENT = 2


class SystemMonitor:
    """Collects system information and keeps a persistent history of metrics."""

    def __init__(self):
        self.history_file = HISTORY_FILE
        self.history = self._load_history()

    # ------------------------------------------------------------------
    # History persistence
    # ------------------------------------------------------------------
    def _load_history(self) -> Dict:
        try:
            with open(self.history_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_history(self):
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f)

    # ------------------------------------------------------------------
    # System checks
    # ------------------------------------------------------------------
    def check_disk_usage(self, path: str='/') -> Dict:
        try:
            output = subprocess.check_output(['df', '-h', path]).decode()
            lines = output.split('\n')
            headers = lines[0].split()
            values = lines[1].split()
            return dict(zip(headers, values))
        except subprocess.CalledProcessError as e:
            return {'error': str(e)}

    def check_process(self, process_name: str) -> Dict:
        # NOTE: the command string is intentionally built exactly as before
        # (shell invocation with the interpolated name) to preserve behaviour.
        command = f"ps aux | grep '{process_name}' | grep -v grep"
        try:
            output = subprocess.check_output(command, shell=True).decode()
        except subprocess.CalledProcessError:
            return {'processes': []}

        processes = [
            self._parse_process_line(line)
            for line in output.split('\n')
            if line.strip()
        ]
        return {'processes': processes}

    @staticmethod
    def _parse_process_line(line: str) -> Dict:
        """Convert a single `ps aux` output line into a dictionary."""
        parts = line.split()
        return {
            'user': parts[0],
            'pid': parts[1],
            'cpu': parts[2],
            'mem': parts[3],
            'command': ' '.join(parts[10:]),
        }

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------
    def log_metric(self, metric_name: str, value: float):
        timestamp = datetime.now().isoformat()
        entries = self.history.setdefault(metric_name, [])
        entries.append({'timestamp': timestamp, 'value': value})
        self._save_history()

    def get_metric_history(self, metric_name: str) -> List[Dict]:
        return self.history.get(metric_name, [])


def _print_json(data) -> None:
    print(json.dumps(data, indent=JSON_INDENT))


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
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


def _handle_disk(monitor: SystemMonitor, args) -> None:
    _print_json(monitor.check_disk_usage(args.path))


def _handle_process(monitor: SystemMonitor, args) -> None:
    _print_json(monitor.check_process(args.name))


def _handle_log(monitor: SystemMonitor, args) -> None:
    monitor.log_metric(args.metric, args.value)
    print('Metric logged successfully')


def _handle_history(monitor: SystemMonitor, args) -> None:
    _print_json(monitor.get_metric_history(args.metric))


COMMAND_HANDLERS = {
    'disk': _handle_disk,
    'process': _handle_process,
    'log': _handle_log,
    'history': _handle_history,
}


def main():
    args = build_parser().parse_args()
    monitor = SystemMonitor()
    handler = COMMAND_HANDLERS.get(args.command)
    if handler is not None:
        handler(monitor, args)


if __name__ == '__main__':
    main()
