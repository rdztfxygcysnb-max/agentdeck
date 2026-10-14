#!/usr/bin/env python3
"""AgentDeck summary layer (Day 3): AI digest of the latest fleet snapshot.

Reads collector/snapshots/latest.json, asks Google's free Gemini tier to
produce a one-line-per-bridge digest + fleet headline (ZH for the dashboard,
EN for the DEV submission), and writes collector/snapshots/digest.json.

Usage:
    GEMINI_API_KEY=<key from aistudio.google.com> python3 summarize.py

The key is NEVER stored in this repo; it comes from the env var only.
Free-tier caveat: do not route private project content through it —
Google may train on free-tier data. We only send bridge health metadata
and truncated activity-note text the user already publishes on their own
dashboard. (Hourly summaries are well within the free quota.)

Exit codes: 0 = digest written (even a soft "unavailable" marker),
            2 = misconfiguration (no key, no snapshot).
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

BASE = "https://generativelanguage.googleapis.com/v1beta"
# Free-tier model ladder: try newest flash first, fall back if a name 404s.
MODEL_LADDER = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash"]
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


def call_gemini(prompt, key):
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 600},
    }).encode("utf-8")
    last_err = None
    for model in MODEL_LADDER:
        url = f"{BASE}/models/{model}:generateContent"
        for attempt in range(3):
            req = urllib.request.Request(
                url, data=body,
                headers={"Content-Type": "application/json",
                         "x-goog-api-key": key})
            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    data = json.load(resp)
                text = "".join(
                    p.get("text", "")
                    for c in data.get("candidates", [])
                    for p in c.get("content", {}).get("parts", []))
                if text.strip():
                    return model, text
                last_err = f"{model}: empty response"
                break
            except urllib.error.HTTPError as e:
                code = e.code
                body_text = e.read().decode("utf-8", "replace")[:200]
                last_err = f"{model}: HTTP {code} {body_text}"
                if code in (429, 503):
                    time.sleep(4 * (attempt + 1))   # backoff, then retry
                    continue
                if code == 404:
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
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    snap = load_snapshot()
    base = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_snapshot": snap.get("collected_at"),
        "model": None,
        "digest": None,
        "error": None,
    }
    if not key:
        # Safe no-op: leaves a soft marker so the dashboard can show
        # "AI 摘要未配置" instead of erroring. Exit 2 = needs attention.
        base["error"] = "GEMINI_API_KEY not set"
        write_digest(base)
        print("GEMINI_API_KEY not set — wrote soft marker, no API call made.",
              file=sys.stderr)
        sys.exit(2)

    model, result = call_gemini(PROMPT_TMPL.format(
        snapshot=json.dumps(compact(snap), ensure_ascii=False)), key)
    if model is None:
        base["error"] = result
        write_digest(base)
        print(f"gemini call failed: {result}", file=sys.stderr)
        sys.exit(1)
    try:
        base["model"] = model
        base["digest"] = parse_digest(result)
    except (json.JSONDecodeError, AttributeError) as e:
        base["error"] = f"unparseable model output: {e}; raw[:200]={result[:200]!r}"
        write_digest(base)
        sys.exit(1)
    write_digest(base)
    print(f"headline: {base['digest']['headline_zh']}")


if __name__ == "__main__":
    main()
