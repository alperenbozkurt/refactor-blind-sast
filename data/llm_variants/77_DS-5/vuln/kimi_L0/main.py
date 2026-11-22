import argparse
import json
import subprocess
import sys
from datetime import datetime
from typing import Dict, List, Optional


class SystemMonitor:
    """Collects system metrics and persists them to a JSON history file."""

    def __init__(self):
        self.history_file = "monitor_history.json"
        self.history = self._load_history()

    def _load_history(self) -> Dict:
        try:
            with open(self.history_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_history(self):
        with open(self.history_file, "w") as f:
            json.dump(self.history, f)

    def check_disk_usage(self, path: str = "/") -> Dict:
        try:
            output = subprocess.check_output(["df", "-h", path]).decode()
            lines = output.splitlines()
            headers = lines[0].split()
            values = lines[1].split()
            return dict(zip(headers, values))
        except subprocess.CalledProcessError as e:
            return {"error": str(e)}

    def check_process(self, process_name: str) -> Dict:
        command = f"ps aux | grep '{process_name}' | grep -v grep"
        try:
            output = subprocess.check_output(command, shell=True).decode()
            processes = [
                self._parse_process_line(line)
                for line in output.splitlines()
                if line.strip()
            ]
            return {"processes": processes}
        except subprocess.CalledProcessError:
            return {"processes": []}

    @staticmethod
    def _parse_process_line(line: str) -> Dict:
        parts = line.split()
        return {
            "user": parts[0],
            "pid": parts[1],
            "cpu": parts[2],
            "mem": parts[3],
            "command": " ".join(parts[10:]),
        }

    def log_metric(self, metric_name: str, value: float):
        entry = {"timestamp": datetime.now().isoformat(), "value": value}
        self.history.setdefault(metric_name, []).append(entry)
        self._save_history()

    def get_metric_history(self, metric_name: str) -> List[Dict]:
        return self.history.get(metric_name, [])


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="System Monitoring Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    disk_parser = subparsers.add_parser("disk")
    disk_parser.add_argument("--path", default="/", help="Path to check disk usage")

    process_parser = subparsers.add_parser("process")
    process_parser.add_argument("name", help="Process name to check")

    log_parser = subparsers.add_parser("log")
    log_parser.add_argument("metric", help="Metric name to log")
    log_parser.add_argument("value", type=float, help="Metric value")

    history_parser = subparsers.add_parser("history")
    history_parser.add_argument("metric", help="Metric name to view history")

    return parser


def main():
    args = _build_parser().parse_args()
    monitor = SystemMonitor()

    if args.command == "log":
        monitor.log_metric(args.metric, args.value)
        print("Metric logged successfully")
        return

    actions = {
        "disk": lambda: monitor.check_disk_usage(args.path),
        "process": lambda: monitor.check_process(args.name),
        "history": lambda: monitor.get_metric_history(args.metric),
    }
    print(json.dumps(actions[args.command](), indent=2))


if __name__ == "__main__":
    main()
