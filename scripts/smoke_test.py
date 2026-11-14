#!/usr/bin/env python3
"""Local smoke tests for go9 bot.py — stdlib only.

Run from repo root:
  python -u scripts/smoke_test.py
  python3 -u scripts/smoke_test.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / "bot.py"


def run_bot(req: dict, timeout: float = 20.0) -> dict:
    out = subprocess.check_output(
        [sys.executable, "-u", str(BOT)],
        input=json.dumps(req, ensure_ascii=False) + "\n",
        text=True,
        timeout=timeout,
        cwd=str(ROOT),
    )
    lines = [ln for ln in out.splitlines() if ln.strip()]
    if len(lines) != 1:
        raise AssertionError(f"expected exactly 1 stdout line, got {len(lines)}: {out!r}")
    return json.loads(lines[0])


def base_obs(**kw):
    board = [[0] * 9 for _ in range(9)]
    obs = {
        "size": 9,
        "komi": 7.5,
        "board": board,
        "current_player": 1,
        "ko_point": None,
        "captures": {"1": 0, "2": 0},
        "pass_count": 0,
        "move_number": 0,
        "last_action": None,
        "available_actions": ["PLACE", "PASS", "RESIGN"],
        "passes_to_score": 2,
    }
    obs.update(kw)
    return obs


def make_req(oid: str, obs: dict, tlim: int = 1000) -> dict:
    return {
        "protocol": "arena.v1",
        "request_id": oid,
        "type": "move_request",
        "game": "go9",
        "rule_version": "go9-chinese-v2",
        "player": obs.get("current_player", 1),
        "turn_index": 1,
        "time_limit_ms": tlim,
        "observation": obs,
    }


def main() -> int:
    if not BOT.is_file():
        print(f"FAIL missing {BOT}")
        return 1

    results: list[tuple[str, bool, dict]] = []

    # 1) empty -> tengen
    r = run_bot(make_req("empty", base_obs()))
    a = r["action"]
    results.append(
        (
            "empty_tengen",
            a.get("kind") == "PLACE" and (a.get("row"), a.get("col")) == (4, 4),
            a,
        )
    )

    # 2) capture
    board = [[0] * 9 for _ in range(9)]
    board[2][3] = board[3][2] = board[3][4] = 1
    board[3][3] = 2
    r = run_bot(
        make_req(
            "capture",
            base_obs(
                board=board,
                move_number=8,
                last_action={"kind": "PLACE", "row": 3, "col": 3},
            ),
            tlim=2000,
        )
    )
    a = r["action"]
    results.append(
        (
            "capture_4_3",
            a.get("kind") == "PLACE" and (a.get("row"), a.get("col")) == (4, 3),
            a,
        )
    )

    # 3) refuse early PASS when capture available after opp PASS
    board = [[0] * 9 for _ in range(9)]
    board[2][3] = board[3][2] = board[3][4] = 1
    board[3][3] = 2
    for i in range(9):
        board[0][i] = 1
        board[1][i] = 1
    r = run_bot(
        make_req(
            "no_early_pass",
            base_obs(
                board=board,
                move_number=40,
                pass_count=1,
                last_action={"kind": "PASS"},
            ),
            tlim=2000,
        )
    )
    a = r["action"]
    results.append(
        (
            "refuse_early_pass_capture",
            a.get("kind") == "PLACE" and (a.get("row"), a.get("col")) == (4, 3),
            a,
        )
    )

    # 4) do not fill true eye
    board = [[0] * 9 for _ in range(9)]
    board[3][4] = board[5][4] = board[4][3] = board[4][5] = 1
    board[3][3] = board[3][5] = board[5][3] = board[5][5] = 1
    board[0][0] = board[0][1] = board[1][0] = 2
    board[8][8] = board[8][7] = board[7][8] = 2
    r = run_bot(
        make_req(
            "no_fill_eye",
            base_obs(
                board=board,
                move_number=20,
                last_action={"kind": "PLACE", "row": 0, "col": 0},
            ),
            tlim=2500,
        )
    )
    a = r["action"]
    results.append(
        (
            "no_fill_true_eye",
            not (a.get("kind") == "PLACE" and (a.get("row"), a.get("col")) == (4, 4)),
            a,
        )
    )

    # 5) legal_moves restriction
    board = [[0] * 9 for _ in range(9)]
    board[4][4] = 1
    r = run_bot(
        make_req(
            "legal",
            base_obs(
                board=board,
                current_player=2,
                move_number=1,
                last_action={"kind": "PLACE", "row": 4, "col": 4},
                legal_moves=[[2, 4], [6, 4]],
            ),
            tlim=2000,
        )
    )
    a = r["action"]
    results.append(
        (
            "legal_moves",
            a.get("kind") == "PLACE" and (a.get("row"), a.get("col")) in {(2, 4), (6, 4)},
            a,
        )
    )

    # 6) after tengen, not opening 3-3
    board = [[0] * 9 for _ in range(9)]
    board[4][4] = 1
    r = run_bot(
        make_req(
            "after_tengen",
            base_obs(
                board=board,
                current_player=2,
                move_number=1,
                last_action={"kind": "PLACE", "row": 4, "col": 4},
            ),
            tlim=1000,
        )
    )
    a = r["action"]
    results.append(
        (
            "after_tengen_not_33",
            a.get("kind") == "PLACE"
            and (a.get("row"), a.get("col")) not in {(2, 2), (2, 6), (6, 2), (6, 6)},
            a,
        )
    )

    # protocol envelope checks on last response
    assert r.get("protocol") == "arena.v1"
    assert r.get("type") == "move_response"
    assert "action" in r

    all_ok = True
    for name, ok, action in results:
        print(f"{'OK' if ok else 'FAIL':4} {name}: {action}")
        all_ok = all_ok and ok

    print("ALL_SMOKE_OK" if all_ok else "SMOKE_FAILED")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
