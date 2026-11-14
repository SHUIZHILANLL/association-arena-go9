#!/usr/bin/env python3
"""Analyze a go9 replay for missed captures / early PASS / time use."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import bot  # noqa: E402


def analyze(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    events = data["events"]
    print(f"=== {path.name} players={data.get('players')} ===")
    our = None
    # infer: if first_name in match meta
    match = data.get("match") or {}
    # from result side
    # We'll mark student by checking names in file parent analysis — pass as arg via filename
    board = [0] * bot.N
    captures = [0, 0, 0]
    ko = -1
    pass_count = 0
    missed = []
    early_pass = []
    time_samples = []
    for e in events:
        a = e["action"]
        player = int(e["player"])
        elapsed = int(e.get("elapsed_ms") or 0)
        time_samples.append((e["seq"], player, elapsed, a.get("kind")))
        pos = bot.Position(board, player, ko, pass_count, captures, e["seq"] - 1)
        places = pos.legal_places()
        caps = bot.capture_moves(pos, places)
        kills = bot.kill_pressure_moves(pos, places)
        if a["kind"] == "PASS":
            if caps or kills:
                early_pass.append(
                    {
                        "seq": e["seq"],
                        "player": player,
                        "caps": [bot.to_rc(m) for m in caps[:5]],
                        "kills": [bot.to_rc(m) for m in kills[:5]],
                        "elapsed": elapsed,
                    }
                )
            pos.play(bot.PASS_MOVE)
        else:
            mv = bot.from_rc(int(a["row"]), int(a["col"]))
            if caps and mv not in caps and player:  # any miss
                # only flag if capturing was available and move wasn't capture
                if caps[0] != mv:
                    # check size of capture
                    ok, captured = pos.is_suicide_after(caps[0], player)
                    if ok and len(captured) >= 2:
                        missed.append(
                            {
                                "seq": e["seq"],
                                "player": player,
                                "played": (a["row"], a["col"]),
                                "could_capture": bot.to_rc(caps[0]),
                                "n": len(captured),
                                "elapsed": elapsed,
                            }
                        )
            pos.play(mv)
        board = pos.board[:]
        captures = pos.captures[:]
        ko = pos.ko
        pass_count = pos.pass_count

    # time by player
    for p in (1, 2):
        ts = [t for s, pl, t, k in time_samples if pl == p and k == "PLACE"]
        if not ts:
            continue
        print(
            f"player{p} PLACE times: n={len(ts)} mean={sum(ts)/len(ts):.0f} "
            f"max={max(ts)} min={min(ts)} under500={sum(1 for t in ts if t < 500)} "
            f"over5k={sum(1 for t in ts if t >= 5000)}"
        )
    print(f"missed_big_captures={len(missed)} sample={missed[:8]}")
    print(f"pass_while_unsettled={early_pass}")
    # final captures from result
    det = (((data.get("result") or {}).get("detail") or {}).get("server_result") or {}).get("detail") or {}
    print("final", det.get("winner_text"), "captures", det.get("captures"))


def main() -> None:
    files = list((ROOT / "docs" / "replays").glob("match_*_replay.json"))
    for f in sorted(files):
        analyze(f)
        print()


if __name__ == "__main__":
    main()
