"""Generate the LLM refactorings (prompts L0/L1/L2) of every base program.

Usage: python -I src/refactor_llm.py --model sonnet|kimi|fake [--prompts L0,L1,L2] [--limit N]
                                      [--workers 4] [--budget 20] [--max-tokens 8000] [--retry-truncated]
Writes data/llm_variants/<id>/<vuln|safe>/<model>_<prompt>/main.py and one log line per call to
results/refactor/<model>.jsonl (prompt, settings, raw answer, token usage, cost, parse status).
Answers whose code block does not parse, or that hit the token limit, are logged but not written as
variants. Already finished calls are skipped, so the command can simply be re-run.
--retry-truncated moves the log lines of answers that hit the token limit to
results/refactor/<model>_truncated.jsonl, so that they are asked again (use with a larger --max-tokens).
"""
import ast
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from llm_backend import EXP, Client  # noqa: E402
from prompts import REFACTOR, REFACTOR_TEMPLATE  # noqa: E402
from runner import run_jobs  # noqa: E402

DATA = EXP / "data" / "pysastbench"
OUT = EXP / "data" / "llm_variants"


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def extract_code(text):
    blocks = re.findall(r"```(?:python|py)?[ \t]*\n(.*?)```", text, re.S)
    if blocks:
        return max(blocks, key=len)
    return text if text.lstrip().startswith(("import ", "from ", "def ", "class ", "#", '"""')) else None


def main():
    alias = arg("--model")
    prompts = arg("--prompts", "L0,L1,L2").split(",")
    max_tokens = int(arg("--max-tokens", 8000))
    log = EXP / "results" / "refactor" / f"{alias}.jsonl"
    if "--retry-truncated" in sys.argv and log.exists():
        rows = [l for l in log.read_text().splitlines() if l.strip()]
        cut = [l for l in rows if json.loads(l)["truncated"]]
        with (log.parent / f"{alias}_truncated.jsonl").open("a") as fh:
            fh.write("".join(l + "\n" for l in cut))
        log.write_text("".join(l + "\n" for l in rows if l not in cut))
        print(f"moved {len(cut)} truncated answers aside; they will be asked again with max_tokens={max_tokens}")
    client = Client(alias)
    jobs = []
    for d in sorted(DATA.iterdir()):
        for kind in ("vuln", "safe"):
            for p in prompts:
                jobs.append(dict(key=f"{d.name}/{kind}/{p}", id=d.name, kind=kind, prompt=p))
    if arg("--limit"):
        jobs = jobs[: int(arg("--limit"))]

    def work(job):
        src = (DATA / job["id"] / f"{job['kind']}.py").read_text()
        prompt = REFACTOR_TEMPLATE.format(instruction=REFACTOR[job["prompt"]], code=src.rstrip())
        r = client.ask(prompt, max_tokens=max_tokens)
        code = extract_code(r["text"])
        truncated = r["stop"] in ("max_tokens", "length")
        try:
            parse_ok = code is not None and not truncated and bool(ast.parse(code))
        except SyntaxError:
            parse_ok = False
        variant = f"{alias}_{job['prompt']}"
        if parse_ok:
            vdir = OUT / job["id"] / job["kind"] / variant
            vdir.mkdir(parents=True, exist_ok=True)
            (vdir / "main.py").write_text(code if code.endswith("\n") else code + "\n")
        row = dict(id=job["id"], kind=job["kind"], prompt=job["prompt"], variant=variant, model=alias,
                   settings=client.settings(), max_tokens=max_tokens, stop=r["stop"], truncated=truncated, parse_ok=parse_ok,
                   usage=r["usage"], latency_ms=r["latency_ms"], answer=r["text"], reasoning=r.get("reasoning"))
        return row, client.cost(r["usage"])

    run_jobs(jobs, work, log, workers=int(arg("--workers", 4)),
             budget_usd=float(arg("--budget")) if arg("--budget") else None, label=f"refactor {alias}")


if __name__ == "__main__":
    main()
