# AGENTS.md — 给 Cursor / 编码代理

你在改进 **Association Arena go9** 参赛 bot。先读完本文再改代码。

**本工程刚整理完毕：说明优先；不要一上来盲目改强度或拆成多文件依赖。**

---

## 1. 你在改什么

| 项 | 内容 |
|----|------|
| 工程根 | 含 `bot.py` 的本目录（用户机常见路径：`C:\Users\UFO\Desktop\grok\arena\go9`） |
| 提交物 | **仅** `bot.py`（ArenaStudent 上传单文件或 ZIP 根目录含 `bot.py`） |
| 协议 | `arena.v1` |
| 规则 | `go9-chinese-v2` |
| 对手 | 官方 Baseline（客户端本地评测，先后手各一局） |
| 分数 | `go-score-v4` |

平台 API（核对规则，勿死记 SDK）：`http://139.196.148.174/api/games`

---

## 2. 硬约束（违反即废）

1. **单文件**可上传的 `bot.py`；评测环境 **Python3 标准库 only**（禁止 numpy/torch/网络下载权重等）。
2. **无 GPU** 假设；单手 **`time_limit_ms` ≈ 10000**，应用约 **90%+** 预算，留余量写 JSON。
3. **stdout**：每个 request **恰好一行** `move_response` JSON；禁止 print 调试到 stdout。
4. **stdin**：按行读 `move_request`；用 `request_id` 原样返回。
5. 必须处理 **`observation.legal_moves`（若有）**：着法 ∈ 该集合。
6. **PASS 策略**：须对齐「**实际提净死子**」——有提子/对方死形时不要 PASS；不要用「本地 80 手终局」之类过短阈值乱 PASS。规则层技术停手 **400**；`passes_to_score = 2`。
7. **komi = 7.5**（黑贴 3¾ 子）。中国数子；提子不重复计入面积。
8. 包体积极小（远低于 8MB）；不要塞模型文件进提交。

### 明确不要做

- 不要相信学生 SDK README 的 **「6 次 PASS 终局」** → 线上是 **2 次**。
- 不要引入第三方依赖或「先 pip install」。
- 不要把 ArenaStudent、Docker、Baseline 二进制拷进本仓库当依赖。
- 不要改协议字段名/坐标体系（0-based）。
- 不要为了「看起来更深」只加浅层 α-β 层数而吃光时间；应用 **偏置 MCTS/UCT（或等价）吃满时间**。
- 不要在未跑冒烟、未说明行为变化时大面积删除战术护栏（提子、禁填眼、legal_moves）。

---

## 3. 文件职责

| 路径 | 谁改 | 说明 |
|------|------|------|
| `bot.py` | 主战场 | 唯一提交入口；保持 `python -u bot.py` 可跑 |
| `README.md` | 规则/上传变更时更新 | 给人看 |
| `AGENTS.md` | 任务/约束变更时更新 | 给你（代理）看 |
| `scripts/smoke_test.py` | 新增行为时扩展用例 | 回归 |
| `docs/protocol-and-rules.md` | 协议澄清时更新 | 摘录与易错点 |

---

## 4. 当前 bot 弱点（改进切入点）

用户反馈：**仍明显弱于 Baseline**。已知方向：

1. **收官 / PASS**：提净不彻底或形势判断导致错 PASS / 该收不收。
2. **开局**：库外立即变差；3-3/傻尖等。
3. **中盘战术**：送吃、填眼、漏双打、征子判断错。
4. **评估**：死活近似差 → 错误领地与错误 PASS。
5. **搜索**：时间分配、先验、playout 质量、RAVE/UCT 参数；静默早退。
6. **与 go-score-v4 不对齐**：只想赢子数不够，还需稳定、战术、提子等得分项（见 API `benchmark.weights`）。

---

## 5. 改进任务清单（按优先级）

完成一项勾一项；每项后跑冒烟。

### P0 — 正确性与别再送分

- [x] 凡 `legal_moves` 存在则严格遵守（含 PASS 是否允许看 `available_actions` / `pass_forbidden_*`）。
- [x] 可提之子优先提；对方 PASS 后仍先提净再考虑 PASS。
- [x] 禁止填真眼；强烈抑制填假眼 / 无意义自紧气。
- [x] 技术停手按 **400** 理解；不要短手数强制终局 PASS。

### P1 — 对 Baseline 有体感的加强

- [x] **吃满时间**：根节点偏置 MCTS/UCT 为主；α-β 只作战术短搜或静搜。
- [x] 提高 playout 质量（提子/逃棋/二气/局部优先 + 3×3），增加有效迭代而非空转。
- [x] 评估：中国面积 + 死活/眼位/气/连通；无两眼大块降权。
- [x] 扩大开局库 + 对称；中盘避免库手与战术冲突时强行走库。

### P2 — 分数与稳定性（go-score-v4）

- [ ] 减少违法/超时/怪招导致的 violation。
- [ ] 稳定完成对局（completion）；提子与优势转化相关权重见 API。
- [ ] 用 ArenaStudent 先后手打 Baseline，根据棋谱改，而不是只看自测分数。

### P3 — 可选结构

- [ ] Zobrist + 置换表、更好先验、轻量模式启发——仍须单文件 stdlib。
- [ ] 保持代码可读分区（规则 / 评估 / 搜索 / I/O），方便下次迭代。

---

## 6. 验收标准

1. `python -u scripts/smoke_test.py`（或 `python3`）**全部通过**。
2. 空盘 → 天元或合理开局库着；可提 → 提；不填真眼；尊重 `legal_moves`。
3. 安静中盘在 `time_limit_ms=2500~10000` 下应 **明显消耗预算**（除非战术强制着）。
4. ArenaStudent 上传 `bot.py` 能跑完 vs Baseline；目标：**胜率/得分相对当前版本提升**，最终「打过或逼近 Baseline」。
5. stdout 无日志污染。

---

## 7. 建议工作流

1. 读 `README.md` + `docs/protocol-and-rules.md`。
2. 跑一遍 `scripts/smoke_test.py` 确认基线绿。
3. 按 P0 → P1 → P2 改 `bot.py`（小步提交逻辑，避免一次重写崩溃）。
4. 每步冒烟；有客户端则打 Baseline 看棋谱。
5. 更新 `README.md`「当前能力 / 已知弱点」一两段（事实描述）。

---

## 8. 冒烟与协议速查

```bash
python -u scripts/smoke_test.py
```

响应必须形如：

```json
{"protocol":"arena.v1","request_id":"...","type":"move_response","action":{"kind":"PLACE","row":4,"col":4}}
```

坐标 0-based。黑=1，白=2，空=0。

---

## 9. 一句话目标

**在硬约束内，把 `bot.py` 提升到对官方 Baseline 有竞争力，并用冒烟 + ArenaStudent 证明；不要破坏协议与可提交性。**
