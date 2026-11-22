"""Minimal LLM clients used by the experiment: Amazon Bedrock (Converse API), the Anthropic
Messages API, Ollama, and a fake backend for dry runs. No third-party packages are needed.

Credentials and model ids are read from .env (never commit it):
  AWS_BEARER_TOKEN_BEDROCK=...      # Bedrock API key (Kimi, and Claude if SONNET_PROVIDER=bedrock)
  AWS_REGION=us-east-1
  ANTHROPIC_API_KEY=...             # Claude through the Anthropic API (default for "sonnet")
  SONNET_PROVIDER=anthropic         # or "bedrock" once the account has access there
  MODEL_SONNET=... / MODEL_KIMI=... # optional, override the default ids below
The working inference settings per model are fixed once by src/check_api.py and stored in
results/api_config.json; the experiment scripts refuse to run an API model without that file, so
every call of the study uses the same, recorded settings.
"""
import json
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
API_CONFIG = EXP / "results" / "api_config.json"

# Aliases used on the command line; check_api.py verifies the ids. Prices are USD per 1M tokens.
MODELS = {
    "sonnet": dict(env="MODEL_SONNET", provider_env="SONNET_PROVIDER", provider="anthropic",
                   default={"anthropic": "claude-sonnet-5-5", "bedrock": "global.anthropic.claude-sonnet-5-5"},
                   price_in=2.0, price_out=10.0),  # Anthropic list price
    "kimi": dict(env="MODEL_KIMI", provider_env="KIMI_PROVIDER", provider="bedrock",
                 default={"bedrock": "us.moonshotai.kimi-k3"},  # inference profile: the bare id is rejected on demand
                 price_in=1.0, price_out=4.0),  # estimate; check the Bedrock pricing page. Reasoning tokens count as output
}


def provider(alias):
    load_env()
    m = MODELS[alias]
    return os.environ.get(m["provider_env"]) or m["provider"]


def load_env():
    f = EXP / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def model_id(alias):
    m = MODELS[alias]
    return os.environ.get(m["env"]) or m["default"][provider(alias)]


class APIError(Exception):
    pass


BedrockError = APIError  # older name


def _headers(prov):
    if prov == "bedrock":
        token = os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
        if not token:
            raise APIError("AWS_BEARER_TOKEN_BEDROCK is not set (put it in .env)")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise APIError("ANTHROPIC_API_KEY is not set (put it in .env)")
    return {"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}


def _request(prov, url, body=None, method="POST", retries=6):
    """HTTP call with retries on throttling (429, Anthropic 529) and transient errors."""
    load_env()
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, method=method, headers=_headers(prov))
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:500]
            if e.code in (429, 500, 502, 503, 504, 529) and attempt < retries - 1:
                time.sleep(min(60, 2 ** attempt + random.random()))
                continue
            raise APIError(f"HTTP {e.code}: {msg}")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt < retries - 1:
                time.sleep(min(60, 2 ** attempt + random.random()))
                continue
            raise APIError(f"{type(e).__name__}: {e}")


def bedrock_converse(model, prompt, inference, extra=None, retries=6):
    """One user turn through the Converse API. Returns dict(text, usage, stop, latency_ms)."""
    load_env()
    region = os.environ.get("AWS_REGION", "us-east-1")
    url = f"https://bedrock-runtime.{region}.amazonaws.com/model/{urllib.parse.quote(model, safe='')}/converse"
    body = dict(messages=[{"role": "user", "content": [{"text": prompt}]}], inferenceConfig=inference)
    if extra:
        body["additionalModelRequestFields"] = extra
    r = _request("bedrock", url, body, retries=retries)
    parts = r["output"]["message"]["content"]
    text = "".join(p.get("text", "") for p in parts)
    # reasoning models (e.g. Kimi K3) return their thinking as reasoningContent blocks
    reasoning = "".join(p["reasoningContent"].get("reasoningText", {}).get("text", "") for p in parts if "reasoningContent" in p)
    return dict(text=text, reasoning=reasoning or None, usage=r.get("usage", {}), stop=r.get("stopReason"),
                latency_ms=r.get("metrics", {}).get("latencyMs"))


def anthropic_messages(model, prompt, inference, extra=None, retries=6):
    """One user turn through the Anthropic Messages API, returned in the same shape as Bedrock."""
    body = dict(model=model, max_tokens=inference.get("maxTokens", 1024),
                messages=[{"role": "user", "content": prompt}])
    if "temperature" in inference:
        body["temperature"] = inference["temperature"]
    body.update(extra or {})
    t0 = time.time()
    r = _request("anthropic", "https://api.anthropic.com/v1/messages", body, retries=retries)
    content = r.get("content", [])
    text = "".join(p.get("text", "") for p in content if p.get("type") == "text")
    reasoning = "".join(p.get("thinking", "") for p in content if p.get("type") == "thinking")
    u = r.get("usage", {})
    return dict(text=text, reasoning=reasoning or None,
                usage=dict(inputTokens=u.get("input_tokens"), outputTokens=u.get("output_tokens")),
                stop=r.get("stop_reason"), latency_ms=int((time.time() - t0) * 1000))


def converse(alias, model, prompt, inference, extra=None, retries=6):
    fn = anthropic_messages if provider(alias) == "anthropic" else bedrock_converse
    return fn(model, prompt, inference, extra, retries)


def bedrock_list(path):
    load_env()
    region = os.environ.get("AWS_REGION", "us-east-1")
    return _request("bedrock", f"https://bedrock.{region}.amazonaws.com/{path}", method="GET", retries=2)


def anthropic_models():
    return [m["id"] for m in _request("anthropic", "https://api.anthropic.com/v1/models?limit=100", method="GET", retries=2).get("data", [])]


def ollama_chat(model, prompt, json_mode=False):
    body = dict(model=model, stream=False, options=dict(temperature=0, seed=2026, num_ctx=8192, num_predict=4000),
                messages=[{"role": "user", "content": prompt}])
    if json_mode:
        body["format"] = "json"
    req = urllib.request.Request("http://localhost:11434/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    r = json.loads(urllib.request.urlopen(req, timeout=900).read())
    return dict(text=r["message"]["content"], usage=dict(inputTokens=r.get("prompt_eval_count"), outputTokens=r.get("eval_count")),
                stop=r.get("done_reason"), latency_ms=int((time.time() - t0) * 1000))


class Client:
    """``Client("sonnet")`` / ``Client("kimi")`` use the provider and settings fixed by check_api.py;
    ``Client("ollama:<model>")`` uses a local Ollama model; ``Client("fake")`` echoes for dry runs."""

    def __init__(self, alias):
        self.alias = alias
        if alias in MODELS:
            if not API_CONFIG.exists():
                raise SystemExit("results/api_config.json missing: run `python -I src/check_api.py` first")
            cfg = json.loads(API_CONFIG.read_text()).get(alias)
            if not cfg or not cfg.get("ok"):
                raise SystemExit(f"model '{alias}' did not pass check_api.py; see results/api_config.json")
            if cfg.get("provider") != provider(alias):
                raise SystemExit(f"provider of '{alias}' changed since check_api.py; run it again")
            self.model, self.inference, self.extra = cfg["model_id"], cfg["inference"], cfg.get("extra")
            self.provider = cfg["provider"]
            self.price = (MODELS[alias]["price_in"], MODELS[alias]["price_out"])
        elif alias.startswith("ollama:"):
            self.model, self.price = alias.split(":", 1)[1], (0.0, 0.0)
        elif alias == "fake":
            self.model, self.price = "fake", (0.0, 0.0)
        else:
            raise SystemExit(f"unknown model alias {alias}")

    def settings(self):
        if self.alias in MODELS:
            return dict(provider=self.provider, model_id=self.model, inference=self.inference, extra=self.extra)
        return dict(model_id=self.model)

    def ask(self, prompt, max_tokens, json_mode=False):
        if self.alias in MODELS:
            inference = dict(self.inference, maxTokens=max_tokens)
            return converse(self.alias, self.model, prompt, inference, self.extra)
        if self.alias.startswith("ollama:"):
            return ollama_chat(self.model, prompt, json_mode)
        code = re.search(r"```python\n(.*?)```", prompt, re.S)
        text = '{"vulnerable": false, "findings": []}' if json_mode else f"```python\n{code.group(1) if code else ''}```"
        return dict(text=text, usage=dict(inputTokens=len(prompt) // 4, outputTokens=len(text) // 4), stop="end_turn", latency_ms=0)

    def cost(self, usage):
        return ((usage.get("inputTokens") or 0) * self.price[0] + (usage.get("outputTokens") or 0) * self.price[1]) / 1e6
