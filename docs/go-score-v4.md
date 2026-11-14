# go-score-v4（go9）加分规则实勘

来源：`GET http://139.196.148.174/api/games` 的 `benchmark.weights`，并用公开对局 `detail.score` / 排行榜反推。

抓取日：2026-11-05（Asia/Shanghai）。

## API weights

| key | value | 实战含义 |
|-----|-------|----------|
| win_base_per_match | 1000 | 名义胜局底分；**实发约 `base_win_points=2001`/胜**（≈2×1000+1） |
| win_base_extra | 1 | 并入胜局底分 |
| draw_points | 300 | 和棋 |
| capture_points_per_stone | 10 | 每提 1 子 +10 |
| capture_points_uncapped | 1 | **提子分不封顶**（关键） |
| advantage_capture_max | 150 | 名义上限；有 uncapped 时实际可超过 |
| advantage_margin_max | 250 | 目差/子数优势加分上限相关 |
| territory_max | 100 | 领地项 |
| tactical_max | 60 | 单局战术上限（两局可叠到排行榜 ~120） |
| efficiency_max | 150 | 速度/效率 → `speed_bonus` |
| completion_bonus | 30 | 完赛（两局常见合计 60） |
| stability_bonus | 50 | 完赛稳定项（排行榜 gap 里常见 +50） |
| violation_penalty | 100 | 违法 |
| loss_penalty_per_stone | 10 | 负局按子扣分 |

## 单局 score 示例（胜）

```text
base_win_points   ≈ 2001
capture_points    = 提子数 × 10
margin_points     = 与胜子/目差相关（有上限）
territory_points  = 小额
tactical_points   ≤ 60
completion_points = 30
speed_bonus       = 效率
game_score        = 以上合计
```

排行榜 `official_score` ≈ 两局 `game_score` 之和（再加稳定项等）。

## 对 AI 的导向

1. **先双胜**（每胜约 +2001）。
2. **多提子、提净死子**（不封顶，拉开分差的主杠杆）。
3. **大胜**（margin），不要刚领先就 PASS。
4. 打满 tactical；避免超时/非法着。
5. 评测 `move_cap=80` 与规则技术停手 400 不同，勿混用。

## 张子益（快照）

- 排行榜第 **5**，best `official_score=4730`，submission `123`，Python，2 胜 0 负。
- 相对第 1（5483）主要差在：`capture` 340→780，`margin` 40→324，`tactical` 90→120。
- 最近公开 `/matches?limit=100` 列表里未出现姓名「张子益」（旧局可能已滚出列表）；网站 http://139.196.148.174/go9 仍可按人点开。
