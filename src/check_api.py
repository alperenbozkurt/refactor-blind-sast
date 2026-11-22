"""Check API access and fix the inference settings of each model before the experiment.

Usage: python -I src/check_api.py [sonnet kimi]
Writes results/api_config.json. For every model (on its provider: Anthropic API or Bedrock) it tries:
  1. temperature 0
  2. temperature 0 with extended thinking explicitly disabled
  3. provider defaults (no temperature)  -> accepted, but marked temperature_zero=false
The first setting the model accepts is stored and used by every later call. It then sends the same
detection prompt twice and records whether the two answers are identical (a determinism check).
If a model id is rejected, the ids available to the account that contain the model's name are
printed so the id can be fixed in .env.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from llm_backend import API_CONFIG, EXP, MODELS, APIError, anthropic_models, bedrock_list, converse, load_env, model_id, provider  # noqa: E402
from prompts import DETECT  # noqa: E402

TRIES = [
    ("temperature 0", dict(temperature=0), None, True),
    ("temperature 0, thinking disabled", dict(temperature=0), {"thinking": {"type": "disabled"}}, True),
    ("provider defaults", dict(), None, False),
]
NAME_HINT = {"sonnet": "sonnet", "kimi": "kimi"}


def candidates(alias):
    hint = NAME_HINT[alias]
    if provider(alias) == "anthropic":
        try:
            return [m for m in anthropic_models() if hint in m]
        except APIError as e:
            return [f"(could not list models: {e})"]
    out = []
    for path, key, idk in (("foundation-models", "modelSummaries", "modelId"),
                           ("inference-profiles?maxResults=1000", "inferenceProfileSummaries", "inferenceProfileId")):
        try:
            out += [i[idk] for i in bedrock_list(path).get(key, []) if hint in i[idk].lower()]
        except APIError as e:
            out.append(f"(could not list {path.split('?')[0]}: {e})")
    return out


def main():
    load_env()
    aliases = sys.argv[1:] or list(MODELS)
    cfg = json.loads(API_CONFIG.read_text()) if API_CONFIG.exists() else {}
    sample = sorted((EXP / "data" / "pysastbench").iterdir())[0] / "vuln.py"
    for alias in aliases:
        mid, prov = model_id(alias), provider(alias)
        print(f"\n== {alias}: {mid} via {prov}")
        entry = dict(model_id=mid, provider=prov, ok=False, attempts=[])
        for label, inference, extra, tzero in TRIES:
            try:
                r = converse(alias, mid, "Reply with the single word OK.", dict(inference, maxTokens=20), extra, retries=3)
                print(f"   {label}: accepted -> {r['text'][:40]!r}")
                entry.update(ok=True, inference=inference, extra=extra, temperature_zero=tzero, setting=label)
                entry["attempts"].append(dict(setting=label, ok=True))
                break
            except APIError as e:
                print(f"   {label}: rejected -> {str(e)[:200]}")
                entry["attempts"].append(dict(setting=label, ok=False, error=str(e)[:500]))
                msg = str(e).lower()
                id_problem = "identifier" in msg or "model id" in msg or "not found" in msg or "not available" in msg
                if "http 400" not in msg or id_problem:
                    break  # access or model-id problem, not a parameter problem
        if not entry["ok"]:
            print("   model not usable. Matching ids available to your account:")
            for c in candidates(alias):
                print("     ", c)
            print(f"   -> set {MODELS[alias]['env']}=<id> in .env (or change {MODELS[alias]['provider_env']}) and re-run")
        else:
            prompt = DETECT.format(code=sample.read_text())
            a = [converse(alias, mid, prompt, dict(entry["inference"], maxTokens=1500), entry["extra"])["text"] for _ in range(2)]
            entry["deterministic_on_sample"] = a[0] == a[1]
            entry["sample_answer"] = a[0][:1000]
            print(f"   setting used: {entry['setting']} | same answer twice: {entry['deterministic_on_sample']}")
            if not entry["temperature_zero"]:
                print("   NOTE: temperature 0 was not accepted; the study will run with provider defaults")
        cfg[alias] = entry
    API_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    API_CONFIG.write_text(json.dumps(cfg, indent=1))
    print(f"\nsaved {API_CONFIG.relative_to(EXP)}")


if __name__ == "__main__":
    main()
