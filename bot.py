#!/usr/bin/env python3
"""Association Arena go9 — arena.v1 / go9-chinese-v2, stdlib only.

Clean rebuild (Michi/Pachi-aligned):
  - Single-thread time-boxed RAVE/AMAF MCTS (stable; multi-proc hurt us)
  - Balanced local playouts: capture/escape + 3x3 patterns
  - Virtual even priors; light tactical AB when hot
  - Instant tengen; never thin-lead PASS (fix 0.25-stone losses)
  - Trust observation.legal_moves
"""

from __future__ import annotations

import json
import math
import random
import sys
import time
from typing import Any, Optional

SIZE = 9
N = SIZE * SIZE
EMPTY, BLACK, WHITE = 0, 1, 2
PASS = -1
TECH_CAP = 400

# Michi priors / RAVE (9x9)
PRIOR_EVEN = 14
PRIOR_SELFATARI = 10
PRIOR_CAPTURE_ONE = 15
PRIOR_CAPTURE_MANY = 30
PRIOR_PAT3 = 10
PRIOR_CFG = (24, 22, 8)
RAVE_EQUIV = 3000.0
EXPAND_VISITS = 6
PROB_CAPTURE = 0.90
PROB_PAT3 = 0.90
PROB_SSAREJECT = 0.90
PROB_RSAREJECT = 0.50

NEIGHBORS: list[list[int]] = [[] for _ in range(N)]
DIAGS: list[list[int]] = [[] for _ in range(N)]
NEIGH8: list[list[int]] = [[] for _ in range(N)]
for _r in range(SIZE):
    for _c in range(SIZE):
        _i = _r * SIZE + _c
        for _dr, _dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            _nr, _nc = _r + _dr, _c + _dc
            if 0 <= _nr < SIZE and 0 <= _nc < SIZE:
                NEIGHBORS[_i].append(_nr * SIZE + _nc)
        for _dr, _dc in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
            _nr, _nc = _r + _dr, _c + _dc
            if 0 <= _nr < SIZE and 0 <= _nc < SIZE:
                DIAGS[_i].append(_nr * SIZE + _nc)
        for _dr in (-1, 0, 1):
            for _dc in (-1, 0, 1):
                if _dr == 0 and _dc == 0:
                    continue
                _nr, _nc = _r + _dr, _c + _dc
                if 0 <= _nr < SIZE and 0 <= _nc < SIZE:
                    NEIGH8[_i].append(_nr * SIZE + _nc)

CENTER = [0.0] * N
for _r in range(SIZE):
    for _c in range(SIZE):
        CENTER[_r * SIZE + _c] = 5.0 - (abs(_r - 4) + abs(_c - 4))

OPENING_BAD = {2 * 9 + 2, 2 * 9 + 6, 6 * 9 + 2, 6 * 9 + 6}
_PAT3_OFFS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 0), (0, 1), (1, -1), (1, 0), (1, 1)]

_rng = random.Random(0xC0FFEE)
Z_STONE = [[_rng.getrandbits(64) for _ in range(3)] for _ in range(N)]
Z_TO_PLAY = [_rng.getrandbits(64) for _ in range(3)]
Z_KO = [_rng.getrandbits(64) for _ in range(N + 1)]


def to_rc(i: int) -> tuple[int, int]:
    return divmod(i, SIZE)


def from_rc(r: int, c: int) -> int:
    return r * SIZE + c


def flatten(board2d: list[list[int]]) -> list[int]:
    out = [0] * N
    for r in range(SIZE):
        row = board2d[r]
        base = r * SIZE
        for c in range(SIZE):
            out[base + c] = int(row[c])
    return out


def parse_ko(ko: Any) -> int:
    if isinstance(ko, (list, tuple)) and len(ko) == 2:
        r, c = int(ko[0]), int(ko[1])
        if 0 <= r < SIZE and 0 <= c < SIZE:
            return from_rc(r, c)
    return -1


def parse_legal(obs: dict) -> Optional[set[int]]:
    raw = obs.get("legal_moves")
    if not raw:
        return None
    out: set[int] = set()
    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            r, c = int(item[0]), int(item[1])
            if 0 <= r < SIZE and 0 <= c < SIZE:
                out.add(from_rc(r, c))
        elif isinstance(item, dict):
            if "row" in item and "col" in item:
                out.add(from_rc(int(item["row"]), int(item["col"])))
    return out


def hash_pos(board: list[int], to_play: int, ko: int) -> int:
    h = Z_TO_PLAY[to_play] ^ Z_KO[ko + 1]
    for i, v in enumerate(board):
        if v:
            h ^= Z_STONE[i][v]
    return h


# ---------------------------------------------------------------------------
# 3x3 patterns (Michi subset)
# ---------------------------------------------------------------------------

_PAT3_SRC = [
    ["XOX", "...", "???"],
    ["XO.", "...", "?.?"],
    ["XO?", "X..", "x.?"],
    [".O.", "X..", "..."],
    ["XO?", "O.o", "?o?"],
    ["XO?", "O.X", "???"],
    ["?X?", "O.O", "ooo"],
    ["OX?", "o.O", "???"],
    [".XO", "o.o", "???"],
    ["X.O", "?.?", "???"],
    ["XX?", "..O", "?.?"],
    ["X.?", "?.O", "?.?"],
]


def _pat3_expand(pat: list[str]) -> list[str]:
    def rot90(p: list[str]) -> list[str]:
        return [p[2][0] + p[1][0] + p[0][0], p[2][1] + p[1][1] + p[0][1], p[2][2] + p[1][2] + p[0][2]]

    def vflip(p: list[str]) -> list[str]:
        return [p[2], p[1], p[0]]

    def hflip(p: list[str]) -> list[str]:
        return [ln[::-1] for ln in p]

    def swap(p: list[str]) -> list[str]:
        return [
            ln.replace("X", "Z").replace("x", "z").replace("O", "X").replace("o", "x").replace("Z", "O").replace("z", "o")
            for ln in p
        ]

    def wildexp(s: str, ch: str, opts: str) -> list[str]:
        i = s.find(ch)
        if i < 0:
            return [s]
        out: list[str] = []
        for t in opts:
            out.extend(wildexp(s[:i] + t + s[i + 1 :], ch, opts))
        return out

    def wildcards(s: str) -> list[str]:
        out: list[str] = []
        for a in wildexp(s, "?", ".XO "):
            for b in wildexp(a, "x", ".O "):
                out.extend(wildexp(b, "o", ".X "))
        return out

    acc: list[str] = []
    for p0 in (pat, rot90(pat)):
        for p1 in (p0, vflip(p0)):
            for p2 in (p1, hflip(p1)):
                for p3 in (p2, swap(p2)):
                    acc.extend(wildcards("".join(p3)))
    return acc


def _key_from_str(s: str) -> int:
    key = 0
    for ch in s.replace("O", "x"):
        key *= 4
        key += {".": 0, "X": 1, "x": 2}.get(ch, 3)
    return key


PAT3: set[int] = set()
for _p in _PAT3_SRC:
    for _e in _pat3_expand(_p):
        PAT3.add(_key_from_str(_e))


def pat3_key(board: list[int], idx: int, color: int) -> int:
    r, c = divmod(idx, SIZE)
    key = 0
    for dr, dc in _PAT3_OFFS:
        key *= 4
        nr, nc = r + dr, c + dc
        if not (0 <= nr < SIZE and 0 <= nc < SIZE):
            key += 3
        else:
            v = board[nr * SIZE + nc]
            if v == 0:
                key += 0
            elif v == color:
                key += 1
            else:
                key += 2
    return key


def matches_pat3(board: list[int], idx: int, color: int) -> bool:
    return pat3_key(board, idx, color) in PAT3


# ---------------------------------------------------------------------------
# Opening book (compact)
# ---------------------------------------------------------------------------

def _sym(r: int, c: int, k: int) -> tuple[int, int]:
    if k == 0:
        return r, c
    if k == 1:
        return r, SIZE - 1 - c
    if k == 2:
        return SIZE - 1 - r, c
    if k == 3:
        return SIZE - 1 - r, SIZE - 1 - c
    if k == 4:
        return c, r
    if k == 5:
        return c, SIZE - 1 - r
    if k == 6:
        return SIZE - 1 - c, r
    return SIZE - 1 - c, SIZE - 1 - r


_RAW_BOOK = [
    ([], (4, 4)),
    ([(4, 4)], (2, 4)),
    ([(4, 4)], (3, 5)),
    ([(4, 4)], (5, 5)),
    ([(4, 4)], (2, 3)),
    ([(4, 4)], (2, 5)),
    ([(4, 4)], (6, 4)),
    ([(4, 4)], (6, 5)),
    ([(4, 4)], (5, 6)),
    ([(4, 4), (2, 4)], (6, 4)),
    ([(4, 4), (2, 4)], (4, 6)),
    ([(4, 4), (2, 4)], (5, 5)),
    ([(4, 4), (6, 4)], (2, 4)),
    ([(4, 4), (6, 4)], (4, 2)),
    ([(4, 4), (6, 4)], (4, 6)),
    ([(4, 4), (6, 5)], (2, 4)),
    ([(4, 4), (6, 5)], (5, 3)),
    ([(4, 4), (6, 5)], (3, 6)),
    ([(4, 4), (5, 5)], (2, 4)),
    ([(4, 4), (5, 5)], (3, 2)),
    ([(4, 4), (3, 5)], (5, 3)),
    ([(4, 4), (2, 4), (6, 4)], (4, 2)),
    ([(4, 4), (2, 4), (6, 4)], (4, 6)),
]


def _build_book() -> dict[tuple, list[int]]:
    table: dict[tuple, list[int]] = {}
    for moves, reply in _RAW_BOOK:
        for k in range(8):
            board = [0] * N
            color = BLACK
            for r, c in moves:
                sr, sc = _sym(r, c, k)
                board[from_rc(sr, sc)] = color
                color = 3 - color
            rr, rc = _sym(reply[0], reply[1], k)
            key = tuple(board) + (color,)
            idx = from_rc(rr, rc)
            bucket = table.setdefault(key, [])
            if idx not in bucket:
                bucket.append(idx)
    return table


BOOK = _build_book()


# ---------------------------------------------------------------------------
# Position
# ---------------------------------------------------------------------------


class Position:
    __slots__ = (
        "board", "to_play", "ko", "pass_count", "captures",
        "move_number", "_stack", "zhash", "_seen_s", "_seen_l", "_stamp",
    )

    def __init__(
        self,
        board: list[int],
        to_play: int,
        ko: int = -1,
        pass_count: int = 0,
        captures: Optional[list[int]] = None,
        move_number: int = 0,
        zhash: Optional[int] = None,
    ) -> None:
        self.board = board[:]
        self.to_play = to_play
        self.ko = ko
        self.pass_count = pass_count
        self.captures = captures[:] if captures else [0, 0, 0]
        self.move_number = move_number
        self._stack: list[tuple] = []
        self.zhash = zhash if zhash is not None else hash_pos(self.board, to_play, ko)
        self._seen_s = [0] * N
        self._seen_l = [0] * N
        self._stamp = 1

    def copy(self) -> "Position":
        return Position(
            self.board, self.to_play, self.ko, self.pass_count,
            self.captures, self.move_number, self.zhash,
        )

    def _bump(self) -> int:
        self._stamp += 1
        if self._stamp > 1_000_000_000:
            self._seen_s = [0] * N
            self._seen_l = [0] * N
            self._stamp = 1
        return self._stamp

    def group_libs(self, start: int, color: int) -> tuple[list[int], list[int]]:
        board = self.board
        stack = [start]
        stones: list[int] = []
        libs: list[int] = []
        st = self._bump()
        ss, sl = self._seen_s, self._seen_l
        while stack:
            i = stack.pop()
            if ss[i] == st:
                continue
            ss[i] = st
            stones.append(i)
            for n in NEIGHBORS[i]:
                v = board[n]
                if v == 0:
                    if sl[n] != st:
                        sl[n] = st
                        libs.append(n)
                elif v == color and ss[n] != st:
                    stack.append(n)
        return stones, libs

    def liberty_count(self, start: int, color: int) -> int:
        board = self.board
        stack = [start]
        st = self._bump()
        ss, sl = self._seen_s, self._seen_l
        count = 0
        while stack:
            i = stack.pop()
            if ss[i] == st:
                continue
            ss[i] = st
            for n in NEIGHBORS[i]:
                v = board[n]
                if v == 0:
                    if sl[n] != st:
                        sl[n] = st
                        count += 1
                elif v == color and ss[n] != st:
                    stack.append(n)
        return count

    def libs_cap(self, start: int, color: int, limit: int = 2) -> tuple[int, int]:
        """Return (nlibs_capped, first_lib_or_-1). Stops once nlibs > limit."""
        board = self.board
        stack = [start]
        st = self._bump()
        ss, sl = self._seen_s, self._seen_l
        count = 0
        first = -1
        while stack:
            i = stack.pop()
            if ss[i] == st:
                continue
            ss[i] = st
            for n in NEIGHBORS[i]:
                v = board[n]
                if v == 0:
                    if sl[n] != st:
                        sl[n] = st
                        if count == 0:
                            first = n
                        count += 1
                        if count > limit:
                            return count, first
                elif v == color and ss[n] != st:
                    stack.append(n)
        return count, first

    def is_legal(self, idx: int, color: int) -> bool:
        """Fast legality: empty-neighbour short-circuit, no capture list."""
        board = self.board
        if board[idx] != 0 or idx == self.ko:
            return False
        opp = 3 - color
        neigh = NEIGHBORS[idx]
        for n in neigh:
            if board[n] == 0:
                return True
        board[idx] = color
        for n in neigh:
            if board[n] == opp and self.libs_cap(n, opp, 0)[0] == 0:
                board[idx] = 0
                return True
        ok = self.libs_cap(idx, color, 0)[0] > 0
        board[idx] = 0
        return ok

    def is_suicide_after(self, idx: int, color: int) -> tuple[bool, list[int]]:
        board = self.board
        if board[idx] != 0 or idx == self.ko:
            return False, []
        opp = 3 - color
        neigh = NEIGHBORS[idx]
        board[idx] = color
        captured: list[int] = []
        seen = self._bump()
        ss = self._seen_s
        for n in neigh:
            if board[n] == opp and ss[n] != seen:
                stones, libs = self.group_libs(n, opp)
                for s in stones:
                    ss[s] = seen
                if not libs:
                    captured.extend(stones)
        for s in captured:
            board[s] = 0
        ok = any(board[n] == 0 for n in neigh) or self.liberty_count(idx, color) > 0
        board[idx] = 0
        for s in captured:
            board[s] = opp
        return ok, captured

    def legal_places(self, hint: Optional[set[int]] = None) -> list[int]:
        color = self.to_play
        board = self.board
        ko = self.ko
        out: list[int] = []
        cands = hint if hint is not None else range(N)
        for idx in cands:
            if board[idx] != 0 or idx == ko:
                continue
            if self.is_legal(idx, color):
                out.append(idx)
        return out

    def _apply_place(self, move: int, color: int, track_hash: bool) -> tuple[list[int], int, int]:
        """Place stone; return (captured, cap_delta, new_ko)."""
        board = self.board
        opp = 3 - color
        board[move] = color
        if track_hash:
            self.zhash ^= Z_STONE[move][color]
        captured: list[int] = []
        seen = self._bump()
        ss = self._seen_s
        for n in NEIGHBORS[move]:
            if board[n] == opp and ss[n] != seen:
                stones, libs = self.group_libs(n, opp)
                for s in stones:
                    ss[s] = seen
                if not libs:
                    captured.extend(stones)
        for s in captured:
            board[s] = 0
            if track_hash:
                self.zhash ^= Z_STONE[s][opp]
        cap_delta = len(captured)
        new_ko = -1
        if cap_delta == 1 and self.libs_cap(move, color, 1)[0] == 1:
            new_ko = captured[0]
        return captured, cap_delta, new_ko

    def play(self, move: int) -> None:
        board = self.board
        color = self.to_play
        prev_ko, prev_pass, prev_hash = self.ko, self.pass_count, self.zhash
        captured: list[int] = []
        cap_delta = 0
        new_ko = -1
        self.zhash ^= Z_TO_PLAY[color] ^ Z_KO[prev_ko + 1]
        if move == PASS:
            self.pass_count = prev_pass + 1
            self.ko = -1
        else:
            captured, cap_delta, new_ko = self._apply_place(move, color, True)
            self.captures[color] += cap_delta
            self.ko = new_ko
            self.pass_count = 0
        self.zhash ^= Z_KO[self.ko + 1]
        self.to_play = 3 - color
        self.zhash ^= Z_TO_PLAY[self.to_play]
        self.move_number += 1
        self._stack.append((move, color, prev_ko, prev_pass, captured, cap_delta, prev_hash, True))

    def play_fast(self, move: int) -> None:
        """Playout play: skip zobrist."""
        color = self.to_play
        prev_ko, prev_pass = self.ko, self.pass_count
        captured: list[int] = []
        cap_delta = 0
        if move == PASS:
            self.pass_count = prev_pass + 1
            self.ko = -1
        else:
            captured, cap_delta, new_ko = self._apply_place(move, color, False)
            self.captures[color] += cap_delta
            self.ko = new_ko
            self.pass_count = 0
        self.to_play = 3 - color
        self.move_number += 1
        self._stack.append((move, color, prev_ko, prev_pass, captured, cap_delta, 0, False))

    def undo(self) -> None:
        item = self._stack.pop()
        move, color, prev_ko, prev_pass, captured, cap_delta, prev_hash, tracked = item
        self.to_play = color
        self.ko = prev_ko
        self.pass_count = prev_pass
        self.move_number -= 1
        if tracked:
            self.zhash = prev_hash
        if move == PASS:
            return
        self.board[move] = 0
        opp = 3 - color
        for s in captured:
            self.board[s] = opp
        self.captures[color] -= cap_delta

    def terminal(self, pts: int = 2) -> bool:
        return self.pass_count >= pts or self.move_number >= TECH_CAP

    def chinese_diff(self, komi: float = 7.5, dead: Optional[set[int]] = None) -> float:
        board = self.board
        dead = dead or set()
        seen = [False] * N
        ba = wa = 0
        for i in range(N):
            if i in dead:
                continue
            v = board[i]
            if v == BLACK:
                ba += 1
            elif v == WHITE:
                wa += 1
            elif not seen[i]:
                stack = [i]
                region: list[int] = []
                borders: set[int] = set()
                while stack:
                    x = stack.pop()
                    if seen[x]:
                        continue
                    seen[x] = True
                    if board[x] != 0 or x in dead:
                        continue
                    region.append(x)
                    for n in NEIGHBORS[x]:
                        if n in dead:
                            continue
                        bv = board[n]
                        if bv == 0:
                            if not seen[n]:
                                stack.append(n)
                        else:
                            borders.add(bv)
                if borders == {BLACK}:
                    ba += len(region)
                elif borders == {WHITE}:
                    wa += len(region)
        for i in dead:
            v = board[i]
            if v == BLACK:
                wa += 1
            elif v == WHITE:
                ba += 1
        return ba - wa - komi


# ---------------------------------------------------------------------------
# Tactics
# ---------------------------------------------------------------------------


def groups(pos: Position, color: int) -> list[tuple[list[int], list[int]]]:
    board = pos.board
    seen: set[int] = set()
    out: list[tuple[list[int], list[int]]] = []
    for i in range(N):
        if board[i] != color or i in seen:
            continue
        stones, libs = pos.group_libs(i, color)
        seen.update(stones)
        out.append((stones, libs))
    return out


def atari_groups(pos: Position, color: int) -> list[tuple[list[int], int]]:
    return [(s, libs[0]) for s, libs in groups(pos, color) if len(libs) == 1]


def is_true_eye(pos: Position, idx: int, color: int) -> bool:
    board = pos.board
    if board[idx] != 0:
        return False
    opp = 3 - color
    for n in NEIGHBORS[idx]:
        if board[n] != color:
            return False
    bad = sum(1 for n in DIAGS[idx] if board[n] == opp)
    deg = len(NEIGHBORS[idx])
    return bad == 0 if deg <= 3 else bad <= 1


def is_own_eye(pos: Position, idx: int, color: int) -> bool:
    if is_true_eye(pos, idx, color):
        return True
    board = pos.board
    if board[idx] != 0:
        return False
    opp = 3 - color
    own = empties = 0
    for n in NEIGHBORS[idx]:
        v = board[n]
        if v == color:
            own += 1
        elif v == opp:
            return False
        else:
            empties += 1
    deg = len(NEIGHBORS[idx])
    if own == deg:
        return True
    if own >= deg - 1 and empties <= 1:
        return sum(1 for n in DIAGS[idx] if board[n] == opp) == 0
    return False


def capture_moves(pos: Position, legal: list[int]) -> list[int]:
    legal_set = set(legal)
    scored: list[tuple[int, int]] = []
    seen: set[int] = set()
    for stones, lib in atari_groups(pos, 3 - pos.to_play):
        if lib in legal_set and lib not in seen:
            seen.add(lib)
            scored.append((-len(stones), lib))
    scored.sort()
    return [m for _, m in scored]


def save_moves(pos: Position, legal: list[int]) -> list[int]:
    legal_set = set(legal)
    out: list[int] = []
    seen: set[int] = set()
    for stones, lib in atari_groups(pos, pos.to_play):
        if lib in legal_set and lib not in seen:
            ok, _ = pos.is_suicide_after(lib, pos.to_play)
            if ok:
                seen.add(lib)
                out.append(lib)
    return out


def self_atari_bad(pos: Position, move: int) -> bool:
    color = pos.to_play
    ok, captured = pos.is_suicide_after(move, color)
    if not ok:
        return True
    if captured:
        return False
    pos.play(move)
    _, libs = pos.group_libs(move, color)
    n = len(libs)
    pos.undo()
    return n <= 1


def two_lib_threats(pos: Position, legal: list[int]) -> list[int]:
    legal_set = set(legal)
    scores: dict[int, float] = {}
    for stones, libs in groups(pos, 3 - pos.to_play):
        if len(libs) != 2:
            continue
        w = 2.0 + 0.35 * len(stones)
        for lib in libs:
            if lib in legal_set and not is_own_eye(pos, lib, pos.to_play):
                scores[lib] = scores.get(lib, 0.0) + w
    return sorted(scores, key=lambda m: -scores[m])


def eye_score(pos: Position, libs: list[int], color: int) -> float:
    e = 0.0
    for lib in libs:
        if is_true_eye(pos, lib, color):
            e += 1.0
        elif is_own_eye(pos, lib, color):
            e += 0.5
    return e


def estimate_dead(pos: Position) -> set[int]:
    dead: set[int] = set()
    for color in (BLACK, WHITE):
        for stones, libs in groups(pos, color):
            eyes = eye_score(pos, libs, color)
            nlib = len(libs)
            if eyes >= 1.8:
                continue
            if nlib == 0 or (nlib == 1 and eyes < 0.9):
                dead.update(stones)
            elif nlib == 2 and eyes < 0.5 and len(stones) <= 6:
                surr = 0
                for lib in libs:
                    if sum(1 for n in NEIGHBORS[lib] if pos.board[n] == 3 - color) >= 2:
                        surr += 1
                if surr == 2:
                    dead.update(stones)
    return dead


def evaluate(pos: Position, komi: float) -> float:
    dead = estimate_dead(pos)
    score = pos.chinese_diff(komi, dead)
    board = pos.board
    seen = [False] * N
    for i in range(N):
        v = board[i]
        if v == 0 or seen[i] or i in dead:
            continue
        stones, libs = pos.group_libs(i, v)
        for s in stones:
            seen[s] = True
        nlib, nst = len(libs), len(stones)
        eyes = eye_score(pos, libs, v)
        if eyes >= 2.0:
            life = 7.0 + 0.2 * nst
        elif eyes >= 1.0:
            life = 2.5 + 0.25 * min(nlib, 5)
        else:
            if nlib <= 1:
                life = -(9.0 + 0.7 * nst)
            elif nlib == 2:
                life = -(3.0 + 0.2 * nst)
            else:
                life = 0.15 * min(nlib, 7)
            if nst >= 5 and eyes < 1.0 and nlib <= 4:
                life -= 2.0
        term = life + 0.08 * nst + 1.2 * eyes
        score += term if v == BLACK else -term
    for i in range(N):
        if board[i] != 0 or i in dead:
            continue
        b = w = 0.0
        for n in NEIGHBORS[i]:
            if n in dead:
                continue
            if board[n] == BLACK:
                b += 1
            elif board[n] == WHITE:
                w += 1
        if b and not w:
            score += 0.3 * b
        elif w and not b:
            score -= 0.3 * w
    return score


def side_diff(pos: Position, komi: float, color: int) -> float:
    d = pos.chinese_diff(komi, estimate_dead(pos))
    return d if color == BLACK else -d


def urgent(pos: Position, legal: list[int]) -> list[int]:
    caps = capture_moves(pos, legal)
    saves = save_moves(pos, legal)
    threats = two_lib_threats(pos, legal)
    ordered: list[int] = []
    seen: set[int] = set()
    for m in caps + saves + threats[:8]:
        if m in legal and m not in seen:
            if m not in caps and self_atari_bad(pos, m):
                continue
            seen.add(m)
            ordered.append(m)
    return ordered


def move_priority(pos: Position, move: int, last: int) -> float:
    if move == PASS:
        return -1e9
    color = pos.to_play
    score = CENTER[move]
    if move in OPENING_BAD and pos.move_number < 8:
        score -= 10.0
    if last >= 0:
        lr, lc = to_rc(last)
        r, c = to_rc(move)
        d = abs(lr - r) + abs(lc - c)
        if 1 <= d <= 2:
            score += 4.5 - 0.7 * d
    own = opp = 0
    for n in NEIGHBORS[move]:
        v = pos.board[n]
        if v == color:
            own += 1
        elif v:
            opp += 1
    score += 0.8 * own + 1.3 * opp
    if is_true_eye(pos, move, color):
        score -= 200.0
    elif is_own_eye(pos, move, color):
        score -= 35.0
    ok, captured = pos.is_suicide_after(move, color)
    if ok and captured:
        score += 16.0 + 3.5 * len(captured)
    elif ok and self_atari_bad(pos, move):
        score -= 12.0
    return score


def ordered_moves(
    pos: Position,
    hint: Optional[set[int]],
    last: int,
    include_pass: bool,
    max_places: int = 40,
) -> list[int]:
    places = pos.legal_places(hint)
    urg = urgent(pos, places)
    urg_set = set(urg)
    filtered = [m for m in places if m in urg_set or not is_true_eye(pos, m, pos.to_play)]
    if not filtered:
        filtered = places[:]
    soft = [m for m in filtered if m in urg_set or not is_own_eye(pos, m, pos.to_play)]
    if soft:
        filtered = soft
    safe = [m for m in filtered if m in urg_set or not self_atari_bad(pos, m)]
    if safe:
        filtered = safe
    ordered: list[int] = []
    seen: set[int] = set()
    for m in urg:
        if m in filtered and m not in seen:
            seen.add(m)
            ordered.append(m)
    rest = [m for m in filtered if m not in seen]
    rest.sort(key=lambda m: move_priority(pos, m, last), reverse=True)
    ordered.extend(rest)
    if len(ordered) > max_places:
        ordered = ordered[: max(len(urg_set), max_places)]
    if include_pass:
        ordered.append(PASS)
    return ordered


def endgame_points(pos: Position, legal: list[int]) -> list[int]:
    color = pos.to_play
    opp = 3 - color
    scored: list[tuple[float, int]] = []
    for m in legal:
        if is_true_eye(pos, m, color) or self_atari_bad(pos, m):
            continue
        own = opp_n = 0
        for n in NEIGHBORS[m]:
            v = pos.board[n]
            if v == color:
                own += 1
            elif v == opp:
                opp_n += 1
        s = 0.0
        if own and opp_n:
            s += 6.0
        elif own:
            s += 3.0 + 0.4 * own
        elif opp_n:
            s += 4.0 + 0.5 * opp_n
        if is_own_eye(pos, m, color):
            s -= 8.0
        ok, cap = pos.is_suicide_after(m, color)
        if ok and cap:
            s += 18.0 + 4.0 * len(cap)
        if s > 0:
            scored.append((s, m))
    scored.sort(reverse=True)
    return [m for _, m in scored]


def should_refuse_pass(pos: Position, komi: float) -> bool:
    places = pos.legal_places()
    if capture_moves(pos, places) or save_moves(pos, places):
        return True
    for stones, libs in groups(pos, 3 - pos.to_play):
        if len(libs) <= 2 and eye_score(pos, libs, 3 - pos.to_play) < 1.5:
            return True
    for stones, libs in groups(pos, pos.to_play):
        if len(libs) <= 2 and len(stones) >= 2 and eye_score(pos, libs, pos.to_play) < 1.5:
            return True
    empties = sum(1 for v in pos.board if v == 0)
    if empties > 12 and pos.pass_count == 0:
        return True
    return False


def safe_to_pass(pos: Position, komi: float) -> bool:
    """Require clear lead before PASS (Black lost by 0.25 after thin PASS)."""
    if should_refuse_pass(pos, komi):
        return False
    diff = side_diff(pos, komi, pos.to_play)
    need = 3.5 if pos.to_play == BLACK else 2.0
    if diff < need:
        return False
    places = pos.legal_places()
    if endgame_points(pos, places) and diff < need + 3.0:
        return False
    return True


# ---------------------------------------------------------------------------
# Playout (Michi-style: never scan full legal_places)
# ---------------------------------------------------------------------------


def _eyeish(board: list[int], idx: int, color: int) -> bool:
    """Cheap false-eye / true-eye filter for playouts."""
    opp = 3 - color
    for n in NEIGHBORS[idx]:
        if board[n] != color:
            return False
    bad = 0
    for n in DIAGS[idx]:
        if board[n] == opp:
            bad += 1
    deg = len(NEIGHBORS[idx])
    return bad == 0 if deg <= 3 else bad <= 1


def _self_atari_fast(pos: Position, move: int, color: int) -> bool:
    """Approx self-atari without stack play/undo."""
    board = pos.board
    opp = 3 - color
    neigh = NEIGHBORS[move]
    board[move] = color
    for n in neigh:
        if board[n] == opp and pos.libs_cap(n, opp, 0)[0] == 0:
            board[move] = 0
            return False
    nlib = pos.libs_cap(move, color, 1)[0]
    board[move] = 0
    return nlib <= 1


def playout_move(pos: Position, last: int, prev: int = -1) -> int:
    color = pos.to_play
    opp = 3 - color
    board = pos.board
    ko = pos.ko

    if random.random() < PROB_CAPTURE:
        # Local atari capture / save using early-exit liberty scan
        for src in (last, prev):
            if src < 0:
                continue
            for pt in NEIGH8[src]:
                v = board[pt]
                if v == opp:
                    nlib, lib = pos.libs_cap(pt, opp, 1)
                    if nlib == 1 and lib >= 0 and lib != ko and board[lib] == 0:
                        if pos.is_legal(lib, color):
                            return lib
                elif v == color:
                    nlib, lib = pos.libs_cap(pt, color, 1)
                    if nlib == 1 and lib >= 0 and lib != ko and board[lib] == 0:
                        if pos.is_legal(lib, color) and (
                            not _self_atari_fast(pos, lib, color) or random.random() > PROB_SSAREJECT
                        ):
                            return lib
            # also check the stone itself if last was a stone
            v = board[src]
            if v == opp:
                nlib, lib = pos.libs_cap(src, opp, 1)
                if nlib == 1 and lib >= 0 and lib != ko and board[lib] == 0 and pos.is_legal(lib, color):
                    return lib
            elif v == color:
                nlib, lib = pos.libs_cap(src, color, 1)
                if nlib == 1 and lib >= 0 and lib != ko and board[lib] == 0:
                    if pos.is_legal(lib, color) and (
                        not _self_atari_fast(pos, lib, color) or random.random() > PROB_SSAREJECT
                    ):
                        return lib

        # two-lib nudge
        if last >= 0 and random.random() < 0.5:
            for pt in NEIGH8[last]:
                if board[pt] != opp:
                    continue
                nlib, first = pos.libs_cap(pt, opp, 2)
                if nlib == 2:
                    # re-scan both libs cheaply
                    _, libs = pos.group_libs(pt, opp)
                    random.shuffle(libs)
                    for lib in libs:
                        if lib != ko and not _self_atari_fast(pos, lib, color) and pos.is_legal(lib, color):
                            return lib
                    break

    if random.random() < PROB_PAT3 and last >= 0:
        pts = [last] + NEIGH8[last]
        if prev >= 0:
            pts = pts + [prev] + NEIGH8[prev]
        random.shuffle(pts)
        for p in pts:
            if board[p] != 0 or p == ko:
                continue
            if not matches_pat3(board, p, color):
                continue
            if not pos.is_legal(p, color):
                continue
            if _self_atari_fast(pos, p, color) and random.random() < PROB_SSAREJECT:
                continue
            return p

    # Random empty point — Michi-style linear probe, no full legal scan
    start = random.randrange(N)
    for off in range(N):
        m = (start + off) % N
        if board[m] != 0 or m == ko:
            continue
        if _eyeish(board, m, color):
            continue
        if not pos.is_legal(m, color):
            continue
        if _self_atari_fast(pos, m, color) and random.random() < PROB_RSAREJECT:
            continue
        return m
    return PASS


def _area_diff_fast(pos: Position, komi: float) -> float:
    """Territory-free stone count + owner flood; no dead-stone estimate."""
    return pos.chinese_diff(komi, None)


def playout(pos: Position, komi: float, pts: int, last: int, max_plies: int = 48) -> tuple[float, list[int], list[int]]:
    start = len(pos._stack)
    cur, prev = last, -1
    passes = 0
    amaf_b: list[int] = []
    amaf_w: list[int] = []
    seen_b = [False] * N
    seen_w = [False] * N
    for _ in range(max_plies):
        if pos.pass_count >= pts or pos.move_number >= TECH_CAP:
            break
        color = pos.to_play
        mv = playout_move(pos, cur, prev)
        if mv == PASS:
            passes += 1
        else:
            passes = 0
        pos.play_fast(mv)
        if mv != PASS:
            if color == BLACK:
                if not seen_b[mv]:
                    seen_b[mv] = True
                    amaf_b.append(mv)
            else:
                if not seen_w[mv]:
                    seen_w[mv] = True
                    amaf_w.append(mv)
            prev, cur = cur, mv
        if passes >= 2:
            break
    diff = _area_diff_fast(pos, komi)
    while len(pos._stack) > start:
        pos.undo()
    if diff > 0.5:
        val = 1.0
    elif diff < -0.5:
        val = -1.0
    else:
        val = math.tanh(diff / 4.0)
    return val, amaf_b, amaf_w


# ---------------------------------------------------------------------------
# Short AB
# ---------------------------------------------------------------------------

NEG, POS = -1e18, 1e18


def root_tactical(pos: Position, komi: float, pts: int, last: int, budget: float) -> Optional[int]:
    places = pos.legal_places()
    caps = capture_moves(pos, places)
    saves = save_moves(pos, places)
    if not caps and not saves:
        return None
    deadline = time.perf_counter() + budget
    moves = ordered_moves(pos, None, last, False, 14)
    root = pos.to_play
    best_m, best_v = moves[0], NEG if root == BLACK else POS

    def ab(depth: int, alpha: float, beta: float, last_m: int) -> float:
        if time.perf_counter() >= deadline or depth <= 0 or pos.terminal(pts):
            return evaluate(pos, komi)
        ms = urgent(pos, pos.legal_places())[:10] or ordered_moves(pos, None, last_m, False, 8)
        if not ms:
            ms = [PASS]
        if pos.to_play == BLACK:
            v = NEG
            for m in ms:
                pos.play(m)
                v = max(v, ab(depth - 1, alpha, beta, m if m != PASS else last_m))
                pos.undo()
                alpha = max(alpha, v)
                if alpha >= beta:
                    break
            return v if v > NEG / 2 else evaluate(pos, komi)
        v = POS
        for m in ms:
            pos.play(m)
            v = min(v, ab(depth - 1, alpha, beta, m if m != PASS else last_m))
            pos.undo()
            beta = min(beta, v)
            if alpha >= beta:
                break
        return v if v < POS / 2 else evaluate(pos, komi)

    for m in moves:
        if time.perf_counter() >= deadline:
            break
        pos.play(m)
        val = ab(2, NEG, POS, m if m != PASS else last)
        pos.undo()
        if root == BLACK and val > best_v:
            best_v, best_m = val, m
        elif root == WHITE and val < best_v:
            best_v, best_m = val, m
    return best_m


# ---------------------------------------------------------------------------
# MCTS RAVE
# ---------------------------------------------------------------------------


class Node:
    __slots__ = (
        "move", "parent", "children", "untried",
        "wins", "visits", "prior", "pw", "pv", "rw", "rv", "to_play",
    )

    def __init__(self, move: int, parent: Optional["Node"], prior: float, to_play: int, pw: float = 0.0, pv: float = 0.0):
        self.move = move
        self.parent = parent
        self.children: list[Node] = []
        self.untried: Optional[list[int]] = None
        self.wins = 0.0
        self.visits = 0
        self.prior = prior
        self.pw = pw
        self.pv = pv
        self.rw = 0.0
        self.rv = 0
        self.to_play = to_play


def rave_urgency(ch: Node) -> float:
    v = ch.visits + ch.pv
    q = (ch.wins + ch.pw) / (v + 1e-9)
    if ch.rv <= 0:
        return q
    beta = ch.rv / (ch.rv + v + v * ch.rv / RAVE_EQUIV + 1e-9)
    return (1.0 - beta) * q + beta * (ch.rw / ch.rv)


def cfg_dist(board: list[int], last: int) -> list[int]:
    dist = [0] * N
    if last < 0:
        return dist
    q = [last]
    dist[last] = 1
    head = 0
    while head < len(q):
        x = q[head]
        head += 1
        for n in NEIGH8[x]:
            if dist[n] == 0 and (board[n] == 0 or n == last):
                dist[n] = dist[x] + 1
                q.append(n)
    return dist


def virtual_prior(pos: Position, move: int, last: int, urg: set[int], caps: set[int], saves: set[int]) -> tuple[float, float]:
    pw = PRIOR_EVEN * 0.5
    pv = float(PRIOR_EVEN)
    if move == PASS:
        return (0.05 * PRIOR_EVEN, float(PRIOR_EVEN + 20)) if not safe_to_pass(pos, 7.5) else (0.2 * PRIOR_EVEN, float(PRIOR_EVEN))
    color = pos.to_play
    if move in caps:
        ok, captured = pos.is_suicide_after(move, color)
        add = PRIOR_CAPTURE_MANY if ok and len(captured) >= 2 else PRIOR_CAPTURE_ONE
        pw += add
        pv += add
    if move in saves:
        pw += PRIOR_CAPTURE_ONE
        pv += PRIOR_CAPTURE_ONE
    if move in urg:
        pw += 8
        pv += 8
    if matches_pat3(pos.board, move, color):
        pw += PRIOR_PAT3
        pv += PRIOR_PAT3
    if last >= 0:
        d = cfg_dist(pos.board, last)[move]
        if 1 <= d <= 3:
            pw += PRIOR_CFG[d - 1]
            pv += PRIOR_CFG[d - 1]
    if self_atari_bad(pos, move) and move not in caps:
        pv += PRIOR_SELFATARI
    if is_true_eye(pos, move, color):
        return 0.01, 40.0
    if move in OPENING_BAD and pos.move_number < 10:
        pv += 14
    return pw, pv


def mcts(
    root_pos: Position,
    budget_s: float,
    komi: float,
    pts: int,
    hint: Optional[set[int]],
    last: int,
    pass_allowed: bool,
) -> tuple[int, int]:
    root_player = root_pos.to_play
    moves = ordered_moves(root_pos, hint, last, pass_allowed, 45)
    if not moves:
        return PASS, 0
    if len(moves) == 1:
        return moves[0], 1

    places = [m for m in moves if m != PASS]
    legal_set = set(places)
    book = []
    if root_pos.move_number <= 12:
        key = tuple(root_pos.board) + (root_pos.to_play,)
        book = [m for m in BOOK.get(key, []) if m in legal_set and m not in OPENING_BAD]
    hot = bool(atari_groups(root_pos, root_player) or atari_groups(root_pos, 3 - root_player))
    if book and root_pos.move_number <= 3 and not hot and budget_s < 2.5:
        return book[0], 0

    caps = capture_moves(root_pos, places)
    saves = save_moves(root_pos, places)
    deadline = time.perf_counter() + budget_s

    ab_move = None
    if hot or caps or saves:
        ab_move = root_tactical(root_pos, komi, pts, last, min(budget_s * 0.1, 0.8))

    mcts_moves = [m for m in moves if not (m == PASS and not safe_to_pass(root_pos, komi))]
    if not mcts_moves:
        mcts_moves = places[:] or [PASS]

    boost: list[int] = []
    for m in (ab_move, *(book[:2]), *caps[:2], *saves[:2]):
        if m is not None and m in mcts_moves and m not in boost:
            boost.append(m)
    for m in boost:
        mcts_moves.remove(m)
        mcts_moves.insert(0, m)

    urg = set(urgent(root_pos, places))
    caps_set, saves_set = set(caps), set(saves)
    raw = []
    for m in mcts_moves:
        p = max(0.1, move_priority(root_pos, m, last))
        if m in urg:
            p += 8
        if m == PASS:
            p = 0.05
        raw.append(p)
    s = sum(raw) or 1.0
    priors = [x / s for x in raw]

    root = Node(PASS, None, 1.0, 3 - root_player)
    for m, pr in zip(mcts_moves, priors):
        pw, pv = virtual_prior(root_pos, m, last, urg, caps_set, saves_set)
        root.children.append(Node(m, root, pr, root_player, pw, pv))

    def child_moves(pos: Position, last_m: int) -> list[int]:
        mv = ordered_moves(pos, None, last_m, True, 22)
        if not safe_to_pass(pos, komi):
            mv2 = [x for x in mv if x != PASS]
            if mv2:
                mv = mv2
        return mv

    iters = 0
    while time.perf_counter() < deadline:
        node = root
        path = [root]
        path_moves: list[int] = []
        amaf_b: list[int] = []
        amaf_w: list[int] = []

        while node.children:
            if node.untried:
                break
            kids = list(node.children)
            random.shuffle(kids)
            # wins/rave are root_player-centric: max for us, min for opponent
            if (3 - node.to_play) == root_player:
                node = max(kids, key=rave_urgency)
            else:
                node = min(kids, key=rave_urgency)
            root_pos.play(node.move)
            path.append(node)
            path_moves.append(node.move)
            if node.move != PASS:
                (amaf_b if node.to_play == BLACK else amaf_w).append(node.move)
            if root_pos.terminal(pts):
                break
            if node.untried is None:
                lm = path_moves[-1] if path_moves[-1] != PASS else last
                node.untried = child_moves(root_pos, lm)

        if node.untried and not root_pos.terminal(pts):
            m = node.untried.pop(0)
            root_pos.play(m)
            path_moves.append(m)
            mover = root_pos._stack[-1][1]
            child = Node(m, node, 0.4, mover, PRIOR_EVEN * 0.5, float(PRIOR_EVEN))
            if m != PASS:
                (amaf_b if child.to_play == BLACK else amaf_w).append(m)
            node.children.append(child)
            path.append(child)
            node = child

        sim_last = path_moves[-1] if path_moves and path_moves[-1] != PASS else last
        if root_pos.terminal(pts):
            diff = root_pos.chinese_diff(komi, estimate_dead(root_pos))
            result = 1.0 if diff > 0.1 else (-1.0 if diff < -0.1 else 0.0)
            pl_b, pl_w = [], []
        else:
            static = math.tanh(evaluate(root_pos, komi) / 16.0)
            pl, pl_b, pl_w = playout(root_pos, komi, pts, sim_last)
            result = 0.25 * static + 0.75 * pl

        for _ in path_moves:
            root_pos.undo()

        for nd in path:
            nd.visits += 1
            if root_player == BLACK:
                nd.wins += (result + 1.0) * 0.5
            else:
                nd.wins += (1.0 - result) * 0.5

        ab = set(amaf_b) | set(pl_b)
        aw = set(amaf_w) | set(pl_w)
        wr = (result + 1.0) * 0.5 if root_player == BLACK else (1.0 - result) * 0.5

        def apply_rave(children: list[Node]) -> None:
            for ch in children:
                if ch.move == PASS:
                    continue
                if ch.to_play == BLACK and ch.move in ab:
                    ch.rv += 1
                    ch.rw += wr
                elif ch.to_play == WHITE and ch.move in aw:
                    ch.rv += 1
                    ch.rw += wr

        apply_rave(root.children)
        if len(path) >= 2:
            apply_rave(path[1].children)

        iters += 1
        if iters > 400000:
            break

    best = mcts_moves[0]
    if root.children:
        best = max(root.children, key=lambda c: (c.visits, c.wins)).move

    if best == PASS and not safe_to_pass(root_pos, komi):
        if caps:
            return caps[0], iters
        eg = endgame_points(root_pos, places)
        if eg:
            return eg[0], iters
        urg_l = urgent(root_pos, places)
        if urg_l:
            return urg_l[0], iters
        if places:
            return places[0], iters
    if best != PASS and is_true_eye(root_pos, best, root_player):
        for m in mcts_moves:
            if m != PASS and not is_true_eye(root_pos, m, root_player):
                return m, iters
    if saves and best not in saves and best not in caps and len(saves) == 1:
        for stones, lib in atari_groups(root_pos, root_player):
            if lib == saves[0] and len(stones) >= 2:
                return saves[0], iters
    return best, iters


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def last_from_obs(obs: dict) -> int:
    la = obs.get("last_action")
    if isinstance(la, dict) and la.get("kind") == "PLACE":
        r, c = int(la["row"]), int(la["col"])
        if 0 <= r < SIZE and 0 <= c < SIZE:
            return from_rc(r, c)
    return -1


def decide_go9(request: dict) -> dict:
    obs = request["observation"]
    board2d = obs["board"]
    if int(obs.get("size") or len(board2d)) != SIZE:
        return {"kind": "PASS"}

    board = flatten(board2d)
    to_play = int(obs.get("current_player") or request.get("player") or BLACK)
    ko = parse_ko(obs.get("ko_point"))
    pass_count = int(obs.get("pass_count") or 0)
    move_number = int(obs.get("move_number") or 0)
    komi = float(obs["komi"]) if obs.get("komi") is not None else 7.5
    pts = int(obs.get("passes_to_score") or 2)
    pass_forbidden = bool(obs.get("pass_forbidden_after_dispute"))
    available = obs.get("available_actions")
    if isinstance(available, list) and available:
        pass_ok = ("PASS" in available) and not pass_forbidden
    else:
        pass_ok = not pass_forbidden

    caps_raw = obs.get("captures") or {}
    captures = [0, 0, 0]
    try:
        captures[1] = int(caps_raw.get("1", caps_raw.get(1, 0)))
        captures[2] = int(caps_raw.get("2", caps_raw.get(2, 0)))
    except Exception:
        pass

    hint = parse_legal(obs)
    last = last_from_obs(obs)
    pos = Position(board, to_play, ko, pass_count, captures, move_number)
    tlim = int(request.get("time_limit_ms") or 10000)
    budget_ms = max(200, min(int(tlim * 0.94), 9400))

    # Instant tengen (any move_number if empty)
    if all(v == 0 for v in board):
        t = from_rc(4, 4)
        if hint is None or t in hint:
            return {"kind": "PLACE", "row": 4, "col": 4}

    places = pos.legal_places(hint)
    if not places:
        return {"kind": "PASS"} if pass_ok else {"kind": "PASS"}

    # Quiet early book only on short clocks
    if move_number <= 6 and tlim < 3000:
        key = tuple(pos.board) + (pos.to_play,)
        cands = [m for m in BOOK.get(key, []) if m in places and m not in OPENING_BAD]
        if cands and not atari_groups(pos, to_play) and not atari_groups(pos, 3 - to_play):
            r, c = to_rc(cands[0])
            return {"kind": "PLACE", "row": r, "col": c}

    caps = capture_moves(pos, places)
    saves = save_moves(pos, places)
    if caps and not saves:
        r, c = to_rc(caps[0])
        return {"kind": "PLACE", "row": r, "col": c}
    if saves and not caps and len(saves) == 1:
        r, c = to_rc(saves[0])
        return {"kind": "PLACE", "row": r, "col": c}

    # After opponent PASS: never thin mutual-PASS
    if pass_ok and pass_count >= 1:
        if caps:
            r, c = to_rc(caps[0])
            return {"kind": "PLACE", "row": r, "col": c}
        if not safe_to_pass(pos, komi):
            urg = urgent(pos, places)
            eg = endgame_points(pos, places)
            pick = urg[0] if urg else (eg[0] if eg else None)
            if pick is None:
                alts = [m for m in places if not is_true_eye(pos, m, to_play) and not self_atari_bad(pos, m)]
                if alts:
                    pick = max(alts, key=lambda m: move_priority(pos, m, last))
            if pick is not None:
                r, c = to_rc(pick)
                return {"kind": "PLACE", "row": r, "col": c}
        else:
            return {"kind": "PASS"}

    move, _ = mcts(pos, budget_ms / 1000.0, komi, pts, hint, last, pass_ok)

    if move == PASS:
        if pass_ok and safe_to_pass(pos, komi):
            return {"kind": "PASS"}
        eg = endgame_points(pos, places)
        if eg:
            r, c = to_rc(eg[0])
            return {"kind": "PLACE", "row": r, "col": c}
        ordered = ordered_moves(pos, hint, last, False)
        if ordered:
            r, c = to_rc(ordered[0])
            return {"kind": "PLACE", "row": r, "col": c}
        return {"kind": "PASS"}

    if hint is not None and move not in hint:
        urg = urgent(pos, places)
        move = urg[0] if urg else max(places, key=lambda m: move_priority(pos, m, last))

    if is_true_eye(pos, move, to_play):
        alts = [m for m in places if not is_true_eye(pos, m, to_play) and not self_atari_bad(pos, m)]
        if alts:
            move = max(alts, key=lambda m: move_priority(pos, m, last))

    r, c = to_rc(move)
    return {"kind": "PLACE", "row": r, "col": c}


def decide(request: dict) -> dict:
    if request.get("game", "go9") != "go9":
        return {"kind": "PASS"}
    return decide_go9(request)


def main() -> None:
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        request = json.loads(raw)
        action = decide(request)
        print(
            json.dumps(
                {
                    "protocol": "arena.v1",
                    "request_id": request["request_id"],
                    "type": "move_response",
                    "action": action,
                },
                separators=(",", ":"),
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
