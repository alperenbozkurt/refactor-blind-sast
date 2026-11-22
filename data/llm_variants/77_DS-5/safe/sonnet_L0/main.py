import subprocess
import argparse
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional

HISTORY_FILE = 'monitor_history.json'


class SystemMonitor:

    def __init__(self):
        self.history_file = HISTORY_FILE
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
    def _parse_ps_line(line: str) -> Dict:
        parts = line.split(maxsplit=4)
        return {
            'user': parts[0],
            'pid': parts[1],
            'cpu': parts[2],
            'mem': parts[3],
            'command': parts[4] if len(parts) > 4 else '',
        }

    def check_process(self, process_name: str) -> Dict:
        try:
            pgrep_result = self._run_command(['pgrep', '-f', process_name], check=False)
            if not pgrep_result.stdout.strip():
                return {'processes': []}

            pids = pgrep_result.stdout.split()
            ps_cmd = ['ps', '-o', 'user,pid,pcpu,pmem,command', '-p', ','.join(pids)]
            ps_result = self._run_command(ps_cmd, check=True)

            lines = ps_result.stdout.split('\n')[1:]
            processes = [self._parse_ps_line(line) for line in lines if line.strip()]
            return {'processes': processes}
        except subprocess.CalledProcessError:
            return {'processes': []}
        except Exception as e:
            return {'error': str(e)}

    def log_metric(self, metric_name: str, value: float):
        timestamp = datetime.now().isoformat()
        self.history.setdefault(metric_name, [])
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


def _handle_log(monitor: SystemMonitor, args) -> None:
    monitor.log_metric(args.metric, args.value)
    print('Metric logged successfully')


def main():
    args = _build_parser().parse_args()
    monitor = SystemMonitor()

    handlers = {
        'disk': lambda: _print_json(monitor.check_disk_usage(args.path)),
        'process': lambda: _print_json(monitor.check_process(args.name)),
        'log': lambda: _handle_log(monitor, args),
        'history': lambda: _print_json(monitor.get_metric_history(args.metric)),
    }
    handler = handlers.get(args.command)
    if handler is not None:
        handler()


if __name__ == '__main__':
    main()
