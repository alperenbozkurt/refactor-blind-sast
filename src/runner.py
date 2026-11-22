"""Run independent LLM jobs in parallel, append one JSON line per finished job, resume after a crash
and stop when a cost budget is reached."""
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


def run_jobs(jobs, work, out_path, workers=4, budget_usd=None, label=""):
    """``jobs``: list of dicts with a unique "key"; ``work(job) -> (row_dict, cost_usd)``."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    spent = 0.0
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                done.add(r["key"])
                spent += r.get("cost_usd") or 0.0
    todo = [j for j in jobs if j["key"] not in done]
    print(f"{label}: {len(done)} done, {len(todo)} to do, spent so far ${spent:.2f}", flush=True)
    if not todo:
        return
    lock, stop = threading.Lock(), threading.Event()
    state = dict(spent=spent, n=0, errors=0, t0=time.time())

    def one(job):
        if stop.is_set():
            return
        try:
            row, cost = work(job)
        except Exception as e:  # keep going; the job is retried on the next run
            with lock:
                state["errors"] += 1
                print(f"   ERROR {job['key']}: {type(e).__name__}: {str(e)[:300]}", file=sys.stderr, flush=True)
            return
        with lock:
            row["key"], row["cost_usd"] = job["key"], round(cost, 6)
            with out_path.open("a") as fh:
                fh.write(json.dumps(row) + "\n")
            state["spent"] += cost
            state["n"] += 1
            if state["n"] % 20 == 0 or state["n"] == len(todo):
                rate = (time.time() - state["t0"]) / state["n"]
                left = (len(todo) - state["n"]) * rate  # rate already reflects the parallel throughput
                print(f"   {label}: {state['n']}/{len(todo)}  ${state['spent']:.2f}  ~{left / 60:.0f} min left", flush=True)
            if budget_usd is not None and state["spent"] >= budget_usd:
                print(f"   budget ${budget_usd:.2f} reached, stopping {label}", flush=True)
                stop.set()

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for f in as_completed([ex.submit(one, j) for j in todo]):
            f.result()
    print(f"{label}: finished {state['n']} jobs, {state['errors']} errors, total spent ${state['spent']:.2f}", flush=True)
    if state["errors"]:
        print(f"   re-run the same command to retry the {state['errors']} failed jobs", flush=True)
