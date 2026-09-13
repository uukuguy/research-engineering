# V0 验收清单：Day-1 must 与 V0 complete

本文件把设计文档 §20.1 的"第一天验收"22 条拆成两组。原文的问题不是条目写错了，而是
**22 条不可能在一天内验证** —— 其中多数需要长时自治运行、第二个客户端、或故障注入
才能测。混在一张清单里的结果是：第一天结束时无法回答"V0 到底能不能用"，因为清单上
永远还剩没测的条目。

上位规范是设计文档 **§26 原生客户端可执行性验收（Normative）**。本文件的演练 D1
直接取自 **§12.16 Session Recovery Benchmark** 与 **§26.2**。

> 出处：设计文档 §20.1（22 条原文）、§12.16（失忆测试与三个 KPI）、§26.1–26.4（原生
> 可执行性与故障注入）。本文件只做拆分与操作化，不改写验收内容。

## 拆分判据

一条验收进入 **Day-1 must**，当且仅当：**它不成立时，"这个项目已经开始做研究了"这句话
就不成立** —— 即它不属于"跑得更好"，而属于"能跑"。其余全部进入 V0 complete。

这个判据是本文件唯一的主观部分，写出来是为了让它可复核、可推翻：如果你认为某条该换
组，换组的理由应当是"它其实是能跑/跑得更好之别"，而不是"它比较容易测"。

## Day-1 must（5 条，覆盖原文 6 条）

这 5 条就是 V0 的目标（§20.1 开篇："证明 AI 能把架构师的高层观察/方向自主转化成
executable evidence"）本身，加上三条使它诚实的前提。

| # | 验收 | 原文条目 | 怎么测 | 通过判据 |
|---|---|---|---|---|
| M1 | 全新 repo 能建立最小 canonical state，且不写重型 plan | #9 | 空目录里跑 `research-bootstrap` | canonical 文件齐备；`reconcile` 干净；产出的 plan 类文档为 0 |
| M2 | 不默认写长 plan 和大量 tests | #3 | 观察一次常规 iteration 的产物 | 没有新 plan 文档、没有新测试套件；改动集中在 probe/instrumentation |
| M3 | 能连续做 2–3 个 evidence-producing iterations | #4 | 交一个高层方向，不指定算法 | 3 次迭代各自产出 `EV-*`；至少一条 `counts_as_evidence_iteration: true` |
| M4 | session 被杀后，只靠文件恢复 active research | #6 + #17 | **演练 D1** | D1 的 7 项判据全过 |
| M5 | 不可行的实验被判为 environment limitation，而非 scientific failure | #7 | 交一个本机做不到的实验 | `execution_status: env_unsupported`（或同类）；`research_outcome` **不是** `refuted`；该限制进入 `ENVIRONMENT.md` |

M4 合并了原文 #6 与 #17 —— 两条说的是同一件事（重启后只依赖 repo state 恢复），#17 只是
把 #6 写得更具体。这里明写出来，是为了让"22 条变 21 条"有账可查，而不是悄悄少一条。

## V0 complete（16 条）

| 原文 | 验收 | 为什么不是 Day-1 |
|---|---|---|
| #1 | Codex 与 Claude Code 都能进入 Research Mode | 需要第二个客户端在场 |
| #2 | 没有 runnable system 也会自主做 probe | M1+M3 通过后自然覆盖，单列只为回归 |
| #5 | 架构师不指定具体算法 | 观察项，随 M3 一起看即可 |
| #8 | 能自行构造至少一种合法 surrogate / harness | 需要先遇到"目标层级测不到"的场景 |
| #10 | 缺失/失真的 evaluator 被当成 Research Subject | 需要先有 evaluator |
| #11 | canonical JSON 带 `schema_version` 且中断写入后安全恢复 | 故障注入，见 §26.4 |
| #12 | Research Block Contract 阻止无界重复 exploitation | 需要长时自治块 |
| #13 | long-running experiment 跨 session 不被重复启动 | 需要跨 session 的长任务 |
| #14 | model/data/prompt/config 在 comparison 中具有 stable identity | 需要可比较的两次 run |
| #15 | 并行 writer 使用 collision-resistant IDs | 需要并发写入场景 |
| #16 | Git/Evidence transaction 无 self-referential commit hash | 已由 CLI 层验证，待端到端复验 |
| #18 | Git commit/diff 与 Evidence 能双向定位 | 证据量足够后才可测 |
| #19 | 不依赖 hooks/subagents/MCP/GitHub 也能完成完整 V0 loop | Normative（§26.1/26.2），靠**移除**适配器验证 |
| #20 | `research-status` 能只读生成全局中文 Project Working Model | 需要先有值得汇报的状态 |
| #21 | 状态汇报正确区分 Established / Provisional / Refuted / Open 与三维 maturity | 同上，且需要已归档的 `FINDINGS` |
| #22 | status 报告交给另一客户端可快速建立正确认知，执行前仍走 Resume | 依赖 #1 与 #20 |

---

## 演练 D1：Session Recovery Benchmark

阻塞性，属 **M4**。规范出处 §12.16 与 §26.2。

fixture 已脚本化，可复现：

```bash
tests/main/build_recovery_drill.sh /tmp/re-drill
```

脚本成功时会自己断言：`reconcile` **恰好**只报 `MANIFEST_STALE_RUNNING`，`validate` 干净。
如果断言不成立，脚本会失败并说明"改 fixture，不要改判据" —— 一个跑在意料之外状态上的
演练，产出的结论没人能归因。

fixture 里有什么（每一项对应 §12.16 的一条判据）：

- `ACTIVE.json` 处于 `running` 中途：`RB-014` / `EXP-0142` / `H-037`，`case-01,02` 已完成，
  `case-03,04,05` 未做，`next_action` 已写；
- `EXP-0141` 已完成并留下 `EV-*`（E2 对标 E4，带 surrogate contract）；
- 一条 `env_unsupported` 记录：本机没有 actuator，问题在这里**测不了**；
- `EXP-0142` 的 manifest 仍是 `running`，无 `result.json`，heartbeat 回写了 150 分钟
  （脚本里唯一一处刻意改动 —— "一个 150 分钟前的尸体"是 fixture 造不出来的，时间不能伪造）；
- `ARCHITECT.md` 里一条真实的 `CONSTRAINT` signal（C-014，带 `source_text`）。注意文件里
  **还有第二条** `CONSTRAINT`（C-009），那是模板骨架自带的示例 —— 见文末"演练已经发现的
  问题"第 3 条。判据 5 只要求保住 C-014；顺带提到 C-009 不算错，但把 C-009 当成真实约束
  来遵守，说明恢复是对的、模型判断不了示例与实况的区别；
- 一处**未提交**的 `probes/replay_probe.py` 改动，其意图只能靠 manifest 的 `--command`
  与 `ACTIVE.intent` 交叉推断 —— 脚本刻意没有留下任何解释性注释，否则测的就不是推断能力。

### 执行

必须由架构师执行。Claude 不能自己跑这一次演练，原因有两个，且都是硬性的：它无法杀死
自己所在的会话；而且它已经知道 fixture 的内容，那会让测试失效。

```bash
cd /tmp/re-drill
claude                     # 或 codex，用于 #1
```

只给这两行，**不要补充任何提示、不要先说"这是一个恢复测试"**：

```
/research-engineering
Continue current research.
```

（中文等价：`/research-engineering` + `继续研究`。§26.2 给的就是这两行。）

**关键约束**：不要在同一个 session 里先做一遍研究再重启 —— 那会注入聊天历史，而"没有旧
聊天"正是这个测试的全部意义。

### 判据

| # | §12.16 判据 | 通过 | 失败的样子 |
|---|---|---|---|
| 1 | 找到正确的 branch / worktree / HEAD | 说出 HEAD 的 subject（`drill: state as the session that died left it`）与当前分支 | 没看 git 就动手；在别处找 worktree |
| 2 | 理解 dirty diff 的意图 | 说这是死掉的 session 正在给 probe 加 `--closed-loop`，且与 EXP-0142 的命令对得上 | 一句 `git checkout --` 把它丢了（把未完成工作当垃圾）；或只字不提 |
| 3 | 知道当前 hypothesis / experiment | 说出 `H-037` / `EXP-0142` | "没有进行中的研究" |
| 4 | 知道 completed / pending cases | 说出 `case-01,02` 已完成、`case-03` 起未做 | 报不出 case 编号；或声称全部完成 |
| 5 | 保留 architect signal 与 environment limitation | 复述 C-014 的 scope/expiry；把 actuator 缺失当成**环境限制** | 丢掉 C-014；或把 `env_unsupported` 说成"机制不成立" |
| 6 | 避免重复已完成的实验 | 不重跑 `EXP-0141` | 重跑 EXP-0141 来"确认一下" |
| 7 | 选择正确的 next action | 先确认 EXP-0142 的存活性（`job`），再决定 resume / finalize / rerun，并落到 `case-03` | 无视 `MANIFEST_STALE_RUNNING` 直接新开实验；未确认存活就重新 launch EXP-0142 |

一条贯穿全部 7 项的元判据：**`reconcile` 从不修复，session 也不能。** 它应当报告
`MANIFEST_STALE_RUNNING` 并基于证据决定动作，而不是静默把 manifest 改成 `interrupted`
好让 `reconcile` 变干净。

### 记录什么

- 新 session 的完整 transcript（至少前 10 步）；
- 它按顺序读了哪些文件；
- 它是否重跑了 EXP-0141、是否重新 launch 了 EXP-0142；
- 它如何处置 `MANIFEST_STALE_RUNNING`；
- §12.16 的三个 KPI：**Session Recovery Accuracy**（7 项判据的通过数/7）、
  **Time-to-resume**（从 prompt 到第一次正确的 evidence 动作的墙钟时间）、
  **Duplicate-work-after-rotation rate**（重复启动的已完成实验数）。

判据 7 的"正确"允许两种：先确认存活后发现进程已死、于是 finalize 成 `interrupted` 再决定
重跑；或发现进程仍在、于是 attach 观察。两者都通过 —— 判的是**它先确认再决定**，不是它
选了哪个分支。

---

## 演练已经发现的问题

验收清单的价值在于真去跑它。准备 D1 的 fixture 时，在**正常路径**上撞到两个缺陷：

**1. `UNKNOWN_HYPOTHESIS` 100% 误报（已修，见 `validate.py`）。** `validate` 把
`sorted(ledger.records)`（EV id 空间）当作 `known_hypotheses` 传入，而 `H-*` 永远不等于
`EV-*`。于是任何记录了 hypothesis 的证据都会报"引用了不存在的假说"。判据本身没错，是它
的注册表接错了 ID 空间。修法是改用 `ACTIVE.hypothesis_ids`（V0 唯一的假说注册表）。

**2. `completed_evidence_iterations` 没有任何写入路径（未修，待决策）。** 该字段被
`check_block_contract` 校验、文档明令"derived，不得手写"，但**没有任何命令会写它** ——
`active --close-block` 只写 `belief_delta`。复现：

```bash
# 任意 repo：init → record 一条改变信念的证据 → validate
researchlog record ... --belief-delta refined ...
researchlog validate      # EVIDENCE_ITERATION_COUNT_DRIFT，subject 为 block id
researchlog active --close-block --belief-delta refined
researchlog validate      # 依旧 DRIFT：count 仍是 0
```

任何记了改变信念的证据的项目都会拿到一个**无法消除**的 error，唯一出路是手改一个文档禁止
手改的字段。这直接冲击 V0 complete 的 #11/#12。本文件的 D1 fixture 因此只用
"不计入迭代"的记录（`inconclusive` + `belief_delta: none`），让演练的失败可归因到
skill 层而不是这个已知缺陷。

修法待定，因为它是设计层选择而非实现细节：让工具在写 `ACTIVE` 时按 ledger 重算该字段
（即兑现"工具会重算"的既有说法），还是让块契约只在**关闭时**校验。

**3. 骨架自带一条"没人下过的约束"（未修，待决策）。** `templates/research/ARCHITECT.md`
里的示例 signal C-009 是一个**真实的块**，不是注释。所以从模板建立的每个新项目，`ARCHITECT.md`
一开头就有一条 scope 为 `recovery research`、expiry 为 `recovery checkpoint` 的 `CONSTRAINT`
—— 没有任何架构师下过它。`validate`/`reconcile` 把它当实况处理（`check_signal` 会检查它的
`source_text`，而 `expiry` 一旦写成 ISO 就会被 `EXPIRED_ARCHITECT_SIGNAL` 强制执行）。示例
与实况在机器看来没有区别，因为**它们本来就是同一种东西**。

修法要么让示例不可执行（例如放进普通代码块而非 `research:signal` 块），要么让 `init` 在
建立新项目时剥掉它。前者更符合"骨架教形状"的用途。
