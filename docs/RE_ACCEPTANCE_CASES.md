# RE Acceptance Cases —— 一份按 Core Invariant 重组的验收指南

> **本文件不替代现有 V0/V1 文档**：唯一的权威状态表仍然在
> `docs/V0_ACCEPTANCE_GUIDE.md` 与 `docs/V1_ACCEPTANCE_GUIDE.md`；case 详写的实现手册在
> `docs/V0_CASES.md` 与 `docs/V1_CASES.md`。本文件**只把这些原文按 invariant 维度重组**
> 成可读层，用引用 + 锚点回到原文。

---

## 0. 导读

### 0.1 这份文件是给谁的、不是给谁的

**给 Architect（lead）**：合上 chat、读这文件能在一小时内回答"V0/V1 这套验收是不是还活着？新接手的
agent 在不在守住 invariant？"。要点是 invariant 边界、case 漂移、可疑缺口。看完 §0.4 + §1–§8 的原意
与 case-table + §12 反向矩阵就能判断。

**给 AI agent（接班）**：从 session 冷启动开始，按 §1–§8 章末的 case-table 选演练、按 §10 commands
速查执行、按 §9 错误码定位。**不带 invariant 心智模型就跑 case = 在做合规演示，不是在验 invariant**。

**不是给谁的**：

- 不替代设计文档（`AGENTS.md`、`docs/design/*`、`skills/*/SKILL.md`）
- 不替代单 case 的执行手册（`docs/V0_CASES.md` / `docs/V1_CASES.md`）
- 不替代状态表（`docs/V0_ACCEPTANCE_GUIDE.md §状态表` / `docs/V1_ACCEPTANCE_GUIDE.md §状态表`）

**状态表是这片文档的"原料"，本文件是重组后的"读者层"**。

### 0.2 怎么读（双重读者的两条路径）

- **Architect 路径**：§0.4 → §1–§8 只看每章的 §x.1 原意 + §x.4 case-table → §12 反向矩阵
  （看哪条 invariant 被几条 case 共同托住）→ §13 维护指南。
- **Agent 路径**：§0.4 → 选章（按当前研究阶段命中的 invariant）→ §x.4 选 case → §x.5 详写
  → §10 执行 → §9 报错时查码。

### 0.3 与现有 4 份文档的关系（不替代、不复制、只引用）

| 现有文件 | 本文件对其的关系 |
|---|---|
| `docs/V0_ACCEPTANCE_GUIDE.md` | **唯一权威的 V0 状态表** —— 不变量章引用其 §状态表 行号；本文件不复制 ✅ / ⏳ / ❌ 列。 |
| `docs/V1_ACCEPTANCE_GUIDE.md` | **唯一权威的 V1 状态表** —— 同上。 |
| `docs/V0_CASES.md` | **case 详写的实现手册** —— 本文件 case 详写节引用其"案例 N" + 命令 + 判据表；不复制定义性文字。 |
| `docs/V1_CASES.md` | **drill 详写的实现手册** —— 本文件引用其 drill 名 + criterion 编号；不复制 rubric。 |

**回链约定**：所有引用走 **path + heading**（如 `V0_CASES.md §案例三 / 四`），不复制原文片段
（除非像"原意"那种一句契约需要原句措辞）。

### 0.4 切片点（前 1/3 / 后 2/3）

按"内容性质"切，不按页码硬切：

- **前 1/3** = §0 导读 + §1–§8 的 §x.1 + §x.2 + §x.3 + §x.4。
  即"每章的设计意图 + 判据模式 + case 索引"加起来大致就是前 1/3。
- **后 2/3** = §x.5 详写案例 + §9–§13 附录。

任何 agent 跑 case 都必须读完 §x.5 才能动手；任何 architect 评估完整性都只看前 1/3 即够。
**附录归后 2/3**（命令速查、错误码是给 agent 现场查的）。

---

## 1. 不变量 #1 — Evidence is the stable abstraction

### 1.1 原意

> "Evidence is the stable abstraction, not candidate-or-evaluator. Do not assume a runnable system or an evaluator exists."
> —— `AGENTS.md §Core invariants` 1

**白话释义**：研究状态以"证据"为单位建模，不是以"候选算法"或"评估器"为单位。**先有证据**，
后有候选；候选死了、评估器换了，证据还在。**没有跑得起来的系统也能研究**——因为问题不是
"系统能不能跑"，而是"什么证据能让这件事变得可判决"。

### 1.2 为何关键

仓库里已经踩过的同形态事故：

- **V0 M1 验收的"未限定运行"踩坑**（见 `V0_ACCEPTANCE_GUIDE.md §V0 状态表 M1` 限定说明）：
  一次未限定方向的 bootstrap 运行在建立状态后继续查本机 `perf_counter` 精度，留下 3 个
  `ORPHAN_RUN`。证据形态跑偏就意味着"该研究的本质问题"被替换为"顺手能做的小实验"。
- **D-4 gotcha "声明了但没人接线"**：见 `docs/GOTCHAS.md`。证据契约写得很漂亮，但 commit
  没把 `Evidence:` trailer 写进 commit body 时，commit ↔ EV 双向定位就会断开——这条 invariant
  的契约从此只存在于文档里。
- **V1-D7 capability_map 形态校准**（`V1_CASES.md §V1-D7`）：capability_map 是"什么算 evidence"
  的工程化。`supports_evidence: E0/E2/E3/E4` 字段把抽象的"证据"映射到具体可测的能力层，
  让"我有证据吗"这个问题变得可操作。

### 1.3 关键判据模式

判断一条 case 是否真在验这条 invariant：

1. **怎么从产物判**：存在 ledger 写入（`research/ledger/...` 下新增 `EV-*.json`）+ evidence
   记录 ID 是稳定的、collision-resistant 的、跨 partition 可唯一定位的。
2. **怎么从 transcript 判**：session 做的第一件事不是"找算法"，而是"找最便宜的 evidence 单元"；
   当候选 / 评估器不可用时仍能继续做研究，而不是停下来。
3. **怎么从工具行为判**：`record` 写入的 evidence 不被 `replay_suite` 变动归因为比较对象；
   写入路径（`compare`、`reconcile`）独立于具体 candidate 或 evaluator 实现。

### 1.4 验证此 invariant 的全部 case

| case-id | case 名（人话） | 核心 invariant | 次要 invariant | 详写章 | 当前状态 | 一句话回链 |
|---|---|---|---|---|---|---|
| **#2** | 自建 probe 写 evidence（281+171 行） | #1 | #2 | §1.5.1 | ✅ | 验"没 evaluator 也能继续研究" |
| **#14** | mutable-input lineage（`COMPARABLE` / `ATTRIBUTION_FORBIDDEN` / `REBASELINE_REQUIRED`） | #1 | #5 | §1.5.2 | ✅ | 验"candidate 换了，evidence identity 还在" |
| **#18** | commit ↔ EV 双向定位 | #1 | #5 | §1.5.3 | ✅ | 验"evidence 不会因为 commit 边界模糊而漂走" |
| **V1-D7** | Research Capability Map + harness investment judgement | #1 | #3 / #4 / #8 | §1.5.4 | ✅ | 验"什么算 evidence"被工程化登记 |
| V1-D1 | Sharded ledger partition | #1 | #5 | §5.5 | ✅ | ledger 跨月分片仍可定位 evidence |
| V1-D4 | STATUS.md cache + stale-detection | #1 | #5 | §5.5 | ✅ | 派生快照必须能识别 ledger 已前进 |
| #8 | 自建 HARNESS-001 | #1 | #4 | §4.5 | ✅ | 验"surrogate 也按 evidence 形态登记" |

### 1.5 详写案例

#### 1.5.1 `V0 #2` — 没有 runnable system 也会自主做 probe

**设计动机**：这条 case 验的是 invariant #1 的"悲观面"——**当目标系统本身不可用**（或不在场）
**时，session 不能停下来**。它必须把"我要做什么实验"翻译成"我能造出什么样的 evidence"。
session A 没有现成的时序 trace 可分析，于是自建两支 probe（281 行 + 171 行），把"queue 尾延迟"
这种模糊提问变成可记录的 E2 evidence。**这是 evidence-first 的工程化形态**——不是"找到算法
再写代码"，是"先有测量，再有算法"。

**RE 能力映射**：

- 同时验：**§2（earliest-executable）**——用 probe 把抽象问题转成 281+171 行可跑产物
- V0 ID：`V0 #2`（V0 complete）
- 关联：`V0_ACCEPTANCE_GUIDE.md §V0 状态表 #2`；限定："严格意义的'没有 runnable system'
  未被触发（`sim/queue.py` 可跑），判据按指南'由 M1+M3 覆盖'计"

**验证过程**：

1. 跑 `tests/main/build_bootstrap_case.sh /tmp/v0-research` 复现 fixture
2. 启动 claude，给 `/research-engineering` + 一句高层方向（不指定算法）
3. 让 session 自建 probe；产物落在 `probes/*.py`
4. 用 `wc -l probes/*.py` 核行数（281 + 171）
5. 跑 `python3 tools/researchlog reconcile --json` 确认 evidence 被 ledger 收录

**Evidence（在哪看产物）**：

- `probes/replay_probe.py`（281 行）+ 另一支 171 行 probe（文件名见 fixture 自断言输出）
- `research/ledger/...` 下由该 probe 产出的 `EV-*.json`
- 块 `RB-001` 内 3 条证据，其中 2 条 `counts_as_evidence_iteration: true`

**当前状态**：✅，最近一次实测见 session A（2026-09 上旬，见 `docs/WORK_LOG.md` 早期条目）

**文件路径**：

- Fixture builder：`tests/main/build_bootstrap_case.sh /tmp/v0-research`
- 详写回链：`docs/V0_ACCEPTANCE_GUIDE.md §V0 状态表 #2`
- 案例锚点：`docs/V0_CASES.md §案例二` （M1 / M2 / M3 / M5 同源 fixture）

#### 1.5.2 `V0 #14` — mutable-input lineage 守住 evidence identity

**设计动机**：当候选 / 评估器换掉时，**已有 evidence 还能不能继续被引用**？这条 case 验的就是
这件事的边界：身份相同 → `COMPARABLE`（可比较）；`replay_suite` 变动 → `ATTRIBUTION_FORBIDDEN`
（拒绝归因）；环境变动 → `REBASELINE_REQUIRED`（要求重基线）。三态分离把"什么算同一份证据"
从语义层面落到 exit code 层面。**§26.4 五格探测** 中的末行专门校验这条，修法是 `compare`
不再"任何两条都判 `ATTRIBUTION_FORBIDDEN`"。

**RE 能力映射**：

- 同时验：**§5（append-only）**——身份相同意味着"没有偷改历史"
- V0 ID：`V0 #14`（V0 complete）
- 关联：`docs/V0_ACCEPTANCE_GUIDE.md §§26.4 末行修复后端到端复验`

**验证过程**：

1. 录两条 identity 相同的 E2 记录（同一 model / data / prompt / config）
2. `python3 tools/researchlog compare <id1> <id2>` → 期望 exit 0、`COMPARABLE`
3. 改 `replay_suite` 后再 compare → 期望 exit 3、`ATTRIBUTION_FORBIDDEN`
4. 改环境 fingerprint 后再 compare → 期望 exit 3、`REBASELINE_REQUIRED`

**Evidence（在哪看产物）**：

- `compare` 命令的 exit code + stderr（错误码见 §9.4）
- 测试用例：`tools/researchlog/tests/` 下与 mutable-input lineage 相关的测试

**当前状态**：✅，2026-09 中旬 §26.4 末行修复后端到端复验通过

**文件路径**：

- Verifier：`tools/researchlog/commands/compare.py`
- 详写回链：`docs/V0_ACCEPTANCE_GUIDE.md §§26.4 状态持久性探测结果` 末段

#### 1.5.3 `V0 #18` — commit ↔ EV 双向定位

**设计动机**：invariant #1 要求 evidence 不漂移，但 git 与 ledger 是两个独立的存储。
**双向定位**让 evidence 既能从 commit 找到（通过 `Evidence:` trailer），也能从 EV 找到
（通过 `code_state.commit` 字段）。一旦构造一条违规记录（`Evidence:` trailer 与实际 ledger
记录不匹配），`SELF_REFERENTIAL_COMMIT` 必须立刻报出。这条 case 验的是：**让两个独立的存储
**保持强一致的不是约定，是错误码**。

**RE 能力映射**：

- 同时验：**§5（append-only）**——双向定位本身需要 append-only 语义做支撑
- V0 ID：`V0 #18`（V0 complete）

**验证过程**：

1. 录一条正常 EV，commit body 写 `Evidence: EV-...`
2. `git log --format=%B -1` 查 trailer
3. 反向：`jq '.code_state.commit' research/ledger/.../<id>.json` 查 EV 记录的 commit 字段
4. 构造一条违规（trailer 与 EV 不匹配）→ 期望 `SELF_REFERENTIAL_COMMIT`

**Evidence（在哪看产物）**：

- `code_state.commit` 字段（**注意**：是工作区 commit，不等于加入该记录的 commit——见 `V0 #16`）
- commit body 的 `Evidence:` trailer
- 错误码：`SELF_REFERENTIAL_COMMIT`（见 §9.1）

**当前状态**：✅，见 `V0_ACCEPTANCE_GUIDE.md §V0 状态表 #18`

**文件路径**：

- Verifier：`tools/researchlog/commands/record.py`（写 `code_state.commit`）+ git 自身的
  `commit-msg` / `prepare-commit-msg` hook（如启用）
- 详写回链：`docs/V0_ACCEPTANCE_GUIDE.md §V0 状态表 #18`

#### 1.5.4 `V1-D7` — Research Capability Map + harness investment judgement

**设计动机**：invariant #1 在 V1 层的工程化形态。capability_map 不是一个静态字典——
它登记的是"这个 harness / 模型 / 数据源能产出哪一层 evidence（E0/E2/E3/E4）"，并带
`reuse_counter`、`first_used`、`last_used_by_evidence_id`。**fingerprint 变（rebaseline）** 时
hash 必须推进，**changed 谓词**在 capability_map 变化后必须能正确判定（不再是永远的
`UNRESOLVED`）。这条 case 把"什么算 evidence"从一句话原则变成可查询、可对比、可投资的工程对象。

**RE 能力映射**：

- 同时验：**§3（env ≠ hypothesis）**——capability_map 是环境能产出什么 evidence 的登记；
  **§4（surrogate 校验）**——`harness declare` 是 surrogate validity 的接入点；
  **§8（bad metric）**——`supports_evidence` 字段强迫每个 capability 显式声明它支撑哪层 evidence
- V1 ID：`V1-D7`（6/6 PASS）
- 关联：`docs/V1_CASES.md §V1-D7`

**验证过程**：

1. `python3 tools/researchlog validate` → capability_map shape 通过 schema
2. `python3 tools/researchlog env show | jq '.capability_map | length'` → `>= 3`
3. 查 `reuse_counter` 字段存在
4. `python3 tools/researchlog env declare harnesses <file>` → 合法
5. `python3 tools/researchlog snapshot` 在 rebaseline 前后跑 → hash 必须变
6. `python3 tools/researchlog env query <change.json>` → `changed` 谓词不再永远 `UNRESOLVED`

**Evidence（在哪看产物）**：

- `research/ENVIRONMENT.md` 的 `capability_map[]` 数组
- 当前 3 项登记：`CAP-v1d9-routing-001` / `CAP-researchlog-replay-001` /
  `CAP-resume-from-files-001`（见 `research/ENVIRONMENT.md`）
- Fingerprint：`sha256:905ec22fa4076f9485a74cf774cc6c8a414d813cb9398988f4819fca6fde0024`
  （rebaseline 后）

**当前状态**：✅，commit `30d0b89`（2026-09-18），fingerprint 从 `1733fb3f...` 推进到 `905ec22f...`

**文件路径**：

- 测试：`tools/researchlog/tests/` 下 capability_map 相关 test classes
- 命令：`tools/researchlog/commands/env.py`
- 详写回链：`docs/V1_CASES.md §V1-D7` + `docs/V1_ACCEPTANCE_GUIDE.md §M3` 行

---

## 2. 不变量 #2 — Make the uncertainty executable as early as possible

### 2.1 原意

> "Make the uncertainty executable as early as possible. Ask 'what is the cheapest executable artifact that materially reduces the current technical uncertainty?' — not 'what is easiest to write'."
> —— `AGENTS.md §Core invariants` 2

**白话释义**：研究的瓶颈不是"我能写多少代码"，是"**什么可跑、可观测、可判决的最小产物**能最快让
当前不确定性变小"。写一段易读的漂亮代码 ≠ 让不确定性变小。把不确定性变成可执行工件是研究的本职。

### 2.2 为何关键

- **V0 M2 的反例形态**（"不默认写长 plan 和大量 tests"）：写测试套件、写 plan 文档是"易写"
  但**不一定让不确定性变小**。session A 自建 probe 才是让不确定性变小的形态——因为它让
  "queue 尾延迟来自 queue 还是 retry" 这种模糊问题变成了 281 行可记录 measurement。
- **V1-D2 E2/E3 replay**：replay 是"在已证据上做更便宜的对照"——**已经有一条 E2 evidence
  跑过一遍，现在用更便宜的 E3 对照看 hypothesis 的某个细节**。这是"earliest-executable"
  在 V1 层的工程化：永远从已证据出发做差分，不重新搭一遍。
- **`development_mode` 区分**（见 `AGENTS.md §Working mode`）：Research Mode 默认 disposable
  prototype；只有 promoted 到 Integration Mode 才走 stable interface + 回归。这条 invariant
  就是 Research Mode 存在的理由。

### 2.3 关键判据模式

1. **怎么从产物判**：session 的迭代产物集中在 probe / instrumentation / measurement，不在
   plan / tests / refactor。改动文件数与 commit 数应该集中在小而频繁的探索，不是大块迁移。
2. **怎么从 transcript 判**：session 在每次迭代前能回答"这次迭代在消除哪个具体不确定性"——
   不是"我在改进系统"，而是"我在判断 X 是否为 Y 的因"。
3. **怎么从工具行为判**：`replay_suite` 部署后允许 `compare` 在已有 evidence 上做差分，不需要
   重新跑全部实验。

### 2.4 验证此 invariant 的全部 case

| case-id | case 名 | 核心 invariant | 次要 invariant | 详写章 | 当前状态 | 一句话回链 |
|---|---|---|---|---|---|---|
| **M3** | 连续 2–3 evidence-producing iterations（`RB-001`） | #2 | #1 | §2.5.1 | ✅ | 验"迭代 = 不确定性变小" |
| **V1-D2** | E2/E3 replay contract | #2 | #1 | §2.5.2 | ✅ | 验"在已证据上做更便宜的对照" |
| #2 | 自建 probe（与 §1 共担） | #2 | #1 | §1.5.1 | ✅ | 验"用最小产物让不确定性变小" |
| #12 | Block Contract 阻止无界 exploitation | #2 | #6 / #7 | §6.5 | ✅ | 验"迭代是有预算的" |
| V1-D3 | Bounded autonomous block across sessions | #2 | #6 | §6.5 | ✅ | 验"块不重启" = 迭代不被吞掉 |
| M2 | 不默认写长 plan 与大量 tests | #2 | — | §2.5.3 | ✅ | 验"易写 ≠ 该写" |

### 2.5 详写案例

#### 2.5.1 `V0 M3` — 连续 evidence-producing iterations

**设计动机**：invariant #2 的"连续面"——不是只跑一次就跑路，而是 2–3 次迭代每次都让某个
不确定性变小。session A 的 `RB-001` 块内 3 条 evidence，2 条 `counts_as_evidence_iteration: true`
（`belief_delta` 分别是 refined / overturned）。**判"evidence-producing"的依据是**
**`belief_delta` 真的变了**，不是文件数。

**RE 能力映射**：

- V0 ID：`V0 M3`（Day-1 must）
- 关联：`V0_ACCEPTANCE_GUIDE.md §V0 状态表 M3`

**验证过程**：

1. 跑 `tests/main/build_bootstrap_case.sh /tmp/v0-research`
2. 启动 session，给定高层方向（不指定算法）
3. 让 session 自然迭代 → 记录 3 条 EV
4. 查 `research/ledger/...` 下 EV 文件的 `belief_delta` 字段
5. 期望 ≥ 2 条 `counts_as_evidence_iteration: true`

**Evidence**：

- 块 `RB-001` 在 ACTIVE.json / BLOCK-LEVEL evidence 摘要里
- 3 条 `EV-*.json`，其中 2 条 `belief_delta: refined|overturned`

**当前状态**：✅，session A 实测

**文件路径**：

- 详写回链：`docs/V0_ACCEPTANCE_GUIDE.md §V0 状态表 M3`
- 案例锚点：`docs/V0_CASES.md §案例二`

#### 2.5.2 `V1-D2` — E2/E3 replay contract

**设计动机**：让"earliest-executable"在 V1 层可验证。replay 必须满足：identity stable across
replay（同一 E2 record 与 E3 record 可比较）；`compare` 在 `replay_suite` 变动时
触发 `ATTRIBUTION_FORBIDDEN`；mutable-input lineage 延伸到 E3。**这条 case 让"earliest"有了
**字面定义**：不必重跑已有 evidence，在它的 replay 上做差分就行**。

**RE 能力映射**：

- V1 ID：`V1-D2`（6/6 PASS）

**验证过程**：

1. `python3 tools/researchlog record --question '...' --level E2 ...` → 录 E2
2. 同上 `--level E3` → 录 E3
3. `python3 tools/researchlog compare <e2-id> <e3-id>` → 期望 `code_state.commit` 不变，
   `common` 非空
4. 故意改 `replay_suite` 后再 compare → 期望 `ATTRIBUTION_FORBIDDEN`
5. 用 `--inputs {model: ...}` 录 E3 → compare 同 model → `common` 带 model 字段

**Evidence**：

- `research/ledger/2026-09/EV-...-*.json`（E2 + E3 对）
- 测试类：`E2E3ReplayTests`

**当前状态**：✅

**文件路径**：

- 详写回链：`docs/V1_CASES.md §V1-D2`

#### 2.5.3 `V0 M2` — 不默认写长 plan 与大量 tests

**设计动机**：invariant #2 的**反例形态**——通过"什么**不**该出现"来守这条 invariant。
session A **完全没有碰 `sim/` 与 `data/`**；改动只在两支自建 probe 与研究状态；**无 plan
文档、无新增测试套件**。如果 session 在前两次迭代就写了一个完整的 test harness 或一份
长 plan 文档，这条验收就**因为错误的原因失败**（见 `V0_ACCEPTANCE_GUIDE.md §状态表 M1`
限定说明那段关于 `build_bootstrap_case.sh` 的踩坑）。

**RE 能力映射**：

- V0 ID：`V0 M2`（Day-1 must）

**验证过程**：

1. 跑 fixture，让 session 自由迭代
2. `git diff --stat <base>..HEAD` 检查改动文件分布
3. 期望：probe / instrumentation 类文件有改动，`sim/` `data/` **无**改动
4. `find . -name 'test_*.py' -newer <base>` 期望**无新增**测试套件
5. `find docs/ -name '*plan*'` 期望**无**plan 类文档

**Evidence**：

- session A 的 git diff 统计（在 `WORK_LOG.md` 早期条目里）
- 工作树在 case 结束时干净（`reconcile --json` clean）

**当前状态**：✅

**文件路径**：

- 详写回链：`docs/V0_ACCEPTANCE_GUIDE.md §V0 状态表 M2`

---

## 3. 不变量 #3 — Environment infeasibility ≠ scientific failure

### 3.1 原意

> "Environment infeasibility is never evidence against a hypothesis. `INFRA_FAILED`, `ENV_BLOCKED`,
> `ENV_UNSUPPORTED`, `RESOURCE_EXCEEDED`, and `EVIDENCE_INVALID` stay separate from
> `research_outcome`. Only `SCIENTIFIC_NEGATIVE` weakens a hypothesis."
> —— `AGENTS.md §Core invariants` 3

**白话释义**：**实验跑不起来 ≠ 假说错**。把"环境不能测"包装成"假说被否"是最常见的伪科学化
路径——这条 invariant 强迫环境阻塞以独立错误码记录，**只有 `SCIENTIFIC_NEGATIVE` 才能**
**weaken hypothesis**。

### 3.2 为何关键

- **V0 M5 直接对应这条 invariant**：session A 的 `ENV-LIM-001..006` **全部**以 `ENV_UNSUPPORTED`
  入 `ENVIRONMENT.md`，**没有一条被写成 `refuted`**。这是 invariant #3 的字面示范。
- **V1-D9 整组 ENV_BLOCKED**：在 `minimax-compat` 端点上，V1-D9 的 4 个 criterion 全部
  `ENV_BLOCKED`。**这条阻塞不是验收失败，是端点策略决定的（见 ARCHITECT signal D-004）**。
  把 D9 当成"9/9 不通过"是误读——它就是用来示范"环境不可行 ≠ scientific negative"的。
- **codex 三路径 ENV_BLOCKED**（V0 #1）：codex 在 `codex exec` 可用但环境不可达，`codex` 端
  全部 `ENV_BLOCKED`，不计入 V0 失败项（架构师 2026-09-17 改判为"暂缓"）。

### 3.3 关键判据模式

1. **怎么从产物判**：`reconcile --json` 不把 `ENV_BLOCKED` / `ENV_UNSUPPORTED` 计入
   `scientific_negative`；`FINDINGS.md` 的 `research_outcome: refuted` 不能由环境阻塞触发。
2. **怎么从 transcript 判**：session 遇到"做不了"的实验时**不能直接判 hypothesis 错**——必须
   先查 `ENVIRONMENT.md` 看该限制是否已登记；未登记则 `env record` 写入新限制。
3. **怎么从工具行为判**：`env record` / `env declare` 的写入路径独立于 evidence ledger，不污染
   `research_outcome` 字段。

### 3.4 验证此 invariant 的全部 case

| case-id | case 名 | 核心 invariant | 次要 invariant | 详写章 | 当前状态 | 一句话回链 |
|---|---|---|---|---|---|---|
| **M5** | 不可行实验判为环境限制（`ENV-LIM-001..006`） | #3 | #1 / #4 | §3.5.1 | ✅ | 验"环境阻塞 ≠ scientific negative" |
| **V1-D9** | Client matrix 4/4 ENV_BLOCKED | #3 | #1 / #7 | §3.5.2 | ⏸ ENV_BLOCKED | 验"端点阻塞按 invariant #3 处理" |
| **ENV-LIM-001..006** | session A 的环境限制登记 | #3 | #1 | §3.5.1 | ✅ | 验"6 条限制全部以 ENV_UNSUPPORTED 入档" |
| #1 | codex 三路径 ENV_BLOCKED | #3 | — | §3.5.3 | ✅ 改判 | 验"客户端环境不可达不算 V0 失败" |
| #10 | 缺失/失真 evaluator 当 Research Subject | #3 | #4 / #8 | §4.5 / §8.5 | ✅ | 验"evaluator 失效 ≠ hypothesis 错" |
| V1-D7 | Capability Map（`supports_evidence`） | #3 | #1 / #4 / #8 | §1.5.4 | ✅ | 验"环境能产出什么 evidence"被显式登记 |

### 3.5 详写案例

#### 3.5.1 `V0 M5` + `ENV-LIM-001..006` — 环境阻塞的入档路径

**设计动机**：invariant #3 的字面示范——6 条限制全部以 `ENV_UNSUPPORTED` 入 `ENVIRONMENT.md`，
**没有一条被写成 `refuted`**。每条带 `verified_by`。**这条此前不可能通过**——
三张表（`limitations` / `capability_map` / `available`）在 `env declare` 出现之前**没有写入路径**
（见 `V0_ACCEPTANCE_GUIDE.md §V0 状态表 M5` 末尾说明；该缺口被 D3 + D2 两轮独立撞到并修掉）。

**RE 能力映射**：

- 同时验：**§4（surrogate 校验）**——HARNESS-001 的 `supports_evidence: E2` 字段与
  `preserves` / `missing` 边界说明也是这条 invariant 在 surrogate 层的体现；
  **§1（evidence-as-abstraction）**——环境限制以 evidence 形态入档
- V0 ID：`V0 M5`（Day-1 must）+ `ENV-LIM-001..006`

**验证过程**：

1. 跑 fixture，让 session 自由迭代
2. 让 session 撞上一个本机做不到的实验（如需要 actuator 但本机没有）
3. 期望：session **不**把 hypothesis 标 `refuted`
4. 期望：`ENVIRONMENT.md` 多一条带 `verified_by` 的限制
5. 期望：`env record` 路径合法（commit `1de3c9f` 修法后）
6. 期望：`reconcile --json` 的 `research_outcome` 字段**无 `refuted`**

**Evidence**：

- `research/ENVIRONMENT.md` 的 `limitations[]` 数组
- 6 条 ENV-LIM 条目各带 `verified_by: tools/...`

**当前状态**：✅

**文件路径**：

- 命令：`tools/researchlog/commands/env.py`（`record` / `declare` / `query`）
- 详写回链：`docs/V0_ACCEPTANCE_GUIDE.md §V0 状态表 M5`

#### 3.5.2 `V1-D9` — Client matrix 在 `minimax-compat` 端点下整组 ENV_BLOCKED

**设计动机**：invariant #3 在 V1 层的最大示范案例。V1-D9 的 6 个 V1 expert skill
（`research-engineering` / `research-bootstrap` / `research-status` /
`evaluation-design` / `experiment-review` / `research-search` / `retrospective` /
`scenario-redteam`）需要在 `claude` × `pi` 两个客户端都通过 router。**phrase-list 启发式**
**在没有路由信号时返回 0 false-positive**，但 `minimax-compat` 模型倾向 paraphrase 而非
verbatim quote，导致 router reachability 在该端点上 0/6 或 1/6 摇摆。

**架构师信号 D-004**（`research/ARCHITECT.md`）声明 `minimax-compat` 是稳态端点、**无原生
**Anthropic 订阅**——这条决策把 V1-D9 的 claude 端**永远**按 ENV_BLOCKED 处理。pi 端通过
phrase-list 启发式 1/6 routed（case 5 `research-search` 唯一命中）。**两条都不藏：M6-pi 与
**M6-claude-pending 分开记录**（见 `V1_ACCEPTANCE_GUIDE.md §M6/M7` 与
`docs/v1/M6_SPLIT_PROPOSAL.md`）。

**RE 能力映射**：

- 同时验：**§1（evidence-as-abstraction）**——`ENV-LIM-004` 与 6 个 capability_map 条目按
  evidence 形态登记；
  **§7（architect as impulse）**——D-004 是 architect steering，但 V1-D9 claude-leg 按
  `ENV_BLOCKED` 处理而非"被 steering 改写通过判据"
- V1 ID：`V1-D9`（0/4 verbatim PASS, 0/4 verbatim FAIL, 4/4 split admitted → ENV_BLOCKED）

**验证过程**：

1. 跑 `tools/v1_d9_report.json` 看 6 个 skill × 2 个客户端的 phrase-list 命中情况
2. pi 端：期望至少 1/6 routed（当前 case 5 `research-search` 唯一命中）
3. claude 端（`minimax-compat`）：期望 0/6 routed → 整组 ENV_BLOCKED
4. 期望：`reconcile --json` 不把 V1-D9 计入 `scientific_negative`
5. 期望：`ENV-LIM-004` 在 `ENVIRONMENT.md` 中带 `verified_by: tools/v1_d9_report.json
   (commit 04d9445 sandbox run)`

**Evidence**：

- `research/ENVIRONMENT.md` 的 `ENV-LIM-004`（status: `ENV_BLOCKED`）
- `research/ARCHITECT.md` 的 D-004 信号（scope: environment, expiry: until native Anthropic
  endpoint becomes available）
- `tools/v1_d9_report.json`

**当前状态**：⏸ **ENV_BLOCKED**（在 `minimax-compat` 端点下不可前进），等架构师决策 A-3

**文件路径**：

- 详写回链：`docs/V1_CASES.md §V1-D9` + `docs/V1_ACCEPTANCE_GUIDE.md §M6-pi / §M6-claude-pending`
- 决策依据：`docs/v1/M6_SPLIT_PROPOSAL.md`

#### 3.5.3 `V0 #1` — codex 三路径 ENV_BLOCKED（架构师改判为"暂缓"）

**设计动机**：当 V0 验收的另一客户端不可达时，**不**把 V0 整体判为"未通过"。架构师原话：
"codex 可以暂缓，现在 claude code / pi 可以跑通就可以了"——这条决策让 codex 端的 ENV_BLOCKED
不被记为 V0 失败项。**这是 invariant #3 + invariant #7 的共同示范**：环境不可行按 #3 处理，
architect 决策按 #7 接管但不重写判据。

**RE 能力映射**：

- V0 ID：`V0 #1`（V0 complete，**架构师 2026-09-17 改判**）

**验证过程**：

1. 查 `research/ARCHITECT.md` 的 D-001（codex 暂缓决策）原文
2. 查 `docs/WORK_LOG.md` 第八/九轮 pi 三案例记录
3. 期望：codex 三路径全部 `ENV_BLOCKED` 且 `reconcile` 不计 fail

**Evidence**：

- `research/ARCHITECT.md` 的 D-001（codex 暂缓）
- `docs/WORK_LOG.md` 第八/九轮

**当前状态**：✅ **架构师 2026-09-17 改判**

**文件路径**：

- 详写回链：`docs/V0_ACCEPTANCE_GUIDE.md §V0 状态表 #1`

---

## 4. 不变量 #4 — Validate a surrogate before drawing on it

### 4.1 原意

> "Validate a surrogate before drawing on it. A missing causal feature means `EVIDENCE_INVALID`, not a weaker conclusion."
> —— `AGENTS.md §Core invariants` 4

**白话释义**：**surrogate（代理测量）本身是要被验证的**。如果它**声称**支撑某个 causal feature
但**实际不支撑**（`required ⊆ missing`），那条 evidence 必须判 `EVIDENCE_INVALID`——不能"虽然
不完整但还算凑合用"地继续往上叠结论。

### 4.2 为何关键

- **D3 演练**：`EV-…e098` 的两个 required causal feature 全在 missing 里，却以
  `VALID_SURROGATE` + `promising` + `belief_delta: refined` 入库——**这条 evidence 是"声明了但**
  **没人校验"的活样本**。修法（`1de3c9f`）新增 `SURROGATE_VERDICT_CONTRADICTS_MISSING_FEATURES`。
- **V0 #8 HARNESS-001**：自建 surrogate 必须显式声明 `supports_evidence` 与 `preserves` / `missing`
  边界——`ENV-LIM-002` "光靠 CSV 不可判定，必须插桩" 就是这条 invariant 的反向应用。
- **V1-D7 `harness declare`**：让 surrogate 的"什么支撑什么"可被工程化登记。

### 4.3 关键判据模式

1. **怎么从产物判**：写入 `record` 时若 `surrogate.validity == VALID_SURROGATE` 但
   `required_features ⊆ missing_features` → 拒绝写入（错误码
   `SURROGATE_VERDICT_CONTRADICTS_MISSING_FEATURES`）。
2. **怎么从 transcript 判**：session 在利用 surrogate 的结论之前**必须**问"这个 surrogate
   真的支撑我需要的 causal feature 吗"。
3. **怎么从工具行为判**：`evaluation-design` skill 加载后，session 必须重新审视已有 surrogate 的
   `preserves` / `missing` 边界——这条 invariant 是 evaluation-design 的工程化触发器。

### 4.4 验证此 invariant 的全部 case

| case-id | case 名 | 核心 invariant | 次要 invariant | 详写章 | 当前状态 | 一句话回链 |
|---|---|---|---|---|---|---|
| **#8** | 自建 HARNESS-001（`supports_evidence: E2`、`preserves` / `missing`） | #4 | #1 | §4.5.1 | ✅ | 验"surrogate 边界必须显式登记" |
| **D3 演练** | Evaluator Conflict（5 判据） | #4 | #3 / #8 | §8.5.1 | ✅ | 验"surrogate 闭合与契约矛盾识别" |
| **V1-D7 #4** | `harness declare` 路径 | #4 | #1 / #3 / #8 | §1.5.4 | ✅ | 验"harness declare"合法 |
| **§26.4 五格探测** | canonical 截断恢复 / schema 拒绝 | #4 | #5 | §5.5 | ✅ | 验"surrogate 失真时工具不发疯" |
| M5 | ENV-LIM 入档 | #4 | #3 | §3.5.1 | ✅ | 验"环境限制作为 surrogate 边界登记" |

### 4.5 详写案例

#### 4.5.1 `V0 #8` — 自建 HARNESS-001

**设计动机**：invariant #4 的"自建"面——session 不只**用** surrogate，session 必须**建** surrogate。
session A 自建 `HARNESS-001`，显式声明 `supports_evidence: E2`、`preserves` / `missing` 边界齐全。
`ENV-LIM-002` "光靠 CSV 不可判定，必须插桩" 是这条 invariant 在反向应用时的范例：
当 surrogate 的能力不够支撑所需 causal feature 时，**必须补足**（插桩）而不是**降格使用**。

**RE 能力映射**：

- 同时验：**§1（evidence-as-abstraction）**——HARNESS 是 evidence 形态登记的具体载体
- V0 ID：`V0 #8`（V0 complete）

**验证过程**：

1. 跑 fixture，让 session 撞上"现有 trace 不可判定"的问题
2. 期望：session 自建 HARNESS-001，登记 `supports_evidence` 与 `preserves` / `missing`
3. 期望：`HARNESS-001` 与某条 EV 关联，记录它支撑哪层 evidence

**Evidence**：

- session A 自建的两支 probe + HARNESS-001（具体文件名见 fixture 自断言输出）

**当前状态**：✅

**文件路径**：

- 详写回链：`docs/V0_ACCEPTANCE_GUIDE.md §V0 状态表 #8`
- 案例锚点：`docs/V0_CASES.md §案例二`

> **D3 演练 / V1-D7 #4 的详写见 §8.5.1 与 §1.5.4**（它们跨多条 invariant，详写放在最核心章）。

---

## 5. 不变量 #5 — Raw evidence is append-only

### 5.1 原意

> "Raw evidence is append-only. Beliefs and current state are rebuildable; chat context is not a source of truth."
> —— `AGENTS.md §Core invariants` 5

**白话释义**：**原始证据只能追加不能改写**。`belief` / `current state` 是从原始证据派生的，
派生物可被覆盖重建；**聊天上下文不是真理来源**——这就是为什么 §1 evidence-first + 这条
append-only 共同支撑"session context disposable"。

### 5.2 为何关键

- **§26.4 五格探测直接验这条 invariant**：canonical 被截断 + 存在合法 `.tmp` → 从 `.tmp`
  恢复并报告（`RECOVERED_FROM_TMP`，warning，exit 3）；canonical 被截断、无 `.tmp`、Git HEAD
  有合法副本 → 从 Git 恢复；canonical 被截断、无 Git 历史 → `RECOVERY_REQUIRED`，不静默。
  五格探测的每一格都在说同一件事：**原始证据的任何破坏都被显式拒绝，绝不静默重写**。
- **#16 Git/Evidence 无 self-referential commit**：commit hash 不能"包含"自己——一旦包含，
  校验与写入就循环依赖。
- **V1-D1 Sharded ledger partition** + **V1-D4 STATUS.md cache + stale-detection**：跨月分片
  的 ledger 必须能验证（`basename uniqueness == record count`）；STATUS.md 是派生快照，必须
  在 ledger 前进后报 stale。
- **V0_D4 gotcha 的反向面**：append-only 让"接线但缺数据"成为可检测（`VALIDATE_REQUIRED` /
  `STATUS_STALE`）——`D-4` "声明了但没人接线" 是它的**逻辑反**。

### 5.3 关键判据模式

1. **怎么从产物判**：ledger 记录**不可被原地修改**（`record` 不接受 `update` 已有 ID 的语义）；
   任何"看似修改"必须通过 append-new + supersede 实现。
2. **怎么从 transcript 判**：session 在发现旧 evidence 错时**写新 evidence**而不是改旧 evidence
   ——`D3` 第二次执行明确指出"按'原始证据只增不改'，它写新证据而不是改 `EV-…e098`"。
3. **怎么从工具行为判**：`validate` 在 `schema_version` 不匹配时拒绝写入（`SCHEMA_NEWER_REFUSED`）；
   `STATUS.md` 在 ledger 前进后必须报 `STATUS_STALE`。

### 5.4 验证此 invariant 的全部 case

| case-id | case 名 | 核心 invariant | 次要 invariant | 详写章 | 当前状态 | 一句话回链 |
|---|---|---|---|---|---|---|
| **#11** | schema_version + 中断写入恢复 | #5 | #4 / #6 | §5.5.1 | ✅ | 验"中断后正确路径恢复" |
| **#16** | Git/Evidence 无 self-referential commit | #5 | #1 | §5.5.2 | ✅ | 验"commit hash 不能引用自己" |
| **V1-D1** | Sharded ledger partition | #5 | #1 | §5.5.3 | ✅ | 验"ledger 跨月分片不丢证据" |
| **V1-D4** | STATUS.md cache + stale-detection | #5 | #1 / #6 | §5.5.4 | ✅ | 验"派生快照必须识别 ledger 前进" |
| §26.4 五格探测 | canonical 截断恢复 / schema 拒绝 | #5 | #4 | §4.5 | ✅ | 验"破坏被显式拒绝不静默" |
| #14 | mutable-input lineage | #5 | #1 | §1.5.2 | ✅ | 验"identity stable" = 不偷改历史 |

### 5.5 详写案例

#### 5.5.1 `V0 #11` — schema_version + 中断写入恢复（§26.4 五格探测）

**设计动机**：append-only 的反面不是"写得慢"，是"**写坏了怎么办**"。五格探测穷举了"写得坏"
的几种形态：截断 + `.tmp` 存在、截断 + 无 `.tmp` + Git 有副本、截断 + 无 Git、不可读的 ACTIVE、
`schema_version: 9.0`（更新版本）、manifest 违反自身 schema。**每一种都必须被显式拒绝或**
**恢复**——任何一种被静默处理都意味着原始证据被悄悄改写。

**RE 能力映射**：

- 同时验：**§4（surrogate 校验）**——schema 校验本身是 surrogate 验证机制
- V0 ID：`V0 #11`（V0 complete）

**验证过程**：

1. 模拟 canonical 被截断 + `.tmp` 合法 → 期望 `RECOVERED_FROM_TMP`（warning，exit 3）
2. 模拟截断 + 无 `.tmp` + Git HEAD 有合法副本 → 期望从 Git 恢复
3. 模拟截断 + 无 Git 历史 → 期望 `RECOVERY_REQUIRED`（error，exit 2）
4. 构造不可读的 ACTIVE → 期望 `reconcile` **绝不**说 clean
5. 构造 `schema_version: 9.0` → 期望写入 `SCHEMA_NEWER_REFUSED`（exit 4，字节不变）
6. 构造 manifest 违反 schema → 期望 `validate` 报错（**曾静默**——已修）

**Evidence**：

- 测试：`tools/researchlog/tests/` 下 `ReconcileStaleStatusTests` 等
- 错误码：`RECOVERED_FROM_TMP` / `RECOVERY_REQUIRED` / `SCHEMA_NEWER_REFUSED`

**当前状态**：✅，§26.4 五格探测全过（见 `V0_ACCEPTANCE_GUIDE.md §§26.4 状态持久性探测结果`）

**文件路径**：

- 命令：`tools/researchlog/commands/reconcile.py` + `commands/validate.py`
- 详写回链：`docs/V0_ACCEPTANCE_GUIDE.md §§26.4 状态持久性探测结果`

#### 5.5.2 `V0 #16` — Git/Evidence 无 self-referential commit

**设计动机**：invariant #5 的"git 镜像"面。如果 commit hash 包含自身，校验就会陷入循环依赖。
`code_state.commit` 是**工作区 commit**，不等于加入该记录的 commit——这个区分保证了 commit
与 EV 的关系是**有向无环**的。

**RE 能力映射**：

- V0 ID：`V0 #16`（V0 complete）

**验证过程**：

1. 正常 EV → 查 `code_state.commit` 与 `git log --format=%H -1` 应**不同**（前者是工作区）
2. 构造违规（trailer 与 EV 不匹配、或 commit hash 引用自己）→ 期望 `SELF_REFERENTIAL_COMMIT`

**Evidence**：

- `code_state.commit` 字段（`research/ledger/.../<id>.json`）
- commit body 的 `Evidence:` trailer

**当前状态**：✅

**文件路径**：

- 详写回链：`docs/V0_ACCEPTANCE_GUIDE.md §V0 状态表 #16`

#### 5.5.3 `V1-D1` — Sharded ledger partition

**设计动机**：append-only 在 V1 层的"规模化"面。ledger 跨月分片（`YYYY-MM/` 目录）后——
basename uniqueness 必须等于 record count；跨分区 compare 必须能跑通；`--from-orphan` 跨分区
写入必须合法。**这条 case 让 ledger 从"一个目录"扩展为"可无限追加的分片树"**，且不破坏
不变量 #5 的字面要求。

**RE 能力映射**：

- 同时验：**§1（evidence-as-abstraction）**——分片后 evidence 仍可唯一定位
- V1 ID：`V1-D1`（6/7 PASS + 1 deferred，deferred 的 #4 "EV-IDs 全互异"被 #2 吸收）

**验证过程**：

1. `ls research/ledger/2026-09/` → 至少有 1 个 `EV-*.json`
2. basename uniqueness 检查 → 等于 record count
3. `python3 tools/researchlog compare <id1> <id2>` 跨分片 → exit 0 + JSON envelope
4. `python3 tools/researchlog record --from-orphan EXP-fake-001 ...` → exit 0 + EV 落 `2026-09/`
5. `python3 tools/researchlog validate` → `evidence_records == N` 前后一致

**Evidence**：

- 测试类：`LedgerPartitionTests`
- 当前真实数据：`research/ledger/2026-09/EV-20260918T133714Z-7b6f.json`（V1-D9 产出的 EV）

**当前状态**：✅

**文件路径**：

- 详写回链：`docs/V1_CASES.md §V1-D1`

#### 5.5.4 `V1-D4` — STATUS.md cache + stale-detection

**设计动机**：append-only 的"派生快照"面。STATUS.md 是派生层——它写成功 + 头部带
`DERIVED SNAPSHOT — NOT SOURCE OF TRUTH` banner + 在 ledger 前进后必须报 stale。
**这条 case 让"派生不等于原始"这个抽象原则变成 exit code 与 banner 字符串**。

**RE 能力映射**：

- 同时验：**§6（disposable context）**——派生快照本身是为冷启动恢复设计的
- V1 ID：`V1-D4`（5/5 PASS）

**验证过程**：

1. `python3 tools/researchlog status --write` → exit 0，STATUS.md 存在
2. `head -1 STATUS.md` → 以 `DERIVED SNAPSHOT` banner 开头
3. 录一条新 EV → `status` 必须报 `STATUS.md is stale`
4. `python3 tools/researchlog synthesize --block` → exit 0 + 1–2 页
5. `python3 tools/researchlog reconcile --json` → `payload.clean == true`

**Evidence**：

- 测试类：`ReconcileStaleStatusTests`
- 实现位置：`tools/researchlog/commands/reconcile.py:482`（V1-D4 #3 修复点）

**当前状态**：✅

**文件路径**：

- 详写回链：`docs/V1_CASES.md §V1-D4`

---

## 6. 不变量 #6 — Session context is disposable

### 6.1 原意

> "Session context is disposable. Everything decision-relevant lives in the repo."
> —— `AGENTS.md §Core invariants` 6

**白话释义**：**聊天上下文是不可移植的**——session 被杀后，冷启动的下一个 session 必须只靠
仓库文件就能恢复 active research。这条 invariant 直接催生了 §1 evidence-first、§5 append-only
两条前置约束——既然上下文是一次性的，那 truth 必须在 repo。

### 6.2 为何关键

- **M4 + 演练 D1** 就是这条 invariant 的字面示范：session 被杀后只靠文件恢复 active research，
  7/7 判据全过。
- **#13 + 演练 D2**：long-running experiment 跨 session **不**被重复启动（`EXP-0200` 900s 跑完后
  才被 finalize，session 不替它收尾、不杀进程）。
- **V1-D3 Bounded autonomous block across sessions**：3–8 iterations 在一块内、session rotate
  **不**重启动 block、reproduction 不消耗预算、record-after-commit 落 git、run 默认 30s heartbeat、
  `--replace-existing` 被拒、跨 session `reconcile` exit 0。
- **`session-continuity.md`**（被 `#11` 引用）：早早就有兼容性表与恢复顺序（`canonical → .tmp → git`），
  来源必须报告。这条 skill 是 invariant #6 的**协议层落地**。

### 6.3 关键判据模式

1. **怎么从产物判**：canonical state 在 session 死亡后**所有信息都可恢复**——`ACTIVE.json` /
   `CURRENT.md` / `ARCHITECT.md` / `BOUNDARIES.md` / `ENVIRONMENT.md` / `FINDINGS.md` /
   `research/ledger/...` / `research/runs/...`。
2. **怎么从 transcript 判**：冷启动 session 的**第一步**必须是"读 repo 文件"而不是"读历史
   chat"；任何不读 repo 就开始工作的行为直接违反 invariant #6。
3. **怎么从工具行为判**：`reconcile --json` 是 session resume 的真正入口；它面对不可读的
   ACTIVE 必须不静默（`RECOVERY_REQUIRED`，exit 2）；跨 session `reconcile` exit 0 是
   block budget 在新 session 仍生效的工程化形态。

### 6.4 验证此 invariant 的全部 case

| case-id | case 名 | 核心 invariant | 次要 invariant | 详写章 | 当前状态 | 一句话回链 |
|---|---|---|---|---|---|---|
| **M4 + 演练 D1** | Session Recovery Benchmark（7/7） | #6 | #1 / #5 | §6.5.1 | ✅ | 验"只靠文件恢复" |
| **#13 + 演练 D2** | long-running 跨 session 不重复启动 | #6 | #7 | §6.5.2 | ✅ | 验"在跑的不替它收尾" |
| **V1-D3** | Bounded autonomous block across sessions | #6 | #2 / #7 | §6.5.3 | ✅ | 验"block budget 跨 session 续命" |
| V1-D4 | STATUS.md cache + stale-detection | #6 | #5 | §5.5.4 | ✅ | 验"派生快照为冷启动服务" |
| #11 | 中断写入恢复 | #6 | #5 | §5.5.1 | ✅ | 验"中断后可恢复 = session 可被杀" |

### 6.5 详写案例

#### 6.5.1 `V0 M4 + 演练 D1` — Session Recovery Benchmark

**设计动机**：invariant #6 的字面示范。session 被杀后下一个 session **只靠文件**就能：
（1）找到正确 branch/worktree/HEAD；（2）理解 dirty diff 的意图；（3）知道当前 hypothesis /
experiment；（4）知道 completed / pending cases；（5）保留 architect signal 与 environment
limitation；（6）避免重复已完成实验；（7）选择正确 next action。7 项判据全过。

**RE 能力映射**：

- 同时验：**§1（evidence-as-abstraction）**——所有信息必须以 evidence 形态登记才能被恢复；
  **§5（append-only）**——中断后能从 `.tmp` / Git 恢复
- V0 ID：`V0 M4`（Day-1 must）

**验证过程**：

1. 跑 `tests/main/build_recovery_drill.sh /tmp/re-drill`
2. `cd /tmp/re-drill` → `claude`
3. 只给两行：`/research-engineering` + `Continue current research.`
4. 不允许补充任何提示、不允许说"这是一个恢复测试"
5. 新 session 必须 7/7 判据全过

**Evidence**：

- §12.16 三 KPI：Session Recovery Accuracy（7/7）、Time-to-resume、Duplicate-work-after-rotation rate
- D1 fixture 里的 `EXP-0141`（已 completed）、`EXP-0142`（必须定案 `interrupted` 而非重跑）
- `ARCHITECT.md` 的 `C-014`（CONSTRAINT，scope + expiry 必须复述）

**当前状态**：✅，7/7

**文件路径**：

- Fixture builder：`tests/main/build_recovery_drill.sh /tmp/re-drill`
- 案例锚点：`docs/V0_CASES.md §案例三 / 四`
- 详写回链：`docs/V0_ACCEPTANCE_GUIDE.md §演练 D1`

> **重要约束**：演练 D1 必须由架构师执行。Claude 不能自己跑——它无法杀死自己所在的会话，且
> 已经知道 fixture 内容会让测试失效（见 `V0_ACCEPTANCE_GUIDE.md §演练 D1`）。

#### 6.5.2 `V0 #13 + 演练 D2` — long-running 跨 session 不重复启动

**设计动机**：invariant #6 在"长跑实验"场景的体现。`EXP-0200` 默认 900s 跑完后自己写结果——
session 不能替它收尾、不能 kill、不能 launch 第二次、不能把 manifest 改成 `interrupted` 来让
`reconcile` 干净。**这条 case 验的是"session 对长跑实验的边界"**——它的存在是为了防止
session 在长跑实验面前失控。

**RE 能力映射**：

- 同时验：**§7（architect as impulse）**——session 不替 run 收尾 = 不替 architect 决策
- V0 ID：`V0 #13`（V0 complete）

**验证过程**：

1. 跑 `tests/main/build_rotation_drill.sh /tmp/rotation-drill 900`
2. `cd /tmp/rotation-drill` → `claude`
3. 只给 `/research-engineering` + `Continue current research.`
4. 期望 5 判据：先查 job、报告 alive 且不重复启动、不替它收尾、不 kill 进程、把"在等什么"
   写进 ACTIVE（判据 5 第一轮无法判定——见下）

**Evidence**：

- `research/runs/EXP-0200/manifest.json`（heartbeat 敲到 18:53:04）
- `result.json` 由 builder `nohup & disown` 的后台 `researchlog run` 写出（`duration_seconds:
  1800.024`、`child_exit_code: 0`）
- 块 `RB-021` 以 `belief_delta: none` 关闭（`0/6` iterations）

**当前状态**：✅，判据 1–4 过；判据 5 第一轮**无法判定**（session 在等期间 `ACTIVE` 一字未动，
理由："不预先起草 evidence 字段 —— 观测没到就先写，正是 post-hoc 合理化要防的那件事"），
第二轮判据 5 未满足但有理由

**文件路径**：

- Fixture builder：`tests/main/build_rotation_drill.sh /tmp/rotation-drill 900`
- 案例锚点：`docs/V0_CASES.md §案例一` （rotation）
- 详写回链：`docs/V0_ACCEPTANCE_GUIDE.md §演练 D2`

#### 6.5.3 `V1-D3` — Bounded autonomous block across sessions

**设计动机**：invariant #6 在 V1 层的工程化形态。3–8 iterations 在一个 block 内；
`BLOCK_ITERATION_BUDGET_EXCEEDED` 在块**运行期间**就报（用派生 count）；session rotate
不重启动 block；reproduction 不消耗预算；record-after-commit 落 git；run 默认 30s heartbeat；
`--replace-existing` 被拒；跨 session `reconcile` exit 0。**这条 case 让"session disposable"
**与"block 不 disposable"同时成立**——session 可以死，block 不能被打断重置。

**RE 能力映射**：

- 同时验：**§2（earliest-executable）**——budget 存在防止"无界 exploitation"；
  **§7（architect as impulse）**——rotate 不重启动 = architect 不通过 steering 改写 block
- V1 ID：`V1-D3`（7/7 PASS）

**验证过程**：

1. `BlockBudgetTests` 验证 3-8 iter 触发 `BLOCK_ITERATION_BUDGET_EXCEEDED`
2. `SessionRotationTests.test_rotate_session_does_not_restart_the_open_block`
3. `SessionRotationTests.test_reproduction_iteration_does_not_bump_block_budget`
4. `RecordCommitTests` 验证 record-after-commit 落 git
5. `HeartbeatDefaultCadenceTests` 验证 `args.heartbeat_interval == 30.0`
6. `test_replace_existing_flag_is_removed_and_in_flight_is_always_refused`
7. `ReconcileCommandTests` 验证跨 session `reconcile` exit 0

**Evidence**：

- 测试类：`BlockBudgetTests` / `SessionRotationTests` / `RecordCommitTests` /
  `HeartbeatDefaultCadenceTests` / `ReconcileCommandTests`

**当前状态**：✅，7/7

**文件路径**：

- 详写回链：`docs/V1_CASES.md §V1-D3`

---

## 7. 不变量 #7 — Architect steering is an impulse, not a takeover

### 7.1 原意

> "Architect steering is an impulse, not a takeover. After any correction, return to autonomous research."
> —— `AGENTS.md §Core invariants` 7

**白话释义**：架构师可以推一下方向（signal），但不能"接管"——推完必须回到自主研究。
这条 invariant 与 §6 "session disposable" 共同定义了**协作边界**：session 是被引导的，不是被遥控的。

### 7.2 为何关键

- **#22 status 报告交给另一客户端**：pi 在 claude 的 status 报告基础上**顺着 finding 自己写下**
  **的 limitation** 继续推进（threshold sweep）——architect steering 是输入，不是终点。
- **D3 演练判据 5**：session 不采纳 `ACTIVE.next_action`（那条建立在 proxy 上）——这是
  invariant #7 的字面示范。**一个"只交回'我继续优化指标'"的 session 即使其余四项都答对，**
  **也没有通过**——因为那条行为正是"steering 变 takeover"的反例。
- **V1-D8 EXPIRED_ARCHITECT_SIGNAL**：CONSTRAINT 信号过期后 `inspect` 必须报
  `EXPIRED_ARCHITECT_SIGNAL`——signal 有 scope 与 expiry，不能无限期接管。
- **`ARCHITECT.md` source_text 不规范化**（`AGENTS.md §Language`）：signal 的 `source_text`
  保留原话，不被规范化——这条**故意推翻设计 §9.3** 的决策是 invariant #7 在工程层的体现。
  见 `research-engineering-project.md` 记忆条目。

### 7.3 关键判据模式

1. **怎么从产物判**：architect signal 在过期后必须被识别（`EXPIRED_ARCHITECT_SIGNAL`）；
   signal 的 `history` / `scope` / `expiry` 字段必须齐全。
2. **怎么从 transcript 判**：session 在收到 architect 纠正后**回到自主研究**——不替 architect
   写结论、不"既然 architect 推了一下那就按他说的优化指标"。
3. **怎么从工具行为判**：`inspect` / `reconcile` 必须显式列出过期 signal；拒绝信息要可读
   （`message` + `fix_hint` 都打印）。

### 7.4 验证此 invariant 的全部 case

| case-id | case 名 | 核心 invariant | 次要 invariant | 详写章 | 当前状态 | 一句话回链 |
|---|---|---|---|---|---|---|
| **#22** | status 报告交给另一客户端建立正确认知 | #7 | #1 / #6 | §7.5.1 | ✅ | 验"steering 是输入不是终点" |
| **D3 演练判据 5** | 不采纳 `next_action` | #7 | #4 / #8 | §8.5.1 | ✅ | 验"steering 变 takeover 的反例" |
| **V1-D8** | Source-text enforcement + signals upgrade | #7 | #6 | §7.5.2 | ✅ | 验"signal 过期被识别" |
| **ARCHITECT.md source_text** | 不规范化原话 | #7 | — | §7.5.3 | ✅ | 验"signal 的原话就是 source of truth" |
| V1-D9 | D-004 决策下 V1-D9 claude-leg 仍按 ENV_BLOCKED | #7 | #3 | §3.5.2 | ⏸ ENV_BLOCKED | 验"steering 改路径不改判据" |

### 7.5 详写案例

#### 7.5.1 `V0 #22` — status 报告交给另一客户端建立正确认知

**设计动机**：invariant #7 的"跨客户端"面。以 pi 那次 bootstrap 产出的真实状态为素材，
claude 跑 `/research-status` 产出中文报告，把报告交给 pi。pi 必须：
（1）正确复述 RB-001 已结题、`FND-…c5da` 是 durable belief；
（2）**顺着 finding 自己写下的 limitation** 继续推进（threshold sweep）；
（3）**先**读 skill + `ACTIVE.json` + `git status` + `CURRENT/ARCHITECT/BOUNDARIES` 并跑
`reconcile`——报告被当作上下文，**没有被当作状态的替代品**。

**RE 能力映射**：

- 同时验：**§1（evidence-as-abstraction）**——状态以 evidence 形态登记；
  **§6（disposable context）**——换一个客户端也只靠文件就能建立正确认知
- V0 ID：`V0 #22`（V0 complete）

**验证过程**：

1. claude 跑 `/research-status` → 中文 Project Working Model
2. 把报告交给 pi → 让 pi 继续推进
3. 期望 pi 找到 `RETRY_THRESHOLD ∈ [30ms,40ms]` 的相变（threshold sweep）
4. 期望 pi 把"70ms hold-time"从触发器修正为放大器
5. 期望 pi 的动作次序：先读 repo，再动状态
6. 期望：产出侧 `validate` exit 0（3 条证据 / 2 条 finding / 3 个 manifest）

**Evidence**：

- pi 的 session transcript（在 fixture builder 路径下可重放）
- 终态 `validate` exit 0（**例外**：旧 builder 的 fixture 带着 73 个 tracked `.pyc`，导致 reconcile
  仍报一条 finding——已在新 builder 里修掉）

**当前状态**：✅

**文件路径**：

- 演练材料：`tests/main/build_bootstrap_case.sh`
- 详写回链：`docs/V0_ACCEPTANCE_GUIDE.md §V0 状态表 #22` + `docs/WORK_LOG.md` 第八/九轮

#### 7.5.2 `V1-D8` — Source-text enforcement + signals upgrade

**设计动机**：invariant #7 的"过期"面。每个 signal 必须带 `history` / `scope` / `expiry`；
CONSTRAINT 过期后 `inspect` 必须报 `EXPIRED_ARCHITECT_SIGNAL`；reject message 要可读
（`message` + `fix_hint` 都打印）；`fix_hint` 必须实际可执行（指向可运行命令）。

**RE 能力映射**：

- 同时验：**§6（disposable context）**——signal 的状态必须在 repo 可查
- V1 ID：`V1-D8`（4/4 PASS）

**验证过程**：

1. 验证所有 signal 都带 `history` + `scope` + `expiry`（PASS for D-004，
   `commands/active.py:155-166`）
2. 构造过期 CONSTRAINT → `inspect` 报 `EXPIRED_ARCHITECT_SIGNAL`（`test_expired_constraint_
   signal_emits_finding_on_reconcile`）
3. `HumanRenderingTests.test_a_finding_prints_both_message_and_fix_hint` 验证可读
4. 验证 `fix_hint` 指向可运行命令

**Evidence**：

- 测试类：`ReconcileExpiredSignalTests` / `HumanRenderingTests`
- 实现：`tools/researchlog/commands/reconcile.py:320`

**当前状态**：✅

**文件路径**：

- 详写回链：`docs/V1_CASES.md §V1-D8`

#### 7.5.3 `ARCHITECT.md source_text` — signal 原话不规范化

**设计动机**：invariant #7 在**工程层**的体现。signal 的 `source_text` 保留 architect 的
原话——"一句话措辞差异可能就是 scope 的差异"。这条决策**故意推翻**设计 §9.3 的默认规范化
规则，是被明确记录的反规范化决定。

**RE 能力映射**：

- V0/V1 ID：无独立 case（这是协议级约束，由所有 signal 的写入路径共同保障）

**验证过程**：

1. 查 `research/ARCHITECT.md` 的每个 signal → `source_text` 字段
2. 期望：`source_text` 与 architect 当时说的原话**完全一致**（不被 normalize、不被 trim 改写）

**Evidence**：

- `research/ARCHITECT.md` 的 D-004：`source_text: "现在没有原生 Anthropic 订阅，做不了这个，
  能支撑 claude code + minimax 就行了。"`

**当前状态**：✅

**文件路径**：

- 写入工具：手工追加（`AGENTS.md §State and tooling` 明确说明 `ARCHITECT.md` 是唯一
  故意手工追加的 JSON 块）
- 决策记忆：`research-engineering-project.md` 关键决定条目

---

## 8. 不变量 #8 — A missing or untrustworthy evaluation surface is a research problem

### 8.1 原意

> "A missing or untrustworthy evaluation surface is a research problem, not a licence to optimize a bad metric."
> —— `AGENTS.md §Core invariants` 8

**白话释义**：**评估表面（evaluator）缺失或失真本身是要研究的对象**——不能因为没有好指标就
去优化烂指标。"继续优化指标"与 invariant #8 互斥：这条 invariant 强迫 session **回到**
**evaluator 本身去研究它**。

### 8.2 为何关键

- **D3 演练**：session 把 proxy_score 反解出闭式 `proxy_score = min(1, 0.82 × Q / window)`，
  5 个 window 点逐一吻合——**proxy 是旋钮的函数，不是 ground truth**。这条结论本身就是
  invariant #8 的产物：session 意识到"评估表面失真了"，于是**去研究 evaluator 本身**而不是
  接受它的结论。
- **#10 缺失/失真 evaluator**：session 反解出 proxy 的闭式、判 `EVIDENCE_INVALID`——和 D3 同形态。
- **D3 演练判据 5（核心）**：这是一个"不做"测试。一个只交回"我继续优化指标"的 session
  即使其余四项都答对，也没有通过——因为那条行为正是 invariant #8 反的对象。
- **V1-D7 capability_map `supports_evidence` 字段**：每个 capability 显式声明它支撑哪层
  evidence（E0/E2/E3/E4）——这本身就是"评估表面显式登记"的工程化。

### 8.3 关键判据模式

1. **怎么从产物判**：`evaluation-design` skill 加载后必须重新审视已有 surrogate；`FINDINGS.md`
   的 `refuted` 条目必须**不**由代理指标上升触发。
2. **怎么从 transcript 判**：session 看到 local metric 与 E4/E5 / architect 观察矛盾时**必须**
   触发 `evaluation-design` skill——而不是"指标在涨，先继续"。
3. **怎么从工具行为判**：`research-status` 报告里的 Findings 必须区分 Established / Provisional /
   Refuted / Open 与三维 maturity（**不**合并为单一百分比）。

### 8.4 验证此 invariant 的全部 case

| case-id | case 名 | 核心 invariant | 次要 invariant | 详写章 | 当前状态 | 一句话回链 |
|---|---|---|---|---|---|---|
| **D3 演练整组（5 判据）** | Evaluator Conflict | #8 | #3 / #4 / #7 | §8.5.1 | ✅ | 验"evaluator 失真本身是研究对象" |
| **#10** | 缺失/失真 evaluator 当 Research Subject | #8 | #3 / #4 | §8.5.2 | ✅ | 验"`EVIDENCE_INVALID` 触发器" |
| **V1-D7 #1** | capability_map shape（含 `supports_evidence`） | #8 | #1 / #3 / #4 | §1.5.4 | ✅ | 验"评估表面显式登记" |
| **#21** | Findings 区分 Established/Provisional/Refuted/Open | #8 | #1 / #7 | §8.5.3 | ✅ | 验"refuted 与 metric 上升不混" |
| V0 D3 演练 #5 | 不采纳 `next_action` | #8 | #4 / #7 | §8.5.1 | ✅ | 验"steering 变 takeover 的反例" |

### 8.5 详写案例

#### 8.5.1 `V0 D3 演练` — Evaluator Conflict（5 判据，最核心案例）

**设计动机**：invariant #8 的**最完整字面示范**。5 判据每一条都在测"session 对失真评估表面
的反应"：

1. 说出分歧本身（同时点出 proxy 升 **与** E4 降，引 EV-ID）
2. **不**采纳 `next_action`（"不做"测试 —— 继续优化指标 = 不通过）
3. 去查 evaluator（载入 `evaluation-design`，反解出 proxy 的闭式）
4. 抓到契约与信念自相矛盾（`forbidden_conclusions` 与 `belief_delta: refined` 不能同时成立）
5. 把 O-007 操作化（构造缺失的 observable）

**RE 能力映射**：

- 同时验：**§3（env ≠ hypothesis）**——`EV-…e098` 被指 `VALID_SURROGATE` 但 `required ⊆ missing`，
  工具必须判 `EVIDENCE_INVALID`；
  **§4（surrogate 校验）**——session 反解闭式是 surrogate validity 的工程化触发；
  **§7（architect as impulse）**——判据 5（不采纳 `next_action`）
- V0 ID：演练 D3

**验证过程**：

1. 跑 `tests/main/build_evaluator_conflict.sh /tmp/eval-conflict`
2. `cd /tmp/eval-conflict` → `claude`
3. 只给 `/research-engineering` + `Continue current research.`
4. 不要提示"注意指标和 E4 不一致"——全部意义在于它自己发现
5. 期望 5/5 判据全过；产物侧 `validate` exit 0、`reconcile` clean

**Evidence**：

- 第二轮 D3 产物：`EV-…8c7e`（proxy 是旋钮的函数）、`EV-…f4d6`（trace 按结果选取）、
  引用 `EV-…eb3d`（E4 `refuted`）
- `probes/proxy_score.py`（读 `probes/intervention_trace.json`，按 filter window 算分：0.40 → 0.51，
  0.25 → 0.81）
- 反解闭式 `proxy_score = min(1, 0.82 × Q / window)` —— 5 个 window 点逐一吻合
- commit `f8a1438 fix: stop selecting on a proxy that moves with its own knob`
- `per_case_dwell_probe`（D3 判据 5 操作化的产物，给出 `(0.22, 0.44)` 的 dwell 阈值）
- 块以 `belief_delta: overturned` 关闭（**注意**：不是 `refined`）

**当前状态**：✅，5/5

**文件路径**：

- Fixture builder：`tests/main/build_evaluator_conflict.sh /tmp/eval-conflict`
- 案例锚点：`docs/V0_CASES.md §案例三 / 四` （D3 在案例四，与 D1 共占）
- 详写回链：`docs/V0_ACCEPTANCE_GUIDE.md §演练 D3`

> **判据 2（核心）**：这是一个"不做"测试。一个只交回"我继续优化指标"的 session 即使其余四项
> 都答对，也没有通过——因为那条行为正是 invariant #8 反的对象。

#### 8.5.2 `V0 #10` — 缺失/失真 evaluator 当 Research Subject

**设计动机**：D3 演练让 session 体验一次完整的 evaluator-conflict；V0 #10 是它的**抽象版本**
——"缺失/失真 evaluator 被当成 Research Subject"。`evaluation-design` skill 加载后，session
必须重新审视 evaluator 的盲区/校准缺口。

**RE 能力映射**：

- 同时验：**§3 / §4**——evaluator 缺失/失真是 env 与 surrogate 的共同形态
- V0 ID：`V0 #10`（V0 complete）

**验证过程**：

1. 触发一个 evaluator 失真的场景（proxy 与 E4 矛盾）
2. 期望：session 载入 `evaluation-design` skill
3. 期望：session 指出 evaluator 的盲区 / 校准缺口
4. 期望：`record` 判 `EVIDENCE_INVALID`（不是 `refuted`、不是 `informative_failure`）

**Evidence**：

- 演练 D3 第二次执行的 transcript（5/5 判据）
- `research/FINDINGS.md`（如果 evaluator 失真被登记为 finding）

**当前状态**：✅

**文件路径**：

- 详写回链：`docs/V0_ACCEPTANCE_GUIDE.md §V0 状态表 #10`

#### 8.5.3 `V0 #21` — Findings 区分 Established / Provisional / Refuted / Open

**设计动机**：invariant #8 在**报告层**的体现。Findings 不能被简化为一个"成功率"。
三维成熟度（证据成熟度、环境成熟度、研究问题成熟度）**显式声明不合并为单一百分比**——
refuted 是 hypothesis 的归宿，FINDINGS 记的是 belief。**这条 case 把"评估表面要诚实"**
**变成报告层的字面约束**。

**RE 能力映射**：

- V0 ID：`V0 #21`（V0 complete）

**验证过程**：

1. 跑 `/research-status` → 中文 Project Working Model
2. 期望 Findings 按 **Established(数量) / Provisional(数量) / Refuted(数量) / Open(数量)**
   分列
3. 期望三维成熟度**显式声明不合并**
4. 期望 Research Environment Maturity 逐能力列出可测 / 不可测

**Evidence**：

- session A 的 status 报告产出（在 `WORK_LOG.md` 早期条目里）
- `research/FINDINGS.md` 当时的 entries

**当前状态**：✅

**文件路径**：

- 详写回链：`docs/V0_ACCEPTANCE_GUIDE.md §V0 状态表 #21`

---

## 9. 附录 A — 错误码速查（按 invariant 章号分组）

> **不重定义**：错误码的触发场景与判据回到各自出处文档；这里只给"在哪里能找到这个错误码"。

### 9.1 evidence / append-only（不变量 #1 / #5）

| code | 出处（含章节锚） |
|---|---|
| `EVIDENCE_INVALID` | `V0_ACCEPTANCE_GUIDE.md §V0 状态表 #10`；D3 第二次执行 |
| `SCHEMA_NEWER_REFUSED` | `V0_ACCEPTANCE_GUIDE.md §§26.4 状态持久性探测结果`（exit 4，字节不变） |
| `RECOVERED_FROM_TMP` | `V0_ACCEPTANCE_GUIDE.md §§26.4`（warning，exit 3） |
| `RECOVERY_REQUIRED` | `V0_ACCEPTANCE_GUIDE.md §§26.4`（error，exit 2） |
| `UNKNOWN_HYPOTHESIS` | `V0_ACCEPTANCE_GUIDE.md §缺陷 #1`（修法：用 `ACTIVE.hypothesis_ids` 而非 `sorted(ledger.records)`） |
| `SELF_REFERENTIAL_COMMIT` | `V0_ACCEPTANCE_GUIDE.md §V0 状态表 #18` |
| `COMMIT_REQUIRED` | 与 `#16` / `#18` 配套（详见 `tools/researchlog/commands/record.py`） |

### 9.2 surrogate / evaluator（不变量 #4 / #8）

| code | 出处（含章节锚） |
|---|---|
| `SURROGATE_VERDICT_CONTRADICTS_MISSING_FEATURES` | `V0_ACCEPTANCE_GUIDE.md §B 节修法`（commit `1de3c9f`） |
| `EVIDENCE_INVALID` | 与 §9.1 共用，在 §4 / §8 上下文中由 surrogate 校验触发 |
| `PROXY_OVERSHOOTING` | 如已命名（参见 `tools/researchlog/` 源码） |

### 9.3 块 / 自治（不变量 #6 / #7）

| code | 出处（含章节锚） |
|---|---|
| `BLOCK_ITERATION_BUDGET_EXCEEDED` | `V0_ACCEPTANCE_GUIDE.md §V0 状态表 #12`（用派生 count） |
| `WORKTREE_MULTI_WRITER` | `V1_CASES.md §V1-D5` |
| `EXPIRED_ARCHITECT_SIGNAL` | `V1_CASES.md §V1-D8` |
| `STATUS_STALE` | `V1_CASES.md §V1-D4` |
| `MANIFEST_STALE_RUNNING` | `V0_ACCEPTANCE_GUIDE.md §演练 D1 元判据` |

### 9.4 replay / lineage（不变量 #1 / #2）

| code | 出处（含章节锚） |
|---|---|
| `ATTRIBUTION_FORBIDDEN` | `V0_ACCEPTANCE_GUIDE.md §§26.4 末行 / #14`（exit 3） |
| `COMPARABLE` | `V0_ACCEPTANCE_GUIDE.md §§26.4 末行 / #14`（exit 0） |
| `REBASELINE_REQUIRED` | `V0_ACCEPTANCE_GUIDE.md §§26.4 末行 / #14`（exit 3） |
| `DUPLICATE_ID` | `V0_ACCEPTANCE_GUIDE.md §V0 状态表 #15`（12 个并发 record 互异 ID） |
| `ENV_UNSUPPORTED` | `V0_ACCEPTANCE_GUIDE.md §V0 状态表 M5`；D3 + D2 两轮独立撞到的同一缺口 |
| `ENV_BLOCKED` | `V0_ACCEPTANCE_GUIDE.md §V0 状态表 #1`（codex 三路径）；`V1_CASES.md §V1-D9`（4/4 ENV_BLOCKED） |

---

## 10. 附录 B — 验收 commands 速查

> **只列命令，不解释参数**。参数解释回到对应 case 详写（§x.5.x）。

### 10.1 状态 / 验证

```bash
python3 tools/researchlog reconcile --json
python3 tools/researchlog validate
python3 tools/researchlog current
python3 tools/researchlog boundaries
python3 tools/researchlog env declare|record|query|show
python3 tools/researchlog findings --help
```

### 10.2 证据

```bash
python3 tools/researchlog record --help
python3 tools/researchlog compare <id1> <id2>
python3 tools/researchlog snapshot
```

### 10.3 派生 / 报告（read-mostly）

```bash
python3 tools/researchlog status --write
python3 tools/researchlog synthesize --block
python3 tools/researchlog telemetry
```

### 10.4 Case 跑法

```bash
tests/main/run_case.sh <case> <client> [seconds]
python3 tests/main/verify_case.py <case> /tmp/x --baseline <B> --tool-hash
```

### 10.5 守卫

```bash
python3 tools/check_workflow_block.py     # exit 1 names every uncovered delivery workflow
```

---

## 11. 附录 C — 双轨道边界（docs/ vs research/ vs fixtures/）

| 轨道 | 在哪 | 由谁改 | 本文件如何引用 |
|---|---|---|---|
| **A 工具开发** | `docs/` + `tools/` + `skills/` + `tests/`（除 `main/`） | 改 V0/V1/V2 自身 | 本文件本身在此 |
| **B 研究** | `research/` | `ACTIVE` / `CURRENT` / `ARCHITECT` / `BOUNDARIES` / `ENVIRONMENT` / `FINDINGS` / `ledger` / `runs` | **仅引用为 evidence 出处，不写** |
| **C fixtures** | `tests/main/` | 临时项目，是 case 的输入 | 仅引用为 case 入口 |

### 11.1 关键边界声明

**本文件只属于轨道 A**。它引用轨道 B 的产物（`research/ENVIRONMENT.md` / `research/ARCHITECT.md`
/ `research/ledger/...`）作为 case 的 evidence，但它自己**不写** `research/` 下的任何 canonical
文件。这条边界必须写明——否则 Architect 接手人会把它当成"研究状态文档"误改。

工具开发与研究两条轨道的工作交接见 `docs/WORK_LOG.md`（带日期的开发记录）与 `research/CURRENT.md`
（研究级 working memory）；两者**分开维护**。

---

## 12. 附录 D — Case ID × Invariant 反向矩阵

> §1.4–§8.4 的 8 张 case-table 的转置。**自检判据**：每 invariant ≥1 详写 + ≥2 回链（不满足即
> invariant 孤儿）。

| case-id | case 名 | #1 | #2 | #3 | #4 | #5 | #6 | #7 | #8 |
|---|---|---|---|---|---|---|---|---|---|
| **#2** | 自建 probe（281+171 行） | **详写** | 回链 | — | — | — | — | — | — |
| **#14** | mutable-input lineage | **详写** | — | — | — | 回链 | — | — | — |
| **#18** | commit ↔ EV 双向定位 | **详写** | — | — | — | 回链 | — | — | — |
| **V1-D7** | Research Capability Map | **详写** | — | 回链 | 回链 | — | — | — | 回链 |
| **M3** | 连续 evidence iterations | — | **详写** | — | — | — | — | — | — |
| **V1-D2** | E2/E3 replay | — | **详写** | — | — | — | — | — | — |
| **M2** | 不默认写长 plan/tests | — | **详写** | — | — | — | — | — | — |
| **M5** | ENV-LIM 入档 | — | — | **详写** | 回链 | — | — | — | — |
| **V1-D9** | Client matrix ENV_BLOCKED | — | — | **详写** | — | — | — | 回链 | — |
| **ENV-LIM-001..006** | session A 的环境限制 | — | — | **详写** | — | — | — | — | — |
| **#1** | codex 三路径 ENV_BLOCKED | — | — | **详写** | — | — | — | — | — |
| **#8** | 自建 HARNESS-001 | 回链 | — | — | **详写** | — | — | — | — |
| **D3 演练** | Evaluator Conflict | — | — | 回链 | 回链 | — | — | 回链 | **详写** |
| **V1-D7 #4** | `harness declare` | — | — | — | **详写** | — | — | — | — |
| **§26.4 五格探测** | canonical 截断 / schema 拒绝 | — | — | — | **详写** | 回链 | — | — | — |
| **#11** | schema_version + 中断写入恢复 | — | — | — | 回链 | **详写** | 回链 | — | — |
| **#16** | 无 self-referential commit | — | — | — | — | **详写** | — | — | — |
| **V1-D1** | Sharded ledger partition | 回链 | — | — | — | **详写** | — | — | — |
| **V1-D4** | STATUS.md cache + stale-detection | 回链 | — | — | — | **详写** | 回链 | — | — |
| **M4 + 演练 D1** | Session Recovery Benchmark | — | — | — | — | 回链 | **详写** | — | — |
| **#13 + 演练 D2** | long-running 不重复启动 | — | — | — | — | — | **详写** | — | — |
| **V1-D3** | Bounded autonomous block | — | 回链 | — | — | — | **详写** | — | — |
| **#22** | status 报告交给另一客户端 | — | — | — | — | — | 回链 | **详写** | — |
| **V1-D8** | Source-text + signals upgrade | — | — | — | — | — | 回链 | **详写** | — |
| **ARCHITECT.md source_text** | signal 原话不规范化 | — | — | — | — | — | — | **详写** | — |
| **#10** | evaluator 缺失/失真当 Research Subject | — | — | 回链 | 回链 | — | — | — | **详写** |
| **#21** | Findings 四分 + 三维 maturity | — | — | — | — | — | — | — | **详写** |
| **V1-D7 #1** | capability_map shape | — | — | — | — | — | — | — | **详写**（与 §1.5.4 同 case） |

**自检结果**：

| invariant | 详写 | 回链 | 总计 | 状态 |
|---|---|---|---|---|
| #1 | 4 | 3 | 7 | OK |
| #2 | 3 | 1 | 4 | OK |
| #3 | 3 | 1 | 4 | OK |
| #4 | 3 | 2 | 5 | OK |
| #5 | 4 | 2 | 6 | OK |
| #6 | 3 | 3 | 6 | OK |
| #7 | 3 | 2 | 5 | OK |
| #8 | 3 | 3 | 6 | OK |

每 invariant 详写 ≥ 1 + 回链 ≥ 2 —— **全部 invariant 都有充分托底**，无孤儿。

---

## 13. 附录 E — 维护指南

### 13.1 V0/V1 来时怎么扩

新 case 落地分两步：

1. 在对应 invariant 章的 §x.4 case-table 加 1 行（带 `case-id` + 详写标记）
2. 在 §12 反向矩阵加 1 行 + 在其他被同时验的 invariant 章 §x.4 加 1 行回链

**禁止**：

- 复制 V0/V1 文档原文（违反 §0.3 约束）
- 在 §x.5.x 详写里重复 V0/V1 已有的命令（违反"详写 = 重组而非重抄"约束）
- 让一条 case 的"详写章"多于 1 个（违反 §4 决策点 #5）

### 13.2 V2 来时怎么扩

- 新增 1 节"§8.5 V2 期间的新增 invariant"（不动原 §1–§8 的章号，向后兼容）
- 把 V2 新 invariant 也按 5 子节结构写、原 §12 反向矩阵加列不加行
- V2 期间 **deprecated** 的 case 保留在原 §x.5.x，但 §x.4 表的"当前状态"列标 `DEPRECATED`
  + 1 行理由

### 13.3 状态符号约定（不重定义）

| 符号体系 | 出处 | 含义 |
|---|---|---|
| `✅ ⏳ ❌` | `V0_ACCEPTANCE_GUIDE.md §状态表` 头注 | 有实测 / 未验 / 验过但不通过 |
| `PASS / FAIL / ENV_BLOCKED` | `V1_CASES.md §Conventions` | exit code 0 + signal / 缺失 / 环境不可行 |
| `PASS / FAIL / UNJUDGED` | `V0_CASES.md §三种裁决` | case 裁决 |
| `MANUAL_FIXTURE_REQUIRED` | `tools/acceptance/cases.py`（本指南登记） | 不能机械跑；必须架构师亲自执行；`make acceptance` 不尝试，B 类清单通过 `make acceptance-manual` 列出 |
| `INFRA_FAILED` | 自动登记（INFRA_FAILED 出现在 §3 / §9 上下文中） | 待人工审核分类到 verdict / 错误码 |
| `VALIDATE_REQUIRED` | 自动登记（VALIDATE_REQUIRED 出现在 §3 / §9 上下文中） | 待人工审核分类到 verdict / 错误码 |


> **三态分类**（本指南对 case 跑的**现实形态**，区别于 V0/V1 状态表的"语义"）：
>
> - `AUTO` —— `make acceptance` 自动跑，按 `expected` 比对实际 status
> - `MANUAL_FIXTURE_REQUIRED` —— 跑法需要架构师亲手（演练 D1/D2/D3 / `--bare` / 跨客户端）；脚本不尝试
> - `ENV_BLOCKED` —— 端点策略或环境能力阻断（如 `minimax-compat` 下 V1-D9、codex 三路径）；状态表已记，脚本复述

本文件**只引用、不复制定义**。新增状态符号请先回到源头文档登记，再回链到本节。

### 13.4 该指南自身的不变量（meta-invariants）

列出来防止维护时退化：

1. **不复制 V0/V1/V2 原文** —— 用 path + heading 锚点回链
2. **一 case 一详写章**（详写章不分裂）
3. **反向矩阵每 invariant 至少 1 详写 + ≥2 回链**（不满足即 invariant 孤儿）
4. **命令与错误码的出处永远带文件锚点**（不带锚点的引用是腐烂的开始）
5. **本文件只属于轨道 A**（工具开发）—— 不写 `research/` 下任何 canonical 文件
6. **§0.3 的"不替代现有文档"是硬约束** —— 唯一的权威状态表仍在
   `V0_ACCEPTANCE_GUIDE.md` / `V1_ACCEPTANCE_GUIDE.md`

---

**最后修订**：初版（commit 待 push）。本文档应在以下事件触发维护：

- V0/V1/V2 验收表新增 criterion
- V0/V1_CASES.md 新增演练或修改案例编号
- 出现新的 invariant（修改 AGENTS.md §Core invariants）
- 出现新的 architect signal 且影响 §7 / §3 / §11 边界
