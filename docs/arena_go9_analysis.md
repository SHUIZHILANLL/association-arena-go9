# go9 加分规则与棋谱分析

抓取时间以本机为准。score_rule=`go-score-v4`

## 现行 weights（API）

```json
{
  "win_base_per_match": 1000,
  "win_base_extra": 1,
  "draw_points": 300,
  "advantage_capture_max": 150,
  "advantage_margin_max": 250,
  "efficiency_max": 150,
  "stability_bonus": 50,
  "violation_penalty": 100,
  "completion_bonus": 30,
  "territory_max": 100,
  "tactical_max": 60,
  "capture_points_per_stone": 10,
  "loss_penalty_per_stone": 10,
  "capture_points_uncapped": 1
}
```

### 字段含义（结合排行榜实数反推）

| 项 | API 字段 | 排行榜合计字段 | 说明 |
|----|----------|----------------|------|
| 胜局底分 | win_base_per_match=1000 | wins×1000 | 每胜一局 +1000 |
| 胜局额外 | win_base_extra=1 | （可能并入别处） | 名义存在 |
| 和棋 | draw_points=300 | draws | 和棋分 |
| 提子优势 | advantage_capture_max=150 + capture_points_per_stone=10 + uncapped=1 | capture_total | **提子按子加分且不封顶**（关键变点） |
| 目差优势 | advantage_margin_max=250 | margin_total | 赢子/目差相关，有上限 |
| 效率 | efficiency_max=150 | speed_bonus_total | 用时/手数效率 |
| 稳定 | stability_bonus=50 | survival? | 未见单独大额 |
| 违法惩罚 | violation_penalty=100 | （扣在对局） | 非法着等 |
| 完赛 | completion_bonus=30 | completion_total | 两局完赛约 60 |
| 领地 | territory_max=100 | territory_total | 领地相关加分 |
| 战术 | tactical_max=60 | tactical_total | 战术项（两局可叠） |
| 负局扣子 | loss_penalty_per_stone=10 | loss_penalty_total | 输了按被提/落后扣分 |

## 排行榜分项复算（official_score ≈ 分项之和？）

| rank | name | lang | wins | official | win1000 | capt | margin | terr | tact | comp | speed | loss_pen | sum_parts | gap |
|------|------|------|------|----------|---------|------|--------|------|------|------|-------|----------|-----------|-----|
| 1 | 徐宸博 | cpp | 2-0 | 5483 | 2000 | 780 | 324 | 36 | 120 | 60 | 111 | 0 | 3431 | 2052 |
| 2 | 冷东宇 | cpp | 2-0 | 5090 | 2000 | 490 | 216 | 32 | 120 | 60 | 120 | 0 | 3038 | 2052 |
| 3 | 曹琳浩 | cpp | 2-0 | 4875 | 2000 | 370 | 128 | 26 | 120 | 60 | 119 | 0 | 2823 | 2052 |
| 4 | 刘永康 | cpp | 2-0 | 4858 | 2000 | 350 | 136 | 12 | 120 | 60 | 128 | 0 | 2806 | 2052 |
| 5 | 张子益 | python | 2-0 | 4786 | 2000 | 290 | 120 | 36 | 90 | 60 | 138 | 0 | 2734 | 2052 |
| 6 | 姜雨涵 | cpp | 2-0 | 4661 | 2000 | 230 | 64 | 14 | 100 | 60 | 141 | 0 | 2609 | 2052 |
| 7 | 柴君乐 | cpp | 1-1 | 2656 | 1000 | 270 | 98 | 18 | 110 | 60 | 62 | 13 | 1605 | 1051 |
| 8 | 孙浩阳 | cpp | 1-1 | 2451 | 1000 | 170 | 74 | 24 | 80 | 60 | 75 | 83 | 1400 | 1051 |
| 9 | 张佩杰 | python | 1-1 | 2130 | 1000 | 50 | 14 | 10 | 50 | 30 | 75 | 0 | 1229 | 901 |
| 10 | 邓铭阳 | cpp | 0-2 | 361 | 0 | 210 | 0 | 32 | 70 | 60 | 0 | 61 | 311 | 50 |
| 11 | 胡毅 | python | 0-2 | 120 | 0 | 30 | 0 | 16 | 20 | 60 | 0 | 56 | 70 | 50 |
| 12 | 赵天宇 | cpp | 0-2 | 69 | 0 | 0 | 0 | 0 | 0 | 60 | 0 | 41 | 19 | 50 |
| 13 | 杨鹏博 | python | 0-2 | 60 | 0 | 60 | 0 | 16 | 50 | 60 | 0 | 176 | 10 | 50 |
| 14 | 葛瀚远 | cpp | 0-2 | 24 | 0 | 0 | 0 | 10 | 0 | 60 | 0 | 96 | -26 | 50 |
| 15 | 安奕铭 | cpp | 0-2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 16 | 马光绪 | python | 0-2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 17 | 乔天宇 | cpp | 0-2 | 0 | 0 | 330 | 0 | 0 | 90 | 60 | 0 | 756 | -276 | 276 |
| 18 | 刘松鸣 | python | 0-2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

若 `gap` 接近 0，说明 official_score 主要由：**胜局底分 + 提子 + 目差 + 领地 + 战术 + 完赛 + 速度 − 负局扣分** 构成。

## 张子益（user_id=23）

- best submission `314` | lang=`python` | official_score=**4786** | rank=**5** | W-D-L=2-0-0
- 分项: capture=290 margin=120 territory=36 tactical=90 completion=60 speed=138 loss_pen=0
- 历史评测: evals=4 累计 W/D/L=5/0/3 avg=3048.25
- achieved_at(UTC): `2026-11-05T13:03:27.837379Z` → 约北京时间 2026-11-04 23:04

与第1名徐宸博对比缺口：
- official_score: 你 4786 / 第1 5483 / 差 697
- capture_total: 你 290 / 第1 780 / 差 490
- margin_total: 你 120 / 第1 324 / 差 204
- territory_total: 你 36 / 第1 36 / 差 0
- tactical_total: 你 90 / 第1 120 / 差 30
- speed_bonus_total: 你 138 / 第1 111 / 差 -27

## 公开棋谱里的「张子益」对局

在最近 100 局公开 matches 中命中 **4** 局。

## 近期对局样本（含 score 明细）

### match 396: 官方基准程序 vs 张子益 (second/WIN) reason=TWO_PASS_SCORE

```json
{
  "result": "WIN",
  "valid_own_decisions": 43,
  "capped_decisions": 43,
  "base_win_points": 2001,
  "speed_bonus": 69,
  "survival_bonus": 0,
  "draw_points": 0,
  "game_score": 2300,
  "capture_points": 100,
  "margin_points": 50,
  "violation": false,
  "completion_points": 30,
  "territory_points": 20,
  "tactical_points": 30,
  "defense_points": 0,
  "chain_points": 0,
  "turn_points": 0,
  "loss_penalty": 0,
  "achievements": {
    "capture_peak": 3,
    "territory": 10
  }
}
```

```json
{"id": 396, "game_type": "go9", "mode": "baseline", "execution_mode": "student_docker", "first_name": "官方基准程序", "second_name": "张子益", "first_kind": "baseline", "second_kind": "student", "result": "SECOND", "reason": "TWO_PASS_SCORE", "baseline_version": "go9-chinese-v2", "events_count": 88, "duration_ms": 388276, "seed": 1101, "created_at": "2026-11-05T13:37:30.741480Z", "verified_at": "2026-11-05T13:37:30.740576Z", "has_replay": true, "detail": {"baseline_resources": {"policy": "auto-root-v2", "docker_cpus": 24, "memory_bytes": 16430112768, "host_cpus": 24, "threads": 4}, "execution_mode": "student_docker", "game_index": 1, "student_side": "second", "student_result": "WIN", "valid_own_decisions": 43, "score": {"result": "WIN", "valid_own_decisions": 43, "capped_decisions": 43, "base_win_points": 2001, "speed_bonus": 69, "survival_bonus": 0, "draw_points": 0, "game_score": 2300, "capture_points": 100, "margin_points": 50, "violation": false, "completion_points": 30, "territory_points": 20, "tactical_points": 30, "defense_points": 0, "chain_points": 0, "turn_points": 0, "loss_penalty": 0, "achievements": {"capture_peak": 3, "territory": 10}}, "go_result": {"winner_text": "数子结束：黑 38.00，白 50.50，白胜 6.25 子。", "pass_count": 2, "captures": {"1": 10, "2": 10}, "resigned_color": null, "technical_stop": false, "black_score": 38.0, "white_score": 50.5, "diff": 12.5, "margin_points": 12.5, "margin_stones": 6.25, "komi": 7.5, "stone_count": {"1": 33, "2": 33}, "territory_count": {"1": 5, "2": 10}, "dead": []}, "dots_result": null, "baseline_version": "go9-chinese-v2", "seed": 1101}}
```

### match 388: 官方基准程序 vs 张子益 (second/WIN) reason=TWO_PASS_SCORE

```json
{
  "result": "WIN",
  "valid_own_decisions": 43,
  "capped_decisions": 43,
  "base_win_points": 2001,
  "speed_bonus": 69,
  "survival_bonus": 0,
  "draw_points": 0,
  "game_score": 2438,
  "capture_points": 160,
  "margin_points": 98,
  "violation": false,
  "completion_points": 30,
  "territory_points": 20,
  "tactical_points": 60,
  "defense_points": 0,
  "chain_points": 0,
  "turn_points": 0,
  "loss_penalty": 0,
  "achievements": {
    "capture_peak": 7,
    "territory": 10
  }
}
```

```json
{"id": 388, "game_type": "go9", "mode": "baseline", "execution_mode": "student_docker", "first_name": "官方基准程序", "second_name": "张子益", "first_kind": "baseline", "second_kind": "student", "result": "SECOND", "reason": "TWO_PASS_SCORE", "baseline_version": "go9-chinese-v2", "events_count": 88, "duration_ms": 414588, "seed": 1101, "created_at": "2026-11-05T13:03:27.830930Z", "verified_at": "2026-11-05T13:03:27.827829Z", "has_replay": true, "detail": {"baseline_resources": {"policy": "auto-root-v2", "docker_cpus": 24, "memory_bytes": 16430133248, "host_cpus": 24, "threads": 4}, "execution_mode": "student_docker", "game_index": 1, "student_side": "second", "student_result": "WIN", "valid_own_decisions": 43, "score": {"result": "WIN", "valid_own_decisions": 43, "capped_decisions": 43, "base_win_points": 2001, "speed_bonus": 69, "survival_bonus": 0, "draw_points": 0, "game_score": 2438, "capture_points": 160, "margin_points": 98, "violation": false, "completion_points": 30, "territory_points": 20, "tactical_points": 60, "defense_points": 0, "chain_points": 0, "turn_points": 0, "loss_penalty": 0, "achievements": {"capture_peak": 7, "territory": 10}}, "go_result": {"winner_text": "数子结束：黑 32.00，白 56.50，白胜 12.25 子。", "pass_count": 2, "captures": {"1": 4, "2": 16}, "resigned_color": null, "technical_stop": false, "black_score": 32.0, "white_score": 56.5, "diff": 24.5, "margin_points": 24.5, "margin_stones": 12.25, "komi": 7.5, "stone_count": {"1": 27, "2": 39}, "territory_count": {"1": 5, "2": 10}, "dead": []}, "dots_result": null, "baseline_version": "go9-chinese-v2", "seed": 1101}}
```

### match 387: 张子益 vs 官方基准程序 (first/WIN) reason=TWO_PASS_SCORE

```json
{
  "result": "WIN",
  "valid_own_decisions": 43,
  "capped_decisions": 43,
  "base_win_points": 2001,
  "speed_bonus": 69,
  "survival_bonus": 0,
  "draw_points": 0,
  "game_score": 2298,
  "capture_points": 130,
  "margin_points": 22,
  "violation": false,
  "completion_points": 30,
  "territory_points": 16,
  "tactical_points": 30,
  "defense_points": 0,
  "chain_points": 0,
  "turn_points": 0,
  "loss_penalty": 0,
  "achievements": {
    "capture_peak": 3,
    "territory": 8
  }
}
```

```json
{"id": 387, "game_type": "go9", "mode": "baseline", "execution_mode": "student_docker", "first_name": "张子益", "second_name": "官方基准程序", "first_kind": "student", "second_kind": "baseline", "result": "FIRST", "reason": "TWO_PASS_SCORE", "baseline_version": "go9-chinese-v2", "events_count": 87, "duration_ms": 442607, "seed": 1100, "created_at": "2026-11-05T13:03:27.822011Z", "verified_at": "2026-11-05T13:03:27.821480Z", "has_replay": true, "detail": {"baseline_resources": {"policy": "auto-root-v2", "docker_cpus": 24, "memory_bytes": 16430133248, "host_cpus": 24, "threads": 4}, "execution_mode": "student_docker", "game_index": 0, "student_side": "first", "student_result": "WIN", "valid_own_decisions": 43, "score": {"result": "WIN", "valid_own_decisions": 43, "capped_decisions": 43, "base_win_points": 2001, "speed_bonus": 69, "survival_bonus": 0, "draw_points": 0, "game_score": 2298, "capture_points": 130, "margin_points": 22, "violation": false, "completion_points": 30, "territory_points": 16, "tactical_points": 30, "defense_points": 0, "chain_points": 0, "turn_points": 0, "loss_penalty": 0, "achievements": {"capture_peak": 3, "territory": 8}}, "go_result": {"winner_text": "数子结束：黑 47.00，白 41.50，黑胜 2.75 子。", "pass_count": 2, "captures": {"1": 13, "2": 4}, "resigned_color": null, "technical_stop": false, "black_score": 47.0, "white_score": 41.5, "diff": 5.5, "margin_points": 5.5, "margin_stones": 2.75, "komi": 7.5, "stone_count": {"1": 39, "2": 29}, "territory_count": {"1": 8, "2": 5}, "dead": []}, "dots_result": null, "baseline_version": "go9-chinese-v2", "seed": 1100}}
```

### match 386: 官方基准程序 vs 孙浩阳 (second/WIN) reason=TWO_PASS_SCORE

```json
{
  "result": "WIN",
  "valid_own_decisions": 40,
  "capped_decisions": 40,
  "base_win_points": 2001,
  "speed_bonus": 75,
  "survival_bonus": 0,
  "draw_points": 0,
  "game_score": 2302,
  "capture_points": 70,
  "margin_points": 74,
  "violation": false,
  "completion_points": 30,
  "territory_points": 12,
  "tactical_points": 40,
  "defense_points": 0,
  "chain_points": 0,
  "turn_points": 0,
  "loss_penalty": 0,
  "achievements": {
    "capture_peak": 4,
    "territory": 6
  }
}
```

```json
{"id": 386, "game_type": "go9", "mode": "baseline", "execution_mode": "student_docker", "first_name": "官方基准程序", "second_name": "孙浩阳", "first_kind": "baseline", "second_kind": "student", "result": "SECOND", "reason": "TWO_PASS_SCORE", "baseline_version": "go9-chinese-v2", "events_count": 82, "duration_ms": 413360, "seed": 1101, "created_at": "2026-11-05T13:01:54.174180Z", "verified_at": "2026-11-05T13:01:54.173220Z", "has_replay": true, "detail": {"baseline_resources": {"policy": "auto-root-v2", "docker_cpus": 32, "memory_bytes": 7909646336, "host_cpus": 32, "threads": 4}, "execution_mode": "student_docker", "game_index": 1, "student_side": "second", "student_result": "WIN", "valid_own_decisions": 40, "score": {"result": "WIN", "valid_own_decisions": 40, "capped_decisions": 40, "base_win_points": 2001, "speed_bonus": 75, "survival_bonus": 0, "draw_points": 0, "game_score": 2302, "capture_points": 70, "margin_points": 74, "violation": false, "completion_points": 30, "territory_points": 12, "tactical_points": 40, "defense_points": 0, "chain_points": 0, "turn_points": 0, "loss_penalty": 0, "achievements": {"capture_peak": 4, "territory": 6}}, "go_result": {"winner_text": "数子结束：黑 35.00，白 53.50，白胜 9.25 子。", "pass_count": 2, "captures": {"1": 0, "2": 7}, "resigned_color": null, "technical_stop": false, "black_score": 35.0, "white_score": 53.5, "diff": 18.5, "margin_points": 18.5, "margin_stones": 9.25, "komi": 7.5, "stone_count": {"1": 33, "2": 40}, "territory_count": {"1": 2, "2": 6}, "dead": []}, "dots_result": null, "baseline_version": "go9-chinese-v2", "seed": 1101}}
```

### match 374: 官方基准程序 vs 刘永康 (second/WIN) reason=TWO_PASS_SCORE

```json
{
  "result": "WIN",
  "valid_own_decisions": 47,
  "capped_decisions": 47,
  "base_win_points": 2001,
  "speed_bonus": 62,
  "survival_bonus": 0,
  "draw_points": 0,
  "game_score": 2429,
  "capture_points": 180,
  "margin_points": 90,
  "violation": false,
  "completion_points": 30,
  "territory_points": 6,
  "tactical_points": 60,
  "defense_points": 0,
  "chain_points": 0,
  "turn_points": 0,
  "loss_penalty": 0,
  "achievements": {
    "capture_peak": 7,
    "territory": 3
  }
}
```

```json
{"id": 374, "game_type": "go9", "mode": "baseline", "execution_mode": "student_docker", "first_name": "官方基准程序", "second_name": "刘永康", "first_kind": "baseline", "second_kind": "student", "result": "SECOND", "reason": "TWO_PASS_SCORE", "baseline_version": "go9-chinese-v2", "events_count": 96, "duration_ms": 518897, "seed": 1101, "created_at": "2026-11-05T11:56:31.936228Z", "verified_at": "2026-11-05T11:56:31.933820Z", "has_replay": true, "detail": {"baseline_resources": {"policy": "auto-root-v2", "docker_cpus": 32, "memory_bytes": 8178061312, "host_cpus": 32, "threads": 4}, "execution_mode": "student_docker", "game_index": 1, "student_side": "second", "student_result": "WIN", "valid_own_decisions": 47, "score": {"result": "WIN", "valid_own_decisions": 47, "capped_decisions": 47, "base_win_points": 2001, "speed_bonus": 62, "survival_bonus": 0, "draw_points": 0, "game_score": 2429, "capture_points": 180, "margin_points": 90, "violation": false, "completion_points": 30, "territory_points": 6, "tactical_points": 60, "defense_points": 0, "chain_points": 0, "turn_points": 0, "loss_penalty": 0, "achievements": {"capture_peak": 7, "territory": 3}}, "go_result": {"winner_text": "数子结束：黑 33.00，白 55.50，白胜 11.25 子。", "pass_count": 2, "captures": {"1": 2, "2": 18}, "resigned_color": null, "technical_stop": false, "black_score": 33.0, "white_score": 55.5, "diff": 22.5, "margin_points": 22.5, "margin_stones": 11.25, "komi": 7.5, "stone_count": {"1": 29, "2": 45}, "territory_count": {"1": 4, "2": 3}, "dead": []}, "dots_result": null, "baseline_version": "go9-chinese-v2", "seed": 1101}}
```

### match 373: 刘永康 vs 官方基准程序 (first/WIN) reason=TWO_PASS_SCORE

```json
{
  "result": "WIN",
  "valid_own_decisions": 45,
  "capped_decisions": 45,
  "base_win_points": 2001,
  "speed_bonus": 66,
  "survival_bonus": 0,
  "draw_points": 0,
  "game_score": 2379,
  "capture_points": 170,
  "margin_points": 46,
  "violation": false,
  "completion_points": 30,
  "territory_points": 6,
  "tactical_points": 60,
  "defense_points": 0,
  "chain_points": 0,
  "turn_points": 0,
  "loss_penalty": 0,
  "achievements": {
    "capture_peak": 6,
    "territory": 3
  }
}
```

```json
{"id": 373, "game_type": "go9", "mode": "baseline", "execution_mode": "student_docker", "first_name": "刘永康", "second_name": "官方基准程序", "first_kind": "student", "second_kind": "baseline", "result": "FIRST", "reason": "TWO_PASS_SCORE", "baseline_version": "go9-chinese-v2", "events_count": 91, "duration_ms": 496365, "seed": 1100, "created_at": "2026-11-05T11:56:31.925121Z", "verified_at": "2026-11-05T11:56:31.924662Z", "has_replay": true, "detail": {"baseline_resources": {"policy": "auto-root-v2", "docker_cpus": 32, "memory_bytes": 8178061312, "host_cpus": 32, "threads": 4}, "execution_mode": "student_docker", "game_index": 0, "student_side": "first", "student_result": "WIN", "valid_own_decisions": 45, "score": {"result": "WIN", "valid_own_decisions": 45, "capped_decisions": 45, "base_win_points": 2001, "speed_bonus": 66, "survival_bonus": 0, "draw_points": 0, "game_score": 2379, "capture_points": 170, "margin_points": 46, "violation": false, "completion_points": 30, "territory_points": 6, "tactical_points": 60, "defense_points": 0, "chain_points": 0, "turn_points": 0, "loss_penalty": 0, "achievements": {"capture_peak": 6, "territory": 3}}, "go_result": {"winner_text": "数子结束：黑 50.00，白 38.50，黑胜 5.75 子。", "pass_count": 2, "captures": {"1": 17, "2": 0}, "resigned_color": null, "technical_stop": false, "black_score": 50.0, "white_score": 38.5, "diff": 11.5, "margin_points": 11.5, "margin_stones": 5.75, "komi": 7.5, "stone_count": {"1": 45, "2": 27}, "territory_count": {"1": 3, "2": 2}, "dead": []}, "dots_result": null, "baseline_version": "go9-chinese-v2", "seed": 1100}}
```

## 对 bot 的加分导向（按现行 go-score-v4）

1. **先保证双胜**（底分 2000）。你已有 2-0 best。
2. **提子是最大可拉开分差的项**（`capture_points_uncapped=1`，每子 10 分）。顶名 capture_total=780，你 340——优先杀棋/提净死子，不要早 PASS。
3. **margin（赢子优势）** 顶名 324 vs 你 40——大胜比险胜分高很多。
4. **tactical** 顶名打满 120，你 90——双打/征子/救棋等战术触发。
5. **territory / speed** 次要；别超时、别非法着（violation / loss_penalty）。
6. 公开页棋谱：http://139.196.148.174/go9 ；复盘接口可试 `/api/matches/{id}`。

## 最近公开对局（节选）

- `396` 官方基准程序 vs 张子益 | WIN | TWO_PASS_SCORE | moves=88 | replay=True
- `395` 张子益 vs 官方基准程序 | LOSS | TWO_PASS_SCORE | moves=79 | replay=True
- `392` 官方基准程序 vs 已删除账号 | LOSS | TWO_PASS_SCORE | moves=67 | replay=True
- `391` 已删除账号 vs 官方基准程序 | LOSS | TWO_PASS_SCORE | moves=66 | replay=True
- `390` 官方基准程序 vs 已删除账号 | LOSS | TWO_PASS_SCORE | moves=73 | replay=True
- `389` 已删除账号 vs 官方基准程序 | LOSS | TWO_PASS_SCORE | moves=80 | replay=True
- `388` 官方基准程序 vs 张子益 | WIN | TWO_PASS_SCORE | moves=88 | replay=True
- `387` 张子益 vs 官方基准程序 | WIN | TWO_PASS_SCORE | moves=87 | replay=True
- `386` 官方基准程序 vs 孙浩阳 | WIN | TWO_PASS_SCORE | moves=82 | replay=True
- `385` 孙浩阳 vs 官方基准程序 | LOSS | TWO_PASS_SCORE | moves=98 | replay=True
- `384` 官方基准程序 vs 已删除账号 | LOSS | TWO_PASS_SCORE | moves=67 | replay=True
- `383` 已删除账号 vs 官方基准程序 | LOSS | TIMEOUT | moves=0 | replay=True
- `376` 官方基准程序 vs 已删除账号 | LOSS | TWO_PASS_SCORE | moves=63 | replay=True
- `375` 已删除账号 vs 官方基准程序 | LOSS | TWO_PASS_SCORE | moves=68 | replay=True
- `374` 官方基准程序 vs 刘永康 | WIN | TWO_PASS_SCORE | moves=96 | replay=True
- `373` 刘永康 vs 官方基准程序 | WIN | TWO_PASS_SCORE | moves=91 | replay=True
- `372` 官方基准程序 vs 已删除账号 | LOSS | TWO_PASS_SCORE | moves=109 | replay=True
- `371` 已删除账号 vs 官方基准程序 | LOSS | TWO_PASS_SCORE | moves=66 | replay=True
- `370` 官方基准程序 vs 已删除账号 | LOSS | TWO_PASS_SCORE | moves=63 | replay=True
- `369` 已删除账号 vs 官方基准程序 | LOSS | TWO_PASS_SCORE | moves=66 | replay=True
- `368` 官方基准程序 vs 姜雨涵 | WIN | TWO_PASS_SCORE | moves=80 | replay=True
- `367` 姜雨涵 vs 官方基准程序 | WIN | TWO_PASS_SCORE | moves=93 | replay=True
- `366` 官方基准程序 vs 已删除账号 | LOSS | TWO_PASS_SCORE | moves=57 | replay=True
- `365` 已删除账号 vs 官方基准程序 | LOSS | TWO_PASS_SCORE | moves=64 | replay=True
- `362` 官方基准程序 vs 杨鹏博 | LOSS | ILLEGAL_ACTION | moves=1 | replay=True
- `361` 杨鹏博 vs 官方基准程序 | LOSS | ILLEGAL_ACTION | moves=0 | replay=True
- `360` 官方基准程序 vs 赵天宇 | LOSS | TWO_PASS_SCORE | moves=37 | replay=True
- `359` 赵天宇 vs 官方基准程序 | LOSS | TWO_PASS_SCORE | moves=22 | replay=True
- `358` 官方基准程序 vs 已删除账号 | LOSS | TWO_PASS_SCORE | moves=65 | replay=True
- `357` 已删除账号 vs 官方基准程序 | LOSS | TWO_PASS_SCORE | moves=70 | replay=True