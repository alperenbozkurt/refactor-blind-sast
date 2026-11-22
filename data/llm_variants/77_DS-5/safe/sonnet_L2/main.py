import subprocess
import argparse
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional

DEFAULT_HISTORY_FILE = 'monitor_history.json'
DEFAULT_DISK_PATH = '/'
JSON_INDENT = 2

DF_COMMAND = ['df', '-h']
PGREP_COMMAND = ['pgrep', '-f']
PS_COMMAND_PREFIX = ['ps', '-o', 'user,pid,pcpu,pmem,command', '-p']
PS_MAX_SPLIT = 4

CMD_DISK = 'disk'
CMD_PROCESS = 'process'
CMD_LOG = 'log'
CMD_HISTORY = 'history'

LOG_SUCCESS_MESSAGE = 'Metric logged successfully'


def _run_text_command(cmd: List[str], check: bool) -> subprocess.CompletedProcess:
    """Run a command capturing stdout/stderr as text."""
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=check,
    )


def _parse_ps_line(line: str) -> Dict:
    """Convert a single line of `ps` output into a process dictionary."""
    parts = line.split(maxsplit=PS_MAX_SPLIT)
    return {
        'user': parts[0],
        'pid': parts[1],
        'cpu': parts[2],
        'mem': parts[3],
        'command': parts[4] if len(parts) > 4 else '',
    }


def _parse_ps_output(stdout: str) -> List[Dict]:
    """Parse full `ps` output (skipping the header) into process dictionaries."""
    lines = stdout.split('\n')[1:]
    return [_parse_ps_line(line) for line in lines if line.strip()]


def _parse_df_output(output: str) -> Dict:
    """Parse `df -h` output into a header->value mapping."""
    lines = output.split('\n')
    headers = lines[0].split()
    values = lines[1].split()
    return dict(zip(headers, values))


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

    def check_disk_usage(self, path: str = DEFAULT_DISK_PATH) -> Dict:
        try:
            output = subprocess.check_output(DF_COMMAND + [path]).decode()
            return _parse_df_output(output)
        except subprocess.CalledProcessError as e:
            return {'error': str(e)}

    def check_process(self, process_name: str) -> Dict:
        try:
            pgrep_result = _run_text_command(PGREP_COMMAND + [process_name], check=False)
            if not pgrep_result.stdout.strip():
                return {'processes': []}
            pids = pgrep_result.stdout.split()
            ps_result = _run_text_command(PS_COMMAND_PREFIX + [','.join(pids)], check=True)
            return {'processes': _parse_ps_output(ps_result.stdout)}
        except subprocess.CalledProcessError:
            return {'processes': []}
        except Exception as e:
            return {'error': str(e)}

    def log_metric(self, metric_name: str, value: float):
        timestamp = datetime.now().isoformat()
        if metric_name not in self.history:
            self.history[metric_name] = []
        self.history[metric_name].append({'timestamp': timestamp, 'value': value})
        self._save_history()

    def get_metric_history(self, metric_name: str) -> List[Dict]:
        return self.history.get(metric_name, [])


def _print_json(data) -> None:
    print(json.dumps(data, indent=JSON_INDENT))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='System Monitoring Tool')
    subparsers = parser.add_subparsers(dest='command', required=True)

    disk_parser = subparsers.add_parser(CMD_DISK)
    disk_parser.add_argument('--path', default=DEFAULT_DISK_PATH, help='Path to check disk usage')

    process_parser = subparsers.add_parser(CMD_PROCESS)
    process_parser.add_argument('name', help='Process name to check')

    log_parser = subparsers.add_parser(CMD_LOG)
    log_parser.add_argument('metric', help='Metric name to log')
    log_parser.add_argument('value', type=float, help='Metric value')

    history_parser = subparsers.add_parser(CMD_HISTORY)
    history_parser.add_argument('metric', help='Metric name to view history')

    return parser


def _handle_disk(monitor: SystemMonitor, args: argparse.Namespace) -> None:
    _print_json(monitor.check_disk_usage(args.path))


def _handle_process(monitor: SystemMonitor, args: argparse.Namespace) -> None:
    _print_json(monitor.check_process(args.name))


def _handle_log(monitor: SystemMonitor, args: argparse.Namespace) -> None:
    monitor.log_metric(args.metric, args.value)
    print(LOG_SUCCESS_MESSAGE)


def _handle_history(monitor: SystemMonitor, args: argparse.Namespace) -> None:
    _print_json(monitor.get_metric_history(args.metric))


COMMAND_HANDLERS = {
    CMD_DISK: _handle_disk,
    CMD_PROCESS: _handle_process,
    CMD_LOG: _handle_log,
    CMD_HISTORY: _handle_history,
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
