#!/usr/bin/env python3
"""Dump go9 match replay events for analysis."""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

BASE = "http://139.196.148.174/api"
OUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "replays"


def get(path: str):
    with urllib.request.urlopen(BASE + path, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main(ids: list[int]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for mid in ids:
        data = get(f"/matches/{mid}")
        payload = data.get("data", data)
        path = OUT_DIR / f"match_{mid}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        events = payload.get("events") or payload.get("detail", {}).get("events") or []
        print(f"match {mid}: keys={list(payload.keys())[:20]} events={len(events) if isinstance(events, list) else type(events)}")
        # try nested
        if not events and isinstance(payload.get("detail"), dict):
            for k, v in payload["detail"].items():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    print(f"  detail.{k} len={len(v)} sample_keys={list(v[0].keys())}")


if __name__ == "__main__":
    ids = [int(x) for x in (sys.argv[1:] or ["387", "388"])]
    main(ids)
