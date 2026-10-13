#!/usr/bin/env python3
"""AgentDeck collector (Day 1): poll phone-bridge MCP servers and snapshot agent activity.

Usage:
    BRIDGE_PRISMA_URL=... BRIDGE_PRISMA_TOKEN=... \
    BRIDGE_RAILWAY_URL=... BRIDGE_RAILWAY_TOKEN=... \
    python3 collect.py

Writes a JSON snapshot to snapshots/<timestamp>.json and prints a summary.
Tokens are NEVER stored in this repo; they come from env vars only.
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
import httpx2

# Sandbox proxy env may contain "[::1]" in no_proxy, which breaks httpx2's
# proxy-pattern parsing. Neutralize it before any client is created.
for _k in ("no_proxy", "NO_PROXY"):
    os.environ[_k] = "localhost,127.0.0.1"


def bridges():
    out = []
    for prefix in ("PRISMA", "RAILWAY"):
        url = os.environ.get(f"BRIDGE_{prefix}_URL", "").strip()
        token = os.environ.get(f"BRIDGE_{prefix}_TOKEN", "").strip()
        if url and token:
            out.append((prefix.lower(), url, token))
    return out


async def poll_bridge(name, url, token):
    """Connect to one bridge, list tools, and pull its activity notes."""
    result = {"bridge": name, "url": url, "ok": False}
    client = httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=30.0)
    try:
        async with streamable_http_client(url, http_client=client) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                tool_names = [t.name for t in tools.tools]
                result["tools"] = tool_names
                # Pull recent notes as the "agent activity stream".
                notes = []
                if "notes_list" in tool_names:
                    for args in ({}, {"limit": 20}):
                        try:
                            resp = await session.call_tool("notes_list", args)
                            notes = _texts(resp)
                            break
                        except Exception:
                            continue
                result["notes"] = notes
                result["notes_count"] = len(notes)
                result["ok"] = True
    except Exception as e:  # noqa: BLE001 - report, don't crash the whole poll
        result["error"] = f"{type(e).__name__}: {e}"
    return result


def _texts(resp):
    out = []
    for c in getattr(resp, "content", []) or []:
        t = getattr(c, "text", None)
        if t:
            out.append(t)
    return out


async def main():
    bs = bridges()
    if not bs:
        print("no bridges configured (need BRIDGE_<PRISMA|RAILWAY>_URL and _TOKEN)", file=sys.stderr)
        sys.exit(2)
    results = await asyncio.gather(*[poll_bridge(n, u, t) for n, u, t in bs])
    snapshot = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "bridges": list(results),
    }
    os.makedirs("snapshots", exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = f"snapshots/{stamp}.json"
    with open(path, "w") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    # The static dashboard always reads this one; no need to guess filenames.
    with open("snapshots/latest.json", "w") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    for r in results:
        if r["ok"]:
            print(f"[{r['bridge']}] OK tools={r.get('tools')} notes={r.get('notes_count')}")
        else:
            print(f"[{r['bridge']}] FAIL {r.get('error')}")
    print(f"snapshot -> {path}")


if __name__ == "__main__":
    asyncio.run(main())
