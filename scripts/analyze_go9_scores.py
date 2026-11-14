#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "http://139.196.148.174/api"
OUT = Path(__file__).resolve().parents[1] / "docs" / "arena_go9_analysis.md"


def get(path: str, params: dict | None = None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    go9 = next(g for g in get("/games")["data"] if g["type"] == "go9")
    weights = go9["benchmark"]["weights"]
    lb = get("/leaderboards/best", {"game": "go9"})["data"]["list"]
    matches = get("/matches", {"game": "go9", "limit": 100})["data"]

    lines: list[str] = []
    lines.append("# go9 加分规则与棋谱分析")
    lines.append("")
    lines.append(f"抓取时间以本机为准。score_rule=`{go9['benchmark']['score_rule_version']}`")
    lines.append("")
    lines.append("## 现行 weights（API）")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(weights, ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("### 字段含义（结合排行榜实数反推）")
    lines.append("")
    lines.append("| 项 | API 字段 | 排行榜合计字段 | 说明 |")
    lines.append("|----|----------|----------------|------|")
    lines.append("| 胜局底分 | win_base_per_match=1000 | wins×1000 | 每胜一局 +1000 |")
    lines.append("| 胜局额外 | win_base_extra=1 | （可能并入别处） | 名义存在 |")
    lines.append("| 和棋 | draw_points=300 | draws | 和棋分 |")
    lines.append("| 提子优势 | advantage_capture_max=150 + capture_points_per_stone=10 + uncapped=1 | capture_total | **提子按子加分且不封顶**（关键变点） |")
    lines.append("| 目差优势 | advantage_margin_max=250 | margin_total | 赢子/目差相关，有上限 |")
    lines.append("| 效率 | efficiency_max=150 | speed_bonus_total | 用时/手数效率 |")
    lines.append("| 稳定 | stability_bonus=50 | survival? | 未见单独大额 |")
    lines.append("| 违法惩罚 | violation_penalty=100 | （扣在对局） | 非法着等 |")
    lines.append("| 完赛 | completion_bonus=30 | completion_total | 两局完赛约 60 |")
    lines.append("| 领地 | territory_max=100 | territory_total | 领地相关加分 |")
    lines.append("| 战术 | tactical_max=60 | tactical_total | 战术项（两局可叠） |")
    lines.append("| 负局扣子 | loss_penalty_per_stone=10 | loss_penalty_total | 输了按被提/落后扣分 |")
    lines.append("")

    # Reconstruct official_score from components for top rows
    lines.append("## 排行榜分项复算（official_score ≈ 分项之和？）")
    lines.append("")
    lines.append("| rank | name | lang | wins | official | win1000 | capt | margin | terr | tact | comp | speed | loss_pen | sum_parts | gap |")
    lines.append("|------|------|------|------|----------|---------|------|--------|------|------|------|-------|----------|-----------|-----|")
    zzy = None
    for row in lb:
        u = row["user"]
        name = u["display_name"]
        if name == "张子益":
            zzy = row
        win_part = 1000 * int(row.get("wins") or 0) + 300 * int(row.get("draws") or 0)
        parts = [
            win_part,
            int(row.get("capture_total") or 0),
            int(row.get("margin_total") or 0),
            int(row.get("territory_total") or 0),
            int(row.get("tactical_total") or 0),
            int(row.get("completion_total") or 0),
            int(row.get("speed_bonus_total") or 0),
            -int(row.get("loss_penalty_total") or 0),
        ]
        s = sum(parts)
        off = int(row.get("official_score") or 0)
        lines.append(
            f"| {row['rank']} | {name} | {row.get('language')} | {row.get('wins')}-{row.get('losses')} | "
            f"{off} | {win_part} | {parts[1]} | {parts[2]} | {parts[3]} | {parts[4]} | {parts[5]} | "
            f"{parts[6]} | {row.get('loss_penalty_total')} | {s} | {off - s} |"
        )

    lines.append("")
    lines.append("若 `gap` 接近 0，说明 official_score 主要由：**胜局底分 + 提子 + 目差 + 领地 + 战术 + 完赛 + 速度 − 负局扣分** 构成。")
    lines.append("")

    # 张子益
    lines.append("## 张子益（user_id=23）")
    lines.append("")
    if not zzy:
        lines.append("未上榜。")
    else:
        lines.append(
            f"- best submission `{zzy['submission_id']}` | lang=`{zzy['language']}` | "
            f"official_score=**{zzy['official_score']}** | rank=**{zzy['rank']}** | "
            f"W-D-L={zzy['wins']}-{zzy['draws']}-{zzy['losses']}"
        )
        lines.append(
            f"- 分项: capture={zzy['capture_total']} margin={zzy['margin_total']} "
            f"territory={zzy['territory_total']} tactical={zzy['tactical_total']} "
            f"completion={zzy['completion_total']} speed={zzy['speed_bonus_total']} "
            f"loss_pen={zzy['loss_penalty_total']}"
        )
        stats = zzy.get("official_ai_stats") or {}
        lines.append(
            f"- 历史评测: evals={stats.get('evaluation_count')} "
            f"累计 W/D/L={stats.get('wins')}/{stats.get('draws')}/{stats.get('losses')} "
            f"avg={stats.get('average_score')}"
        )
        lines.append(f"- achieved_at(UTC): `{zzy.get('achieved_at')}` → 约北京时间 2026-11-04 23:04")
        lines.append("")
        lines.append("与第1名徐宸博对比缺口：")
        top = lb[0]
        for k in (
            "official_score",
            "capture_total",
            "margin_total",
            "territory_total",
            "tactical_total",
            "speed_bonus_total",
        ):
            lines.append(f"- {k}: 你 {zzy.get(k)} / 第1 {top.get(k)} / 差 {int(top.get(k) or 0) - int(zzy.get(k) or 0)}")

    # matches involving 张子益
    lines.append("")
    lines.append("## 公开棋谱里的「张子益」对局")
    lines.append("")
    zzy_ms = [
        m
        for m in matches
        if "张子益" in (m.get("first_name") or "") or "张子益" in (m.get("second_name") or "")
    ]
    lines.append(f"在最近 {len(matches)} 局公开 matches 中命中 **{len(zzy_ms)}** 局。")
    lines.append("")

    # Also try fetching match detail for top recent wins to understand score object
    lines.append("## 近期对局样本（含 score 明细）")
    lines.append("")
    sample = []
    for m in matches:
        if m.get("detail", {}).get("student_result") == "WIN":
            sample.append(m)
        if len(sample) >= 6:
            break
    if not sample:
        sample = matches[:4]

    for m in sample:
        d = m.get("detail") or {}
        sc = d.get("score") or {}
        lines.append(
            f"### match {m['id']}: {m['first_name']} vs {m['second_name']} "
            f"({d.get('student_side')}/{d.get('student_result')}) reason={m['reason']}"
        )
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(sc, ensure_ascii=False, indent=2)[:3500])
        lines.append("```")
        lines.append("")
        # try full match
        try:
            full = get(f"/matches/{m['id']}")
            data = full.get("data", full)
            # keep events short
            if isinstance(data, dict) and "events" in data:
                ev = data["events"]
                lines.append(f"events_count={len(ev) if isinstance(ev, list) else ev}")
                if isinstance(ev, list) and ev:
                    lines.append("first_event:")
                    lines.append("```json")
                    lines.append(json.dumps(ev[0], ensure_ascii=False, indent=2)[:800])
                    lines.append("```")
                    lines.append("last_event:")
                    lines.append("```json")
                    lines.append(json.dumps(ev[-1], ensure_ascii=False, indent=2)[:800])
                    lines.append("```")
            else:
                lines.append("```json")
                lines.append(json.dumps(data, ensure_ascii=False)[:2000])
                lines.append("```")
        except Exception as e:
            lines.append(f"match detail fail: {e}")
        lines.append("")

    # Strength recommendations aligned to new weights
    lines.append("## 对 bot 的加分导向（按现行 go-score-v4）")
    lines.append("")
    lines.append("1. **先保证双胜**（底分 2000）。你已有 2-0 best。")
    lines.append("2. **提子是最大可拉开分差的项**（`capture_points_uncapped=1`，每子 10 分）。顶名 capture_total=780，你 340——优先杀棋/提净死子，不要早 PASS。")
    lines.append("3. **margin（赢子优势）** 顶名 324 vs 你 40——大胜比险胜分高很多。")
    lines.append("4. **tactical** 顶名打满 120，你 90——双打/征子/救棋等战术触发。")
    lines.append("5. **territory / speed** 次要；别超时、别非法着（violation / loss_penalty）。")
    lines.append("6. 公开页棋谱：http://139.196.148.174/go9 ；复盘接口可试 `/api/matches/{id}`。")

    # list recent public matches compact
    lines.append("")
    lines.append("## 最近公开对局（节选）")
    lines.append("")
    for m in matches[:30]:
        d = m.get("detail") or {}
        lines.append(
            f"- `{m['id']}` {m['first_name']} vs {m['second_name']} | "
            f"{d.get('student_result')} | {m['reason']} | moves={m['events_count']} | "
            f"replay={m.get('has_replay')}"
        )

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", OUT)
    print("matches", len(matches), "zzy_matches", len(zzy_ms))
    if zzy:
        print("zzy rank", zzy["rank"], "score", zzy["official_score"])


if __name__ == "__main__":
    main()
