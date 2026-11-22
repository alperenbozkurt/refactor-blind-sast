"""System monitoring tool with persistent metric history."""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from typing import Dict, List, Optional


class SystemMonitor:
    """Check disk usage and processes, and log metrics to a JSON file."""

    def __init__(self):
        self.history_file = 'monitor_history.json'
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

    def check_disk_usage(self, path: str = '/') -> Dict:
        try:
            output = subprocess.check_output(['df', '-h', path]).decode()
            lines = output.split('\n')
            headers = lines[0].split()
            values = lines[1].split()
            return dict(zip(headers, values))
        except subprocess.CalledProcessError as e:
            return {'error': str(e)}

    def check_process(self, process_name: str) -> Dict:
        try:
            pgrep_result = self._run_command(['pgrep', '-f', process_name])
            if not pgrep_result.stdout.strip():
                return {'processes': []}
            pids = pgrep_result.stdout.split()
            ps_cmd = ['ps', '-o', 'user,pid,pcpu,pmem,command', '-p', ','.join(pids)]
            ps_result = self._run_command(ps_cmd, check=True)
            processes = [
                self._parse_process_line(line)
                for line in ps_result.stdout.split('\n')[1:]
                if line.strip()
            ]
            return {'processes': processes}
        except subprocess.CalledProcessError:
            return {'processes': []}
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def _run_command(cmd: List[str], check: bool = False) -> subprocess.CompletedProcess:
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=check,
        )

    @staticmethod
    def _parse_process_line(line: str) -> Dict:
        parts = line.split(maxsplit=4)
        return {
            'user': parts[0],
            'pid': parts[1],
            'cpu': parts[2],
            'mem': parts[3],
            'command': parts[4] if len(parts) > 4 else '',
        }

    def log_metric(self, metric_name: str, value: float):
        timestamp = datetime.now().isoformat()
        entry = {'timestamp': timestamp, 'value': value}
        self.history.setdefault(metric_name, []).append(entry)
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


def main():
    args = _build_parser().parse_args()
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
