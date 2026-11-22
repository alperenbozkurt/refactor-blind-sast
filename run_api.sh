#!/bin/bash
# Full API run: check access, scan base programs, generate LLM refactorings, scan them with SAST and
# with both LLMs, then print the comparison. Every step is resumable: if anything stops (network,
# budget, laptop sleep), run this script again and it continues where it left off.
# Usage: ./run_api.sh            (from the repository root)
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-.venv/bin/python}
WORKERS=${WORKERS:-6}
mkdir -p results
exec > >(tee -a results/run_api.log) 2>&1
echo "=== run started $(date)"

echo "--- 1/6 check API access and fix model settings"
$PY -I src/check_api.py sonnet kimi
$PY -I - <<'EOF'
import json, sys
cfg = json.load(open("results/api_config.json"))
bad = [m for m in ("sonnet", "kimi") if not cfg.get(m, {}).get("ok")]
if bad:
    sys.exit(f"STOP: model(s) {bad} not usable. Fix the model id in .env (see the ids printed above) and run again.")
EOF

echo "--- 2/6 LLM scan of the 240 base programs"
for m in sonnet kimi; do $PY -I src/llm_scan.py --model $m --set base --workers $WORKERS --budget 5; done

echo "--- 3/6 LLM refactorings (240 programs x L0/L1/L2)"
for m in sonnet kimi; do $PY -I src/refactor_llm.py --model $m --workers $WORKERS --budget 15; done

echo "--- 4/6 Bandit + Semgrep on the refactorings"
$PY -I src/scan_variants.py

echo "--- 5/6 LLM scan of the refactorings"
for m in sonnet kimi; do $PY -I src/llm_scan.py --model $m --set variants --workers $WORKERS --budget 15; done

echo "--- 6/6 comparison on the base programs"
$PY -I src/compare_detectors.py
echo "=== run finished $(date)"
