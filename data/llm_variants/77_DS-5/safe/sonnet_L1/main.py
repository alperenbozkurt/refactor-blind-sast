import subprocess
import argparse
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional

HISTORY_FILE = 'monitor_history.json'
PS_FIELDS = 'user,pid,pcpu,pmem,command'
PS_COLUMN_NAMES = ('user', 'pid', 'cpu', 'mem')


class SystemMonitor:

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
    # Disk usage
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

    # ------------------------------------------------------------------
    # Process inspection
    # ------------------------------------------------------------------
    @staticmethod
    def _run_command(cmd: List[str], check: bool) -> subprocess.CompletedProcess:
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=check,
        )

    @staticmethod
    def _parse_ps_output(output: str) -> List[Dict]:
        processes = []
        # First line is the header row.
        for line in output.split('\n')[1:]:
            if not line.strip():
                continue
            parts = line.split(maxsplit=4)
            process = dict(zip(PS_COLUMN_NAMES, parts[:4]))
            process['command'] = parts[4] if len(parts) > 4 else ''
            processes.append(process)
        return processes

    def check_process(self, process_name: str) -> Dict:
        try:
            pgrep_result = self._run_command(['pgrep', '-f', process_name], check=False)
            if not pgrep_result.stdout.strip():
                return {'processes': []}

            pids = pgrep_result.stdout.split()
            ps_cmd = ['ps', '-o', PS_FIELDS, '-p', ','.join(pids)]
            ps_result = self._run_command(ps_cmd, check=True)
            return {'processes': self._parse_ps_output(ps_result.stdout)}
        except subprocess.CalledProcessError:
            return {'processes': []}
        except Exception as e:
            return {'error': str(e)}

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------
    def log_metric(self, metric_name: str, value: float):
        timestamp = datetime.now().isoformat()
        if metric_name not in self.history:
            self.history[metric_name] = []
        self.history[metric_name].append({'timestamp': timestamp, 'value': value})
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


def _print_json(data) -> None:
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
