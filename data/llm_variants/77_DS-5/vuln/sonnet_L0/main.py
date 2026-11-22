import subprocess
import argparse
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional

DEFAULT_HISTORY_FILE = 'monitor_history.json'


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

    def check_disk_usage(self, path: str='/') -> Dict:
        try:
            output = subprocess.check_output(['df', '-h', path]).decode()
            lines = output.split('\n')
            headers = lines[0].split()
            values = lines[1].split()
            return dict(zip(headers, values))
        except subprocess.CalledProcessError as e:
            return {'error': str(e)}

    @staticmethod
    def _parse_process_line(line: str) -> Dict:
        parts = line.split()
        return {
            'user': parts[0],
            'pid': parts[1],
            'cpu': parts[2],
            'mem': parts[3],
            'command': ' '.join(parts[10:]),
        }

    def check_process(self, process_name: str) -> Dict:
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

    def log_metric(self, metric_name: str, value: float):
        timestamp = datetime.now().isoformat()
        self.history.setdefault(metric_name, []).append(
            {'timestamp': timestamp, 'value': value}
        )
        self._save_history()

    def get_metric_history(self, metric_name: str) -> List[Dict]:
        return self.history.get(metric_name, [])


def _build_parser() -> argparse.ArgumentParser:
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
    print(json.dumps(data, indent=2))


def _handle_disk(monitor: SystemMonitor, args):
    _print_json(monitor.check_disk_usage(args.path))


def _handle_process(monitor: SystemMonitor, args):
    _print_json(monitor.check_process(args.name))


def _handle_log(monitor: SystemMonitor, args):
    monitor.log_metric(args.metric, args.value)
    print('Metric logged successfully')


def _handle_history(monitor: SystemMonitor, args):
    _print_json(monitor.get_metric_history(args.metric))


_HANDLERS = {
    'disk': _handle_disk,
    'process': _handle_process,
    'log': _handle_log,
    'history': _handle_history,
}


def main():
    args = _build_parser().parse_args()
    monitor = SystemMonitor()
    handler = _HANDLERS.get(args.command)
    if handler is not None:
        handler(monitor, args)


if __name__ == '__main__':
    main()
