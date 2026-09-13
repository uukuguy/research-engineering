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
- `EXP-0142` 的 `stdout.log` 里有 `case-01`/`case-02` 两行输出 —— 这是 ACTIVE 声称"已完成
  两个 case"的**唯一依据**，也是判据 4 可判的前提。日志停在 case-02，正因如此 `case-03` 起
  才是 pending。这一条是第一次演练之后补的：原本 fixture 没有它，于是"已完成"没有任何东西
  支撑，而 session **正确地**不信这个声明 —— 那测的是 fixture 而不是 session；
- `ARCHITECT.md` 里**唯一**一条 live signal：`CONSTRAINT` C-014（带 `source_text`）。文件里
  还能读到 C-009 的字段，但它在普通 `json` 块里，是**形状说明而非信号** —— 骨架不再自带任何
  live signal（见文末第 3 条）；
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

## D1 第一次执行结果（2026-09-14）

架构师在 `/tmp/re-drill` 跑了一次，只给 §26.2 那两行。它以 `validate` exit 0、`reconcile`
exit 0 clean 收尾。

**这次跑的是"补 case artifact 之前"的 fixture 版本**（见上文 fixture 说明的最后一条）。所以
下面的结论只对该版本成立；判据 4 因此无法判定，要拿到干净的 7/7 需要用当前 fixture 重跑一次。

以下是**只读检查产物**能核实的事实。限制必须说清：只读检查看不到 transcript，所以判据 1/2/5
里"说出……"那一半无法由此确认 —— 它们需要 transcript。可核实的部分是：

| 判据 | 可核实的证据 | 结果 |
|---|---|---|
| 1 | 两个新 commit 落在同一 branch 的同一 repo；其中一条明确把 ACTIVE 指向 checkpoint commit | 过 |
| 2 | `git status` 仍显示 ` M probes/replay_probe.py` —— **未完成工作没有被 `git checkout --` 丢掉**；commit body 记录了该改动**跑不起来**（两个分支同样失败） | 过 |
| 3 | ACTIVE 保留 `H-037`/`H-039`，并给出新的 `experiment_id` 与 intent | 过 |
| 4 | 它读取了 case 进度并判定**无据** —— 就当时的 fixture 而言判得对，据此清空。判据本身因此无法判定 | 无法判定 |
| 5 | `ARCHITECT.md` 里 C-014 仍在；actuator 缺失被当作**环境限制**处理 | 过 |
| 6 | `EXP-0141` 的 started 时间戳与 fixture 一致、仍为 `completed` —— **没有重跑** | 过 |
| 7 | `EXP-0142` 被定案为 `interrupted`（不是删除、不是重新 launch）；`ACTIVE.next_action` 写明"缺的是输入不是算法" | 过 |

最值得记下的一条：**6 条证据记录里没有一条 `refuted`。** 它撞了三次墙（2×`infra_failed`、
1×`interrupted`），三次都记为 `informative_failure`，且每条 `belief_delta: none`，commit
body 明确写 "No belief change: H-037 and H-039 are weakened in neither direction"。环境不可行
没有被转化成科学结论 —— 这条设计第一不变量在真实压力下成立。

**这次执行暴露的 fixture 缺陷（已修）**：判据 4 无法判定，原因在 fixture 而不是 session。
fixture 让 ACTIVE 声称 `case-01,02` 已完成，但 EXP-0142 没有任何 artifact —— 于是这个声明
没有东西支撑，session **正确地**不信它，并据此清空了两组 case（commit body: "the ACTIVE
capsule claiming progress that no artifact supported"）。

session 的行为是对的；错的是 fixture 自相矛盾。已修：EXP-0142 现在带着一份写到 case-02
为止的 `stdout.log`，使"已完成两个 case"有 artifact 可依、且 pending 的起点有据可查。
判据 4 要在**当前** fixture 上重跑才算数。

## 准备 fixture 时在正常路径上撞到的三个缺陷（全部已修）

验收清单的价值在于真去跑它。这三个都不是边界情况 —— 它们在任何一次"记录一条证据"的
普通研究里都会遇到。

**1. `UNKNOWN_HYPOTHESIS` 100% 误报。** `validate` 把 `sorted(ledger.records)`（**EV id
空间**）当作 `known_hypotheses` 传入，而 `H-*` 永远不等于 `EV-*`。于是任何记录了 hypothesis
的证据都会报"引用了不存在的假说"。判据本身没错，是它的注册表接错了 ID 空间。改用
`ACTIVE.hypothesis_ids`（V0 唯一的假说注册表）。

**2. `completed_evidence_iterations` 没有任何写入路径，且块预算根本没实现。** 这比"没人写
这个字段"更严重：`max_evidence_iterations` **没有任何代码消费者**，所以 V0 验收 #12（Block
Contract 阻止无界重复）其实并不成立 —— 字段存在只是为了让另一个检查拿它自比。

根因是生命周期搞错了。`belief_delta` 的规则是"开块期间为 null，关闭时写一次"，而 count 被
当成活计数器：开块期间拿一个永远为 0 的值去比对，于是每个记过改变信念的证据的项目都拿到一个
**无法消除**的 error，而 finding 的修法提示又写着"不要手写这个字段"。

修法让两者同生命周期：

- count **只在块关闭时**由 `active --close-block` 从 ledger 派生并写入（与 `belief_delta`
  同一次写入）。没有活计数器，因为没有东西会让它保持诚实；
- 开块期间**不做**漂移比较（无可比之物）；
- 新增 `BLOCK_ITERATION_BUDGET_EXCEEDED`：用**派生**的 count 与 `max_evidence_iterations`
  比较，**在块运行期间**就报 —— 那才是 grinding 发生的时候。这补上了 #12 缺的那一半。

顺带修掉同族的第二处：块成员判定只读 `hypothesis_ids`，于是只填
`hypotheses_differentiated` 的记录会被漏掉，**块会少算自己的预算**。现在两者取并集，且与
`_check_hypotheses` 共用同一个 `identified_hypotheses`，使"成员"与"引用"不可能再分叉。

**3. 骨架自带一条"没人下过的约束"。** `templates/research/ARCHITECT.md` 的示例 signal
C-009 是一个**真实的块**，不是注释。于是从模板建立的每个项目一开头就有一条 `CONSTRAINT`，
而且它**完全合规** —— 所以没有任何检查能看见它。工具区分不了示例与实况，因为它们本来就是
同一种东西。

修法：示例改放进普通 `json` 块，并在正文里点明**围栏就是形状与状态的全部差别**。骨架因此
自带 0 条 live signal。回归测试只能断言结构（文本里不得出现 ```` ```json research:signal ````），
因为一个合规的幽灵对检查层是隐形的。

