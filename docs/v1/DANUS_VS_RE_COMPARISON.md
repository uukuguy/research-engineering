# Danus vs research-engineering：核心对照

> Danus 是 frenzymath 的多 agent 研究级数学证明系统（公开仓库 + arXiv:2607.06447）。
> research-engineering（RE）是当前项目。两个系统都是"长期运行的研究循环 + 状态系统"，但研究对象不同：
> Danus 解决数学定理，RE 让 coding agent 在 session 边界保持状态。

## 一句话差异

**Danus 编码的是数学家的研究流程；RE 编码的是 coding agent 的研究流程。两者共享"事实图 / 权限边界 / 验证 gate / 慢循环战略反思"这套机制骨架。**

---

## 1. 共同的 8 项核心机制

| 机制 | Danus 名字 | RE 名字 | 关键差异 |
|---|---|---|---|
| **角色权限分离** | `roles.py ROLE_TOOLS`：main 不能 `fact_submit`；verifier 是 read-only；worker 是唯一能 `fact_submit` | 没有显式 role 概念；skill 自身承担 boundary | Danus 用 **代码** enforce 权限，RE 用 **SKILL.md 自然语言**——前者强一致，后者靠 router |
| **三层存储 + 一个真值源** | local memory（worker 私有）/ global memory（共享 awareness）/ **fact graph（唯一真值）** | local session state / CURRENT.md / **EV-* ledger（唯一真值）** | 同形态；Danus 显式声明 "global memory is never a correctness source"，RE 的 `FINDINGS.md` 也是 awareness 不是 truth |
| **内容寻址** | `fact_id = hash(problem_id + predecessors + glossary + statement + proof)`，`external_refs` 故意不参与 hash | `EV-*` = 时间戳 + 短 hash；`compute_fact_id` 类似思路但实现更简单 | RE 比 Danus 简单——EV 没 predecessor 字段，但 `hypothesis_ids` + `supports`/`contradicts` 提供隐式依赖 |
| **未验证结果不能进真值层** | worker 必须经过 verifier → accept → 进 fact graph；否则留在 global memory 的 `conclusion`/`example` kind | `EV-*.execution_status ≠ "completed"` 或 `research_outcome` 是环境错误类 → 工具拒绝（`NON_SCIENTIFIC_REFUTATION`） | 同思想；RE 在 tool 层 enforce，Danus 在 service 层 enforce |
| **冷启动 verifier（隔离上下文）** | `danus.verify` HTTP service + cold-start codex launcher；verifier 不保留记忆 | V1 tool-layer 没有 verifier——只有 `experiment-review` skill 自承四层判定 | RE 的"验证"是自我审查；Danus 是独立实例。**这是 RE 的最弱一环** |
| **主 agent 周期性战略重组** | 30 分钟 control beat + 4 小时 macro audit；强制输出 `master_guidance` + `elaboration` | `retrospective` skill（8-15 iterations 或 phase boundary 触发）；输出 `FINDINGS.md` + `CURRENT.md` | 同思想；Danus 用 wall-clock 强制（`clock.sleep`），RE 用 iteration-count 触发（更可移植但不够强制） |
| **慢循环 vs 快循环分工** | 快循环 = worker 跑一个 fact；慢循环 = main agent 在 30/240 min 心跳上重审 portfolio | 快循环 = `experiment-review`（一个 run → 一个假设判定）；慢循环 = `retrospective`/`research-search` | RE 比 Danus **多一层**：`research-search` 是"换家族"——Danus 把这个动作揉进了 main agent 的 control beat，没独立 skill |
| **失败也是有价值的状态** | `dead_end` finding（global memory），sibling worker 跳过 | `research_outcome: informative_failure` + `EV-*` 永久记录 | 同思想；RE 没显式 `dead_end` kind，但 `research_outcome` 词表覆盖 |

## 2. RE 缺的关键能力（来自 Danus）

### 2.1 **冷启动独立 verifier** — 最高优先级缺口

**Danus 的**：`danus.verify` 是独立 HTTP service，启动时 cold-start（不读 worker 的上下文），judge `statement + proof` 返回 `{verdict, repair_hints}`。worker 必须修复到 accept 才能进 fact graph。

**RE 的现状**：`experiment-review` skill 让**同一个 agent** 在四层里做判定（OBSERVATION / COMPARISON / INTERPRETATION / DECISION）。问题是：判定者和产生者是同一个上下文——**自我审查同形态偏见**。

**RE 可迁移**（不动 V1 已有 boundary）：
- 加一个 `verify-evidence` skill：cold-start 读 `EV-*.json` + 关联 `EXP-*`，返回 `{verdict, repair_hints}`，不读当前 session context
- 触发条件：`experiment-review` 的 INTERPRETATION 阶段 → 调 `verify-evidence` 而不是自己判定
- 实施成本：中（独立 verifier = 单独 agent 启动，需要 client 支持 sub-agent）

### 2.2 **30/240 min 强制 wall-clock 心跳** — 中等优先级

**Danus 的**：main agent 启动后建两个 deadline（30 min beat / 240 min macro audit），用 `clock.sleep` 等待而不是靠记忆。**`clock.sleep` 完成是真正的 wake-up**；agent 不主动 end turn 依赖记忆。

**RE 的现状**：`retrospective` 的 trigger 是"8-15 counted iterations"——纯 iteration-count，**没有 wall-clock anchor**。

**RE 可迁移**：
- `research-engineering` skill 加一个 wall-clock 心跳：每 30 min 强制跑一次 `retrospective` 或 `research-search`，不管 iteration 数
- 实施成本：低（`SessionRotateTests` 已经能跑 session-level 时间追踪）

### 2.3 **失败路径显式记录为 sibling-skip 状态** — 低优先级

**Danus 的**：`dead_end` finding（global memory kind），其他 worker 看到就跳过。

**RE 的现状**：`informative_failure` 是 `research_outcome` 词表里的一项，但 EV 进了 ledger 后**没有人显式 skip 它**——下次 hypothesis 触发时，`experiment-review` 还是会把它当 live evidence。

**RE 可迁移**：
- 加 `finding status` 中的 `Superseded`/`Dead-end`（已有词表，但没人用）
- `research-search` 触发时先扫 dead-end，避免重蹈
- 实施成本：低

## 3. Danus 缺的 / 不如 RE 的

### 3.1 **跨 session 状态持续性** — Danus 没有

Danus 是 **per-project** 的（一个 project 一个 main agent + worker swarm）。Project 之间不共享状态。RE 的 `research/ACTIVE.json` + `sessions.jsonl` 是 **跨 project** 的——同一会话可以挂多个 project 或从 idle resume。

RE 在这一层比 Danus **成熟**。

### 3.2 **architect signal 的语义** — Danus 没有

Danus 的"操作者信号"是 chat 直说，没结构化。RE 有 `ARCHITECT.md` 的 `research:signal` 块（OBSERVE / SUSPECT / DIRECTION / CHALLENGE / CONSTRAINT / DECISION / IMPLEMENT / VETO + scope + expiry + source_text）——`reconcile` 在 resume 时强制校验 expiry。

RE 在这一层比 Danus **严格**。

### 3.3 **三轴成熟度分离** — Danus 没有

Danus 没有 system maturity / evidence maturity / environment maturity 的分离概念。RE `AGENTS.md` 顶部明文规定**不坍缩成一个百分比**。

RE 在这一层比 Danus **更诚实**——Danus 的"六个研究级案例"是 narrative 描述，没量化。

## 4. SKILL 设计风格对照

读了两个 Danus SKILL.md（`direct-proving` worker / `elaboration` main agent）+ 五个 RE SKILL.md，**Danus 的 SKILL 写得明显更厚、更结构化**。

### 4.1 形态差异

| 维度 | Danus SKILL | RE SKILL |
|---|---|---|
| 长度 | 200-300 行（含表格、JSON 模板） | 50-150 行（段落 + 简短列表） |
| 触发 | description 4-6 句（"Screen a decomposition plan..."） | description 1-2 句（"Load when..."） |
| 输入输出契约 | 显式 "Input Contract" / "Output Contract" 段 | 隐式散在正文里 |
| 模板不变式 | "Template invariants" 段 + 7 个 UPPERCASE 状态标签强制 | 没有 |
| 工具表 | "Tools" 段列具体 MCP 工具名 | 散在正文 |
| Failure Logging | 独立段 | 散在正文 |

### 4.2 哪些 RE 学得到

| 学到的 | 实施成本 | 价值 |
|---|---|---|
| "Input Contract / Output Contract" 显式段 | 低（每个 skill 加 2 段） | 高（router 一眼分清边界） |
| "Template invariants" + 强制状态标签 | 低（写一份不变量清单） | 中（防止 elaboration 风格漂移） |
| "Failure Logging" 段 | 低 | 中 |
| 工具表独立段 | 低 | 中（router 知道该用哪个 MCP） |

**但有一个 RE 自己的特色要保留**：RE 的 **description 是 trigger + 互斥点双段**（我刚做的 deep fix），这是 RE 独有的——Danus 的 description 是"什么时候 + 做什么"单段，**没有显式互斥**。这是 deep fix 的实质价值，不应该照搬 Danus 退回去。

## 5. 总判断

**RE 的设计骨架和 Danus 高度同构**，差异主要在：
1. **研究对象不同**（coding agent vs 数学定理）→ 决定 verifier 的实现不同
2. **RE 没有独立 verifier**（最大的能力缺口）
3. **RE 没有 wall-clock 心跳**（第二个能力缺口）
4. **RE 的 cross-session state + architect signal 比 Danus 严格**
5. **RE 的 SKILL 风格比 Danus 轻**——这是双刃剑：轻 = 易维护 / 重 = 行为可预测

**RE 不需要照搬 Danus**。但有两个具体能力可以借：
- **`verify-evidence` skill**（独立 cold-start verifier）
- **`research-engineering` 的 30 min wall-clock 心跳**

其他差异是"研究对象不同"自然带来的，不该强求对齐。
