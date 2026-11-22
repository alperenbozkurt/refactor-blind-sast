# refactor-blind-sast

Does ordinary LLM refactoring hide real, still-exploitable vulnerabilities from Python security
scanners? This repository contains the pipeline, prompts, tool versions, the LLM refactorings and the results
of a study that refactors the PySASTBench synthetic programs with two LLMs, scans the originals
and the refactorings with Bandit, Semgrep, CodeQL and two LLM reviewers, and runs every version to
decide whether a lost detection is a real miss (the attack still fires) or a real fix.

## Data

The base programs come from the synthetic set of PySASTBench
(Liu et al., "An Empirical Study on Static Application Security Testing (SAST) Tools for Python",
ICSE 2026; https://github.com/Victor725/PySASTBench): 120 vulnerable programs and their fixed
versions, 20 pairs for each of CWE-22, 77, 79, 89, 94 and 502.

The dataset repository states no licence for the synthetic set, so **the original programs are not
included here.** `src/prepare.py` rebuilds them from a clone of that repository at commit `3ad04b7`.
The 1,434 valid LLM refactorings are included in `data/llm_variants/<id>/<vuln|safe>/<model>_<prompt>/main.py`;
`results/refactor/<model>.jsonl` holds every refactoring call (prompt, settings, raw answer, token
usage, cost, parse status) and `results/llm_scan/*.jsonl` every review answer.

`prepare.py` removes comments, docstrings and identifiers that announce the vulnerability
(e.g. `# Vulnerable function`, `vulnerable_render`), so that the LLMs that refactor or review the
code are not given the answer. Both versions of each pair are treated the same way.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt                # Bandit 1.8.6, Semgrep 1.136.0
python3 -m venv .venv-dynamic                            # frameworks the programs import
.venv-dynamic/bin/pip install -r requirements-dynamic.txt
git clone https://github.com/Victor725/PySASTBench data/PySASTBench_raw
git -C data/PySASTBench_raw checkout 3ad04b7
.venv/bin/python -I src/prepare.py
cp .env.example .env                                     # then add your API credentials
```

CodeQL: CLI 2.27.4 with the `codeql/python-queries` pack 1.9.0, suite `python-security-extended`,
threat model `local` (see `results/codeql/versions.json`). The Semgrep rule sets are pinned in
`rules/` (checksums in `rules/SHA256SUMS`). `src/dynamic_check/fix_probes.py` also needs Google
Chrome for one headless page check. All experiment code uses the Python standard library only;
the third-party packages are the scanners and the frameworks the benchmark programs import.

## Models and prompts

Refactorers and reviewers: Kimi K3 (Amazon Bedrock, `us.moonshotai.kimi-k3`) and Claude Sonnet 5.5
(Anthropic API, `claude-sonnet-5-5`), both with provider defaults because neither accepts a
temperature setting (`results/api_config.json`). All prompts are in `src/prompts.py`: three
refactoring prompts (L0 plain, L1 readability, L2 modular) that require behaviour, names,
signatures, classes, routes and the command-line interface to stay the same, and one review prompt
that asks for a JSON verdict with CWE, function and line.

## Pipeline

| Step | Script | Output |
|---|---|---|
| Fix model settings | `src/check_api.py` | `results/api_config.json` |
| Bandit and Semgrep on the base programs | `src/scan_base.py` | `results/base_detections.json` |
| LLM review of the base programs (3 repetitions) | `src/llm_scan.py --set base --repeat 3` | `results/llm_scan/<model>__base.jsonl` |
| LLM refactorings (L0/L1/L2) | `src/refactor_llm.py` | `data/llm_variants/`, `results/refactor/<model>.jsonl` |
| Bandit and Semgrep on the refactorings | `src/scan_variants.py` | `results/variant_detections.json` |
| LLM review of the refactorings | `src/llm_scan.py --set variants` | `results/llm_scan/<model>__variants.jsonl` |
| CodeQL on originals and refactorings | `src/scan_codeql.py --work DIR` | `results/codeql/findings.jsonl`, `results/codeql_detections.json` |
| Dynamic check, CLI programs | `src/dynamic_check/run.py --cwe C` | `results/dynamic/<cwe>.json` |
| Dynamic check, web programs | `src/dynamic_check/run_web.py --cwe C` | `results/dynamic/<cwe>_web.json` |
| Blinding rates and intervals (Tables II, III) | `src/compare_variants.py --json results/blinding.json` | `results/blinding.json` |
| Controlled SQL experiment (Table IV) | `src/sql_literal_experiment.py prepare/scan --work DIR` | `results/codeql/sql_literal_experiment.json` |
| Controlled dispatch experiment (Table V) | `src/dispatch_experiment.py prepare/scan --work DIR` | `results/codeql/dispatch_experiment.json` |
| False alarms, equivalence, per-model analyses | `src/extra_analyses.py` | `results/extra_analyses.json` |
| Line check, combinations, silent repairs, sensitivity | `src/review_analyses.py` | `results/review_analyses.json` |
| Probes on six fixed programs | `src/dynamic_check/fix_probes.py` | `results/fix_probes.json` |

`run_api.sh` runs the API steps in order. Every LLM step is resumable and has a cost limit.
Run every script from the repository root with `-I`.

## Measurement rules

A finding counts if one of its CWE ids is in the accepted set for the program's CWE (`ACCEPT` in
`src/scan_base.py`, e.g. CWE-78 for CWE-77), it is not on an import line, and its severity is at
least medium (or the tool's equivalent). *Located* additionally requires the finding to lie inside
the function the dataset labels as vulnerable; *flagged* accepts any line of the file. Because
refactorings move code into new helpers, located shows a 20-28% loss for every detector, so
blinding is measured with flagged.

Each program is run once with a normal input and once with an attack input carrying a harmless
marker (`src/dynamic_check/`). A program is *verified* if the attack fires on the vulnerable version
and not on the fixed one (109 of 120). Each refactoring of a verified program that a detector
flagged originally is *kept* (attack fires, still flagged), *blinded* (attack fires, not flagged) or
*fixed* (attack no longer fires). Blinding rate = blinded / (kept + blinded), with 95% Wilson
intervals and program-clustered bootstrap intervals (5,000 resamples).

## Other files

`results/llm_scan/claude.jsonl` and `results/llm_scan/qwen2.5-coder_14b.jsonl` are early trial runs
(isolated Claude sessions; a local Qwen2.5-Coder 14B through Ollama) used only by
`src/compare_detectors.py`; they are not part of the reported measurements.
