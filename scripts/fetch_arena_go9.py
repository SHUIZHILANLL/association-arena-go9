#!/usr/bin/env python3
"""Fetch go9 leaderboard / matches / score weights from Association Arena."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "http://139.196.148.174/api"
OUT = Path(__file__).resolve().parents[1] / "docs" / "arena_go9_snapshot.md"


def get(path: str, params: dict | None = None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    games = get("/games")["data"]
    go9 = next(g for g in games if g["type"] == "go9")
    lb = get("/leaderboards/best", {"game": "go9"})["data"]
    matches = get("/matches", {"game": "go9"})["data"]

    lines: list[str] = []
    lines.append("# Arena go9 快照")
    lines.append("")
    lines.append(f"- rule_version: `{go9['rule_version']}`")
    lines.append(f"- score_rule_version: `{go9['benchmark']['score_rule_version']}`")
    lines.append(f"- move_cap: `{go9['benchmark']['move_cap']}`")
    lines.append(f"- match_count: `{go9['benchmark']['match_count']}`")
    lines.append(f"- participants: `{go9.get('stats', {}).get('participants')}`")
    lines.append("")
    lines.append("## go-score-v4 weights")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(go9["benchmark"]["weights"], ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## 排行榜（best）")
    lines.append("")
    target_row = None
    for i, row in enumerate(lb["list"], 1):
        u = row.get("user") or {}
        name = u.get("display_name") or u.get("username") or "?"
        total = row.get("total_score", row.get("score"))
        breakdown = row.get("breakdown") or row.get("score_detail") or {}
        lines.append(
            f"{i}. **{name}** (user_id={u.get('id')}) total={total} "
            f"submission={row.get('submission_id')} "
            f"keys={sorted(k for k in row.keys() if k != 'user')}"
        )
        # compact non-user fields
        slim = {k: v for k, v in row.items() if k != "user"}
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(slim, ensure_ascii=False, indent=2)[:2500])
        lines.append("```")
        lines.append("")
        if name == "张子益":
            target_row = row

    lines.append("## 张子益")
    lines.append("")
    if not target_row:
        lines.append("排行榜未找到 display_name=张子益")
    else:
        uid = target_row["user"]["id"]
        lines.append(f"- user_id: `{uid}`")
        lines.append(f"- submission_id: `{target_row.get('submission_id')}`")
        # try detail endpoint
        try:
            detail = get(
                f"/leaderboards/best/{target_row.get('submission_id')}/{uid}",
                {"season": (lb.get("season") or {}).get("id")},
            )
            lines.append("")
            lines.append("### leaderboard detail")
            lines.append("```json")
            lines.append(json.dumps(detail, ensure_ascii=False, indent=2)[:4000])
            lines.append("```")
        except Exception as e:
            lines.append(f"- detail fetch failed: {e}")

        name = target_row["user"]["display_name"]
        lines.append("")
        lines.append("### 相关对局")
        for m in matches:
            related = name in (m.get("first_name") or "", m.get("second_name") or "")
            # also match via detail student name fields if any
            blob = json.dumps(m, ensure_ascii=False)
            if related or name in blob:
                d = m.get("detail") or {}
                sc = d.get("score") or {}
                lines.append(
                    f"- match `{m['id']}`: {m['first_name']} vs {m['second_name']} | "
                    f"result={m['result']} reason={m['reason']} | "
                    f"student_side={d.get('student_side')} student_result={d.get('student_result')} | "
                    f"events={m['events_count']} duration_ms={m['duration_ms']} has_replay={m['has_replay']}"
                )
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(sc, ensure_ascii=False, indent=2)[:3000])
                lines.append("```")
                lines.append("")
                # try replay
                if m.get("has_replay"):
                    for path in (
                        f"/matches/{m['id']}",
                        f"/matches/{m['id']}/replay",
                        f"/matches/{m['id']}/events",
                    ):
                        try:
                            rep = get(path)
                            lines.append(f"#### GET {path}")
                            lines.append("```json")
                            s = json.dumps(rep, ensure_ascii=False)
                            lines.append(s[:5000])
                            lines.append("```")
                            lines.append("")
                            break
                        except Exception:
                            continue

    lines.append("## 全部公开对局摘要")
    lines.append("")
    for m in matches:
        d = m.get("detail") or {}
        sc = d.get("score") or {}
        lines.append(
            f"- `{m['id']}` {m['first_name']} vs {m['second_name']} | "
            f"{m['result']}/{m['reason']} | student={d.get('student_result')} | "
            f"total={sc.get('total', sc.get('final_score', sc.get('score')))} | "
            f"moves={m['events_count']}"
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
