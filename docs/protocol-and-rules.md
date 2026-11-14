# go9 协议与规则摘录（给开发者）

> **权威来源**：平台 `GET http://139.196.148.174/api/games` 中 `type=go9` 条目。  
> 学生 SDK `README.md` 可能过时（曾写「连续 6 次 PASS」）——**以 API 与本文为准**。

## 线上配置摘要（go9-chinese-v2）

| 字段 | 值 | 含义 |
|------|-----|------|
| `protocol` | `arena.v1` | I/O 协议 |
| `rule_version` | `go9-chinese-v2` | 规则包 |
| `size` | 9 | 九路 |
| `komi` | 7.5 | 黑贴 7½ 目 = 3¾ 子 |
| `passes_to_score` | **2** | 连续两次 PASS 数子 |
| `technical_stop_moves` | **400** | 技术停手上限 |
| `time_limit_ms` | 10000 | 单手硬超时 |
| `action_kinds` | PLACE, PASS, RESIGN | 无 END_GAME |
| `scoring` | 中国数子 | 提子不重复计入面积；胜子数 = 贴后面积差 ÷ 2 |
| Benchmark `score_rule_version` | `go-score-v4` | 本地评测计分 |
| Benchmark `move_cap` | 80 | 评测侧手数相关配置（勿与 400 技术停手混用） |

## 规则条文（API `rules` 意译）

1. 9×9，黑先；中国数子，黑贴 3¾ 子（7½ 目）。
2. 落子、提子、禁自杀、全局同形等走平台 RuleEngine；AI 侧若给了 `legal_moves` 必须遵守。
3. **连续两次 PASS** 终局；死活争议须 **实际提净**，不靠启发式自动删棋。
4. 正式协议不开放开局刷分用的 END_GAME。
5. 超时 / 非法着 / 协议错误 → 外层判负。

## arena.v1 I/O

- 启动：`python3 -u bot.py`（无缓冲）。
- 每个 `move_request` → 一个 `move_response`（单行 JSON → stdout）。
- `action` 示例：
  - `{"kind":"PLACE","row":r,"col":c}`（0-based）
  - `{"kind":"PASS"}`
  - `{"kind":"RESIGN"}`
- 调试只写 **stderr**。

## observation 常用字段

- `board`：9×9，`0` 空 / `1` 黑 / `2` 白
- `current_player`：轮到谁
- `ko_point`：简单劫点或 null（全局同形可能只体现在 `legal_moves`）
- `pass_count`：连续 PASS 计数
- `move_number`：已手数
- `captures`：`{"1":n,"2":n}`
- `legal_moves`：可选，`[[r,c], ...]`
- `available_actions`：如 `["PLACE","PASS","RESIGN"]`
- `komi` / `passes_to_score`：若缺省按 7.5 / 2

## SDK 过时警告

学生 SDK README 曾写：

> 九路围棋连续 6 次 PASS 进入原版数子终局。

**当前赛季 go9-chinese-v2 为 2 次 PASS。** 若按 6 实现会严重错判终局与 PASS 策略。

完整协议模板见平台下发的 `student-sdk/protocol/arena-v1.md`（勿把整个 SDK 拷进本 go9 工程）。

## 评测提示

- ArenaStudent + Docker：先后手 vs Baseline，自动上报。
- 改进效果以网站/客户端分数与棋谱为准，不以自写 Elo 为准。
