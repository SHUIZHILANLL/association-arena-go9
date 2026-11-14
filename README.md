# Association Arena · go9

**九路围棋 AI** — 面向 [Association Arena](http://139.196.148.174) 学生赛道 `go9` 的单文件参赛 bot。

| 项 | 值 |
|----|-----|
| 赛道 | `go9`（9×9） |
| 协议 | `arena.v1` |
| 规则 | `go9-chinese-v2` |
| 提交物 | **仅** 根目录 [`bot.py`](bot.py)（Python 3 **标准库 only**） |
| 单手时限 | **10000 ms**（超时判负） |
| 评分 | `go-score-v4`（vs 官方 Baseline，先后手各一局） |
| 历史峰值 | submission **#314**，official ≈ **4786**，2–0 |

> **线上终局是连续 2 次 PASS，不是 6 次。**  
> 学生 SDK README 可能过时；以平台 `GET /api/games` 与本仓库 [`docs/`](docs/) 为准。

---

## 目录

- [项目简介](#项目简介)
- [快速开始](#快速开始)
- [架构概览](#架构概览)
- [规则要点](#规则要点-go9-chinese-v2)
- [协议 I/O](#协议-arenav1)
- [评分导向（go-score-v4）](#评分导向-go-score-v4)
- [ArenaStudent 打榜](#arenastudent-打榜)
- [目录结构](#目录结构)
- [硬约束](#硬约束)
- [已知弱点与改进方向](#已知弱点与改进方向)
- [给 Cursor / 代理](#给-cursor--代理)
- [许可证与声明](#许可证与声明)

---

## 项目简介

本仓库是干净可上传的 go9 工程：核心是约 1.5k 行的单文件 `bot.py`，无 numpy / torch / 权重文件。

**搜索主路径**：单线程、时限盒内的 **RAVE/AMAF MCTS**（对齐 Michi/Pachi 思路），吃满约 **94%** 的 `time_limit_ms`。

**配套能力**：

- 规则层：气 / 提子 / 自杀过滤 / 简单劫；**优先服从** `observation.legal_moves`
- 开局：开局库 + 8 对称；空盘瞬着天元；抑制开局 3-3
- 战术：提子 / 逃一手 / 二气威胁；禁填真眼；热战浅层 α-β
- 收官：可提净时拒 PASS；**薄领先不 PASS**（防 0.25 子负）
- 评估：中国数子 + 轻量死活 / 气 / 眼
- Playout：局部优先（提逃 + 3×3 模式），禁止全盘 legal 扫描；中盘约 **800+ iter/s**（10s 量级 ~8k）

本地回归：[`scripts/smoke_test.py`](scripts/smoke_test.py)（stdlib only）。

---

## 快速开始

### 环境

- Python **3.8+**（推荐 3.10 / 3.12）
- **无**第三方依赖：不要 `pip install` 任何棋库或数值库

### 冒烟测试

```bash
# Windows（本目录）
python -u scripts\smoke_test.py

# Linux / macOS
python3 -u scripts/smoke_test.py
```

期望全部 `OK`，且进程 **stdout 无调试杂讯**。

### 手工跑一手

```bash
python -u bot.py
```

stdin 贴一行空盘 `move_request`（见 `scripts/smoke_test.py`），stdout 应返回天元：

```json
{"protocol":"arena.v1","request_id":"...","type":"move_response","action":{"kind":"PLACE","row":4,"col":4}}
```

### 启动方式对照

| 目的 | 命令 / 操作 |
|------|-------------|
| 确认能跑 | `python -u scripts/smoke_test.py` |
| 手工对一手 | `python -u bot.py` + stdin JSON |
| 正式打分 | ArenaStudent 上传 `bot.py` → vs Baseline |

---

## 架构概览

```text
move_request (stdin JSON)
        │
        ▼
┌───────────────────┐
│  I/O / 合法着过滤  │  尊重 legal_moves、available_actions
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 战术强制 / 开局库  │  提净、逃棋、书着、天元
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 热战浅层 α-β（可选）│  短搜，不吃满时限
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ RAVE/AMAF MCTS    │  虚拟先验 + 局部 playout，吃满时限
└─────────┬─────────┘
          │
          ▼
move_response (stdout 单行 JSON)
```

代码分区（均在 `bot.py` 内）：规则 / 评估 / 搜索 / I/O。详见文件头注释与 [`AGENTS.md`](AGENTS.md)。

---

## 规则要点（go9-chinese-v2）

权威：`GET http://139.196.148.174/api/games`（`type=go9`）。摘录见 [`docs/protocol-and-rules.md`](docs/protocol-and-rules.md)。

1. **棋盘** 9×9，黑先（`player` / `current_player`：`1` 黑，`2` 白；空 `0`）。
2. **中国数子**：黑贴 **3¾ 子（`komi = 7.5` 目）**；提子不重复计入面积。
3. **终局**：双方 **连续两次 PASS**（`passes_to_score = 2`）后数子；**无 `END_GAME`**。
4. **死子**：AI 必须 **实际提净**；不要「领先就 PASS」指望裁判删棋。
5. **技术手数** `technical_stop_moves = 400`（勿用「80 手强制 PASS」之类短启发式）。
6. **动作**：`PLACE` / `PASS` / `RESIGN`。
7. 若 observation 带 **`legal_moves`**，着法必须 ∈ 该集合。
8. 单手硬超时 **10000 ms**；非法着 / 协议错误 / 超时 → 外层判负。

评测侧另有 `move_cap: 80` 等（Benchmark），与规则层 400 **不要混用**。

---

## 协议（arena.v1）

- 启动：`python3 -u bot.py`（无缓冲）。
- **stdin**：每行一个 `move_request`。
- **stdout**：每行一个 `move_response`（**只能**是响应；禁止 print 调试到 stdout）。
- **stderr**：可打调试（评测可能丢弃）。
- 坐标 **0-based**，`row` / `col` ∈ `[0, 8]`。
- `request_id` **原样返回**。

### 请求示意

```json
{
  "protocol": "arena.v1",
  "request_id": "...",
  "type": "move_request",
  "game": "go9",
  "rule_version": "go9-chinese-v2",
  "player": 1,
  "time_limit_ms": 10000,
  "observation": {
    "size": 9,
    "komi": 7.5,
    "board": [[0, 0, 0, 0, 0, 0, 0, 0, 0], "..."],
    "current_player": 1,
    "ko_point": null,
    "captures": {"1": 0, "2": 0},
    "pass_count": 0,
    "move_number": 0,
    "last_action": null,
    "available_actions": ["PLACE", "PASS", "RESIGN"],
    "legal_moves": [[4, 4], "..."]
  }
}
```

### 响应示意

```json
{
  "protocol": "arena.v1",
  "request_id": "...",
  "type": "move_response",
  "action": {"kind": "PLACE", "row": 4, "col": 4}
}
```

或 `{"kind":"PASS"}` / `{"kind":"RESIGN"}`。

---

## 评分导向（go-score-v4）

详解：[`docs/go-score-v4.md`](docs/go-score-v4.md)。对 AI 的实战含义：

1. **先双胜**（胜局底分占大头）。
2. **多提子、提净死子**（`capture` 按子加分且 **不封顶**）。
3. **大胜 margin**，不要刚领先就 PASS。
4. 打满 tactical；避免超时 / 非法着 / violation。
5. 稳定完赛拿 completion / stability。

---

## ArenaStudent 打榜

1. 打开平台 <http://139.196.148.174>，下载 **ArenaStudent**；安装 **Docker Desktop**（Linux 容器模式），保持客户端与 Docker 运行。
2. 登录同一账号 → 赛道 **go9** → 语言 **Python**。
3. **上传我的 AI**：选本目录 **`bot.py`**；或 ZIP（**根目录必须有 `bot.py`**）。
4. **开始本地评测**（积分赛 / vs 官方 Baseline 先后手各一局）。客户端自动拉对手。
5. 结束后自动上报；排行榜可在客户端入口打开。

上传前确认：无第三方依赖、stdout 只出 JSON、单手能在 ~10s 内返回。

**不要**把 ArenaStudent 安装包、Docker wrap、Baseline 二进制、权重或大型 zip 塞进本仓库。

---

## 目录结构

```text
go9/
├── bot.py                      # ★ 唯一上传入口
├── README.md                   # 本说明（GitHub / 人类）
├── AGENTS.md                   # Cursor / 编码代理约束与任务清单
├── CURSOR.md                   # 代理入口指针
├── .gitignore
├── scripts/
│   ├── smoke_test.py           # 本地冒烟（必跑）
│   ├── analyze_replay.py       # 棋谱分析（可选）
│   ├── print_moves.py
│   ├── dump_match_replay.py
│   ├── fetch_arena_go9.py
│   └── analyze_go9_scores.py
└── docs/
    ├── protocol-and-rules.md   # 协议/规则易错点
    ├── go-score-v4.md          # 评分实勘
    ├── arena_go9_analysis.md
    ├── arena_go9_snapshot.md
    └── replays/                # 对局回放样例（分析用，非提交物）
```

| 文件 | 职责 |
|------|------|
| `bot.py` | 参赛 AI；唯一需要上传的源码 |
| `README.md` | 规则、协议、启动、上传、架构 |
| `AGENTS.md` | 硬约束、勿做清单、P0–P3、验收 |
| `scripts/smoke_test.py` | 回归冒烟 |
| `docs/*` | 协议澄清、评分、对局分析 |

---

## 硬约束

违反即废（评测或上传失败）：

1. **单文件**可上传的 `bot.py`；评测环境 **仅 Python 标准库**。
2. 无 GPU 假设；单手应用约 **90%+** 时间预算，留余量写 JSON。
3. 每个 request **恰好一行** `move_response`；禁止 stdout 调试。
4. 必须处理 `legal_moves`（若有）。
5. PASS 对齐「实际提净死子」；技术停手按 **400** 理解。
6. `komi = 7.5`；包体远低于 8MB，不塞模型。

明确不要做：

- 相信 SDK「6 次 PASS」
- 引入第三方依赖或「先 pip install」
- 改协议字段名 / 坐标体系
- 只加浅层 α-β 层数吃光时间
- 未跑冒烟就大面积删战术护栏

---

## 已知弱点与改进方向

**弱点**

- 无神经网络；对强 Baseline 中盘深度仍可能不够
- 开局库非穷尽；非库局面靠启发式先验
- 死活 / 征子 / 接不归仍浅
- 死子近似与「须提净」不完全一致时可能错 PASS
- 全局同形超劫完全依赖平台 `legal_moves`

**优先改进（见 [`AGENTS.md`](AGENTS.md)）**

| 优先级 | 方向 |
|--------|------|
| P0 | 合法着、提净、禁填眼、400 停手理解 |
| P1 | 吃满时间的偏置 MCTS、playout 质量、评估、开局库 |
| P2 | 减少 violation、稳定完赛、按 Baseline 棋谱迭代 |
| P3 | Zobrist/置换表、更好先验（仍须单文件 stdlib） |

验收：冒烟全绿 → ArenaStudent vs Baseline 分数提升。

---

## 给 Cursor / 代理

完整约束与任务清单：**[`AGENTS.md`](AGENTS.md)**。

一句话：

> 在 **不破坏 arena.v1 / stdlib / 单文件 `bot.py`** 的前提下，把对官方 Baseline 的胜率与 go-score-v4 做上去；改完跑 `scripts/smoke_test.py`，再交 ArenaStudent 复测。

---

## 许可证与声明

- 面向 Association Arena 学生赛道本地评测与学习改进。
- 平台 API、规则与 Baseline 归赛事方；本仓库 bot 实现以本目录源码为准。
- 规则与权重以线上 API 为准；文档为摘录，可能随赛季更新。
