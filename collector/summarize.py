#!/usr/bin/env python3
"""AgentDeck summary layer (Day 3): AI digest of the latest fleet snapshot.

Reads collector/snapshots/latest.json, asks an LLM to produce a
one-line-per-bridge digest + fleet headline (ZH for the dashboard,
EN for the DEV submission), and writes collector/snapshots/digest.json.

Providers (first configured key wins):
  1. Atria (default): OpenAI-compatible endpoint.
       ATRIA_API_KEY=<atr_... from api.atria-asi.ai/console/keys>
       ATRIA_BASE_URL (default https://api.atria-asi.ai/v1)
       ATRIA_MODEL    (default Atria-Dawn-Preview)
     Verified 2026-10-17: POST {base}/chat/completions with
     Authorization: Bearer atr_...; free preview (~100M token cap/account).
  2. Gemini (fallback): Google AI Studio free tier.
       GEMINI_API_KEY=<key from aistudio.google.com>
     Free-tier caveat: do not route private project content through it --
     Google may train on free-tier data. We only send bridge health metadata
     and truncated activity-note text the user already publishes on their own
     dashboard. (Hourly summaries are well within the free quota.)

Keys are NEVER stored in this repo; they come from env vars only.
The hourly cron reads them from mode-600 files outside the repo:
  /home/hatch/workspace/.agentdeck-atria-key
  /home/hatch/workspace/.agentdeck-gemini-key

Exit codes: 0 = digest written (even a soft "unavailable" marker),
            1 = provider call failed (marker written, cron continues),
            2 = misconfiguration (no key, no snapshot).
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

# --- provider config -------------------------------------------------------
ATRIA_BASE_URL = os.environ.get("ATRIA_BASE_URL",
                                "https://api.atria-asi.ai/v1").rstrip("/")
ATRIA_MODEL = os.environ.get("ATRIA_MODEL", "Atria-Dawn-Preview")
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
# Free-tier model ladder: try newest flash first, fall back if a name 404s.
GEMINI_MODEL_LADDER = ["gemini-2.5-flash", "gemini-flash-latest",
                       "gemini-2.0-flash"]

SNAP = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "snapshots", "latest.json")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "snapshots", "digest.json")
MAX_NOTES_CHARS = 4000


def load_snapshot():
    try:
        with open(SNAP, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"no usable snapshot at {SNAP}: {e}", file=sys.stderr)
        sys.exit(2)


def compact(snap):
    """Shrink the snapshot into digestible input for the model."""
    bridges = []
    for b in snap.get("bridges", []):
        notes = [n for n in (b.get("notes") or [])
                 if isinstance(n, str) and n.strip() and n.strip() != "(none)"]
        text = "\n".join(notes)[:MAX_NOTES_CHARS]
        bridges.append({
            "bridge": b.get("bridge"),
            "ok": b.get("ok"),
            "error": (b.get("error") or "")[:300] if not b.get("ok") else None,
            "tools": b.get("tools") or [],
            "notes_count": b.get("notes_count", len(notes)),
            "notes": text,
        })
    return {
        "collected_at": snap.get("collected_at"),
        "bridges": bridges,
    }


PROMPT_TMPL = """You are the daily-digest writer for AgentDeck, a phone dashboard that
shows a user's fleet of coding-agent bridge servers. Below is a compact fleet
snapshot (bridge health, tool list, recent agent activity notes).

Write a tight digest. Output ONLY valid JSON, no markdown fences, with exactly
these keys:
  headline_zh: one Chinese sentence describing the whole fleet's state right now
  headline_en: the same, in English (one sentence)
  per_bridge: object keyed by bridge name, each with one_liner_zh and
    one_liner_en (one sentence each: what's happening on that bridge;
    if offline, say so plainly and briefly)

Keep every sentence under 40 words. No hype, no exclamation marks.

SNAPSHOT:
{snapshot}
"""


def _post(url, body, headers, timeout=45):
    """POST JSON, return parsed JSON response; raise on HTTP/network error."""
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def call_openai_compat(prompt, base_url, model, key):
    """OpenAI-compatible /chat/completions call (used for Atria)."""
    url = f"{base_url}/chat/completions"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 600,
    }
    headers = {"Content-Type": "application/json",
               "Authorization": f"Bearer {key}"}
    last_err = None
    for attempt in range(3):
        try:
            data = _post(url, body, headers)
            # Atria reasoning models may also return `reasoning_content`;
            # the digest lives in the regular content field.
            msg = (data.get("choices") or [{}])[0].get("message") or {}
            text = (msg.get("content") or "").strip()
            if text:
                return model, text
            last_err = f"{model}: empty content (raw keys: {list(msg.keys())})"
            break
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", "replace")[:200]
            last_err = f"{model}: HTTP {e.code} {body_text}"
            if e.code in (429, 503):
                time.sleep(4 * (attempt + 1))   # backoff, then retry
                continue
            return None, last_err               # 401/404/...: fail loudly
        except Exception as e:  # noqa: BLE001 - network flakiness
            last_err = f"{model}: {type(e).__name__}: {e}"
            time.sleep(2 * (attempt + 1))
    return None, last_err


def call_gemini(prompt, key):
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 600},
    }
    headers = {"Content-Type": "application/json", "x-goog-api-key": key}
    last_err = None
    for model in GEMINI_MODEL_LADDER:
        url = f"{GEMINI_BASE}/models/{model}:generateContent"
        for attempt in range(3):
            try:
                data = _post(url, body, headers)
                text = "".join(
                    p.get("text", "")
                    for c in data.get("candidates", [])
                    for p in c.get("content", {}).get("parts", []))
                if text.strip():
                    return model, text
                last_err = f"{model}: empty response"
                break
            except urllib.error.HTTPError as e:
                body_text = e.read().decode("utf-8", "replace")[:200]
                last_err = f"{model}: HTTP {e.code} {body_text}"
                if e.code in (429, 503):
                    time.sleep(4 * (attempt + 1))   # backoff, then retry
                    continue
                if e.code == 404:
                    break                            # bad model name: next rung
                return None, last_err
            except Exception as e:  # noqa: BLE001 - network flakiness
                last_err = f"{model}: {type(e).__name__}: {e}"
                time.sleep(2 * (attempt + 1))
    return None, last_err


def parse_digest(text):
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1]
        t = t.rsplit("```", 1)[0]
    d = json.loads(t)
    return {
        "headline_zh": str(d.get("headline_zh", ""))[:200],
        "headline_en": str(d.get("headline_en", ""))[:200],
        "per_bridge": d.get("per_bridge", {}),
    }


def write_digest(payload):
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"digest -> {OUT}")


def main():
    atria_key = os.environ.get("ATRIA_API_KEY", "").strip()
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    snap = load_snapshot()
    base = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_snapshot": snap.get("collected_at"),
        "model": None,
        "digest": None,
        "error": None,
    }
    # Provider priority: SUMMARY_PROVIDER=atria|gemini forces one;
    # default "auto" tries Atria first (the key the user is fetching now),
    # then Gemini. Flip to gemini if the $200 Best-Use-of-Gemma category
    # matters more than unblocking the digest tonight.
    pref = os.environ.get("SUMMARY_PROVIDER", "auto").strip().lower()
    order = [("atria", atria_key), ("gemini", gemini_key)]
    if pref in ("atria", "gemini"):
        order = [c for c in order if c[0] == pref]
    provider, call = None, None
    for name, key in order:
        if not key:
            continue
        if name == "atria":
            provider = f"atria/{ATRIA_MODEL}"
            call = (lambda p, k=key: call_openai_compat(p, ATRIA_BASE_URL,
                                                        ATRIA_MODEL, k))
        else:
            provider = "gemini"
            call = (lambda p, k=key: call_gemini(p, k))
        break
    if call is None:
        # Safe no-op: leaves a soft marker so the dashboard can show
        # nothing instead of erroring. Exit 2 = needs attention.
        base["error"] = "no API key set (ATRIA_API_KEY or GEMINI_API_KEY)"
        write_digest(base)
        print("no API key set — wrote soft marker, no API call made.",
              file=sys.stderr)
        sys.exit(2)

    model, result = call(PROMPT_TMPL.format(
        snapshot=json.dumps(compact(snap), ensure_ascii=False)))
    if model is None:
        base["error"] = f"{provider}: {result}"
        write_digest(base)
        print(f"{provider} call failed: {result}", file=sys.stderr)
        sys.exit(1)
    try:
        base["model"] = model
        base["digest"] = parse_digest(result)
    except (json.JSONDecodeError, AttributeError) as e:
        base["error"] = (f"unparseable model output: {e}; "
                         f"raw[:200]={result[:200]!r}")
        write_digest(base)
        sys.exit(1)
    write_digest(base)
    print(f"[{provider}] headline: {base['digest']['headline_zh']}")


if __name__ == "__main__":
    main()
