#!/usr/bin/env python3
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
n = int(sys.argv[2]) if len(sys.argv) > 2 else 60
ev = json.loads(path.read_text(encoding="utf-8"))["events"]
for e in ev[:n]:
    a = e["action"]
    p = e["player"]
    if a["kind"] == "PASS":
        print(f"{e['seq']:2} P{p} PASS t={e['elapsed_ms']}")
    else:
        print(f"{e['seq']:2} P{p} {a['row']},{a['col']} t={e['elapsed_ms']}")
