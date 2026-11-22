"""Thin wrappers around Bandit and Semgrep that return findings in one common format.

Semgrep runs from the repository root with the pinned rule files in rules/ (see rules/SHA256SUMS),
so rule ids look like ``rules.python.lang.security...`` and contain no machine-specific paths.
"""
import ast
import json
import re
import subprocess
import sys
import time
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent

SEMGREP_CONFIGS = {
    "semgrep-registry": ["semgrep_p_python.yaml", "semgrep_p_security-audit.yaml"],
    "semgrep-bandit": ["semgrep_p_bandit.yaml"],
}
TOOLS = ["bandit"] + list(SEMGREP_CONFIGS)


def import_lines(path):
    """Line numbers of import statements; findings there flag a module, not its use."""
    try:
        tree = ast.parse(Path(path).read_text())
    except SyntaxError:
        return set()
    lines = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            lines.update(range(n.lineno, (n.end_lineno or n.lineno) + 1))
    return lines


def cwe_ids(value):
    if value is None:
        return []
    if isinstance(value, dict):
        return [int(value.get("id"))] if value.get("id") else []
    if isinstance(value, (list, tuple)):
        return sorted({i for v in value for i in cwe_ids(v)})
    return [int(m) for m in re.findall(r"CWE-(\d+)", str(value))]


def _rel(path):
    p = Path(path).resolve()
    try:
        return str(p.relative_to(EXP))
    except ValueError:
        return str(p)


def run_bandit(root):
    t0 = time.time()
    out = subprocess.run([str(BIN / "bandit"), "-r", _rel(root), "-f", "json", "-q"],
                         capture_output=True, text=True, cwd=EXP)
    data = json.loads(out.stdout)
    findings = [dict(tool="bandit", file=str(EXP / r["filename"]), line=r["line_number"],
                     lines=r.get("line_range") or [r["line_number"]], rule=r["test_id"] + ":" + r["test_name"],
                     cwes=cwe_ids(r.get("issue_cwe")), severity=r["issue_severity"], confidence=r["issue_confidence"])
                for r in data["results"]]
    return data, findings, time.time() - t0


def run_semgrep(root, name):
    t0 = time.time()
    cfg = [a for f in SEMGREP_CONFIGS[name] for a in ("--config", f"rules/{f}")]
    out = subprocess.run([str(BIN / "semgrep"), "scan", *cfg, "--json", "--metrics=off", "--disable-version-check",
                          "--no-git-ignore", "-q", _rel(root)], capture_output=True, text=True, cwd=EXP)
    data = json.loads(out.stdout)
    findings = [dict(tool=name, file=str(EXP / r["path"]), line=r["start"]["line"],
                     lines=list(range(r["start"]["line"], r["end"]["line"] + 1)), rule=r["check_id"],
                     cwes=cwe_ids(r["extra"].get("metadata", {}).get("cwe")),
                     severity=r["extra"].get("severity"), confidence=r["extra"].get("metadata", {}).get("confidence"))
                for r in data["results"]]
    return data, findings, time.time() - t0
