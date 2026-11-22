"""Lines of a Python file that can run a command through a shell (used to check CodeQL's CWE-77 alarms)."""
import ast
from pathlib import Path

ALWAYS_SHELL = {"system", "popen", "getoutput", "getstatusoutput", "create_subprocess_shell"}
SUBPROCESS = {"run", "call", "check_call", "check_output", "Popen"}


def shell_call(node):
    name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", None)
    if name in ALWAYS_SHELL:
        return True
    if name not in SUBPROCESS:
        return False
    for kw in node.keywords:
        if kw.arg == "shell":
            return not (isinstance(kw.value, ast.Constant) and not kw.value.value)
    return False


def shell_sink_lines(path):
    """Every physical line covered by a call that goes through a shell."""
    lines = set()
    for n in ast.walk(ast.parse(Path(path).read_text())):
        if isinstance(n, ast.Call) and shell_call(n):
            lines.update(range(n.lineno, (n.end_lineno or n.lineno) + 1))
    return lines
