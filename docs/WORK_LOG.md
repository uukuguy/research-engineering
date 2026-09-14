# Work Log

本仓库的**开发记录**。新会话从这里接续：读最新一条即可知道"做到哪、下一步做什么、动手前要注意什么"。

条目**带日期且只追加** —— 一条过期的条目看起来就是旧的，不会伪装成现状。这正是它不需要被重新
生成或校验的原因（而"当前状态快照"需要）。

> 两条轨道别混：`research/*` 是**这个工具所服务的研究**的状态（由 `researchlog` 持续维护）；
> 本文件是**开发这个工具**的记录。本仓库的 `research/ACTIVE.json` 保持 `idle` 是正常状态，
> 不是待填的空缺。

---

## 2026-09-14 — 评审收官、V0 验收操作化、三个演练

### 会话概览

关闭 V1.5 评审的**全部 19 项**（P0-1..5 / M-1 / P1-1..12 / D-1）；把设计文档 §20.1 的 22 条验收
拆成 **Day-1 must（5）/ V0 complete（16）** 并操作化到可执行；§26.4 的六个故障注入在 CLI 层
实测；三个 session 级演练（D1 恢复 / D2 rotation / D3 evaluator conflict）脚本化、跑过、结果入档。
**17 个 commit**，工作树干净。

这一轮最有价值的产出不是那些修复，而是**那条缺陷模式**：绝大多数缺陷是"声明了但没人接线"
（`git_recover` 参数没人传、`max_evidence_iterations` 没有消费者、`completed_evidence_iterations`
没有写入者、示例 signal 是合规的真块），而测试之所以放过它们，是因为**测试注入了被测字段本身**。

### 技术变更

**`tools/researchlog/`**

- `constraints.py` —— Architect Signal 的字段契约（八类、`source_text` 对
  CONSTRAINT/DECISION/VETO 强制、`scope`/`expiry` 对 CONSTRAINT 强制）；块成员改由 `block_id`
  认定；`BLOCK_ITERATION_BUDGET_EXCEEDED`（用**派生** count 在块**运行期间**报）；
  `count_evidence_iterations`、`identified_hypotheses`
- `commands/validate.py` —— 假说注册表改用 `ACTIVE.hypothesis_ids`（原先把 EV id 空间当注册表，
  100% 误报）；四种 kind 都做 schema 校验（原先从不校验 manifest）；报告非当前 schema 版本
- `commands/reconcile.py` —— 把 ACTIVE 的加载结果加入报告（原先对不可读的 ACTIVE 报
  `clean: true`）；signal 完整性；抽出 `_signal_blocks`
- `commands/record.py` —— 从 ACTIVE 落印 `block_id`
- `commands/active.py` —— 关块时派生并写入 count；开新块重置块摘要
- `state.py` —— 接上 Git 恢复回退（`git_recover` 此前从未被传入）；`Ledger.findings_block`
- `jgit.py` —— code identity 排除 `research/`（原先每写一条证据就改变一次身份，导致
  `compare` 的 `COMPARABLE` 不可达）
- `schema/registry.py`、`schema/__init__.py` —— 新增 `version_findings`
- `schemas/evidence.schema.json` —— 新增 `block_id`

**skills** —— `SKILL.md`（块归属语义、预算在运行期生效）；`references/architect-signals.md`
（signal 契约、echo-back、**选项框的文案不是架构师的原话**）；`references/session-continuity.md`
（块归属、schema 兼容表）；`references/evaluation-design.md`（E2/E3 的隔离：frozen replay +
hash + dev/holdout 只读）；`research-status/SKILL.md`（末尾英文 key 的 YAML snapshot basis、
不一致时给出下一步）

**状态与模板** —— `templates/research/ARCHITECT.md` 与 `research/ARCHITECT.md`：示例不再放在
`research:signal` 围栏里（**围栏就是形状与状态的全部差别**，骨架现在自带 0 条 live signal）

**演练工具** —— `tests/main/build_recovery_drill.sh`、`build_rotation_drill.sh`、
`build_evaluator_conflict.sh`。三者都会**自断言自己要测的状态确实存在**，失败时报
"改 fixture，不要改判据"

**文档** —— `docs/V0_ACCEPTANCE_GUIDE.md`（新增）：拆分判据、两张表、三个演练的判据与结果、
§26.4 实测表、每个缺陷的修法

### 测试结果

- `researchlog` 的四个模块（`test_constraints` / `test_integration` / `test_commands` /
  `test_schema`）**152 项全绿**
- `validate` exit 0 / `reconcile` exit 0 clean（在仓库根跑）
- `install_research_skills.py --self --check` —— 两个 client 无漂移
- **每个修复都做了变异验证**（把修复改回去，测试确实失败），结果写在各自 commit message 里
- 三个演练的自校验：D1 → `reconcile` 恰好只报 `MANIFEST_STALE_RUNNING` 且 `validate` 干净；
  D2 → `job` 报 alive + 双清；D3 → proxy 在 window 0.40 报 0.51、0.25 报 0.81，两条记录
  `diff_sha256` 相同，`compare` 判 **COMPARABLE**

### 开放项

- **⚠️ 本轮未推送。** 本会话无网络（`git fetch` 报 `Error in the HTTP2 framing layer`），且这个
  工作副本没有 upstream、没有 remote-tracking ref、reflog 里 0 条 push —— **远端状态未知**。
  17 个 commit 只在本地。有网络时：`git push -u origin main`
- **D2 / D3 的结论对应修 fixture 之前**的版本，需在新 fixture 上重跑；D2 还会顺带验证
  **收紧后的判据 5**（要求把"在等什么"写进 `ACTIVE`）
- D1 的判据 1 与判据 5、以及所有"说出……"类判据，**只能从 transcript 判**；目前只核实了产物能
  证明的那一半
- V0 complete 里需要**第二个客户端**（#1、#22）、**长时自治块**（#12 的完整形态）、
  **并发写入**（#15）的项尚未做过。#11 与 #14 已由 §26.4 探测覆盖
- `research/ACTIVE.json` 的 `git.base_commit` 仍是 bootstrap 的 `403383d`（没有块开过，从未更新；
  `reconcile` 不检查它，无功能影响 —— 但别据此以为状态落后）
- `docs/V0_ACCEPTANCE_GUIDE.md` 的位置：它是**题材范围**的参考材料（V0 验收），按全局约定 §4
  属于"核心文档"（`docs/design/`）。留在 `docs/` 根还是挪过去，待定

### 下一步

1. `git push -u origin main`
2. 在**修好的** fixture 上重跑 D2 与 D3 —— 命令与判据表见 `docs/V0_ACCEPTANCE_GUIDE.md`
   的 D2 / D3 两节。收尾：`kill $(jq -r .execution.pid_or_job_id research/runs/EXP-0200/manifest.json)`
3. 若架构师保留了 transcript，回填需要 transcript 的判据；没有就标"未判定"，不要猜
4. V0 complete 的剩余项（第二个客户端 / 长时自治块 / 并发写入）

### 动手前必须知道

1. **`researchlog` 按 cwd 向上找 `research/`，不看脚本路径。** 检查一个副本（例如演练 repo 里的
   `tools/researchlog`）时必须先 `cd` 进去，否则它会去检查你**当前所在**的仓库 —— 而且很可能报
   clean，于是你得到一个关于错误对象的"通过"。踩过，误读了一次演练结果。
2. **跑全量测试前必须先问架构师**，哪怕改动落在共享底座上。先跑覆盖改动模块的定向测试并报告。
3. **造演练 fixture 的两条铁律**：每条主张都要有 artifact 支撑；每个异常都必须是刻意埋的
   （工作区文件在捕获身份**之前**就位、探测桩只打印不写工作区、可调参数走**声明的 input** 而不是
   工作区文件）。并且让 fixture **自断言**这两条 —— 否则会悄悄腐烂。

---

## 2026-09-14（第二轮）— 推送、无头重跑 D2/D3、不变量 #4 接线

### 会话概览

先把上一轮**未推送**的 17 个 commit 推上 `origin/main`（远端此前确实空，`ls-remote` 无任何分支）。
然后在**修好的** fixture 上重跑 D2 与 D3 —— 这次由 Claude 用无头方式驱动，因此 transcript
第一次可读，判据里"说出……"那一半第一次可判。

**D3 5/5。D2 4/5** —— 不过的那条恰是上一轮被收紧过的**判据 5**，而且失败方式很有信息量（见下）。
D2 的 session 另外交出了本轮最有价值的产出：**它拒绝把 `41/60` 当结果**（拒绝理由是硬编码字面量，
判 `EVIDENCE_INVALID` + 如实计为零进展），并独立报了 fixture 的两处 state 层缺陷。

### 技术变更（5 个 commit，均已推送）

- **`101dc46`** —— 三个 drill builder 之前只复制 `AGENTS.md`，**没复制 `.claude/settings.json`**，
  而 AGENTS.md 写着那个 workflow 屏蔽是 mechanical、"the deny list ... is the load-bearing part"。
  builder 现在带上该文件并自断言。**第一版断言是死的**（写的是"fixture 与源仓库一致"，而 fixture
  就是源的字节副本 —— 恒真、永不失败），变异验证抓到后才改成对内容的断言。
- **`1de3c9f`** —— **不变量 #4 接线**。`_check_surrogate` 从不比较 `required_causal_features` 与
  `missing_or_distorted_features`，所以"必需因果特征全缺 + `VALID_SURROGATE` + `promising`"能一路
  通过。新增 `SURROGATE_VERDICT_CONTRADICTS_MISSING_FEATURES`。**是 D3 的 session 自己发现并上报的。**
- **`3325935` / `b11e08c`** —— 参考文档补上"这条规则由谁执行"，并把 docstring 从下绝对断言
  （"绝不会冤枉"）改成只陈述机制。
- **`32d1b33`** —— recovery fixture 的契约把**宽主张**当成了 `target_causal_claim`，同时把它要求的
  `actuator dynamics` 列为 missing 却宣告 `VALID_SURROGATE`。查设计文档 §6.5.3 才敢动。

### 演练判据

**D3 —— 5/5。** 详见 `docs/V0_ACCEPTANCE_GUIDE.md`（含每条判据的可核实证据）。两条超出判据的
表现：它**反向发现 E4 证据是单臂的**（没有收窄前的对照臂，所以那条 `refuted` 其实不足以区分
reduced/preserved/caused），并把要那一臂作为**架构师范围内的请求**提出；它**没有回改历史记录**，
而是写新证据。

**D2 —— 4/5。** 判据 1–4 过（无第二次 launch、没替它收尾、没杀进程、状态干净）。
**判据 5 未满足**：等待期间 `ACTIVE` 一字未动。但它**不是疏忽，是拒绝预写** —— 理由是"观测没到就
先写，正是 post-hoc 合理化要防的那件事"。这个理由对**结论**成立，而判据要的是**意图**；意图不是
post-hoc 合理化，恰恰相反，**未写下的意图事后无法与编造区分**。判据的修法是协议设计问题（接受
manifest heartbeat 作为 attach 证据，或在 `session-continuity.md` 里写明"等待期写意图、不写结论"），
**不是 session 的错**。

### 这一轮暴露的 fixture 缺陷（都还没修）

1. **缺 workflow 块**（A）—— 已修。
2. **D3 的污染记录现在造不出来了** —— 已改成"先写诚实契约、事后补丁"，并自断言补丁生效。
3. **D1 的契约写错了 target claim** —— 已修。
4. **D2 的 canonical state 是三个互不相关的示例拼的**（D 节）：`research_question` 是本轮新造、
   `H-037/H-039` 来自 `experiment-review.md` / `diagnosis.md`、`case-31/37/42` 来自
   `evaluation-design.md`，而五份 canonical 文件全是空骨架。后果是 session **无路可走** ——
   它无法从 state 设计实验，而"Do not invent missing prior state"又不许它补。**未修。**
5. **fixture 里 `AGENTS.md` 指向不存在的路径**（E 节）：`docs/WORK_LOG.md`（AGENTS.md 写的是
   "**Start here**"）、`skills/`、`tools/install_research_skills.py` 全不存在。根因与 A 同族 ——
   `CLAUDE.md` 是本仓库的适配说明，整份复制进 fixture 等于让它声称一个没有的布局。**未修。**

### 工具缺口（两轮独立发现，据此确认）

**`researchlog env record` 写不了 `ENVIRONMENT.md` 的三张表。** D3 与 D2 **独立**报出同一处：
没有 `limitations` / `capability_map` / `available` 的写入路径，`tools/researchlog/schemas/` 下
根本没有 `environment.schema.json`。两者都没有绕过、没有手改 canonical JSON，而是把缺口报上来。

### 开放项

- **V0 远未完成。** 有实测证据的约 6 条（M4 / #10 / #11 / #13 / #14 / #12 的一半）；明确没做过的是
  #1、#22（需第二个客户端）、#12 完整形态（需长时自治块）、#15（需并发写入）、#16 端到端复验、
  #18、#19（需移除适配器）、#20、#21。**且指南里那张 V0 complete 表是"为什么不算 Day-1"，不是
  状态表** —— `#2/#5/#8/#20/#21` 与 `M1/M2/M3` 在指南里找不到"是否验过"的记录：可能验过没落档，
  也可能没验。要答"V0 还差什么"，得先把这张表补成真状态表。
- 上面 fixture 缺陷 4 与 5 **未修**。
- `record` 拒绝写入时报 `error <CODE> <id>`，**不带 message 与 remedy**（`_default_human` 只打印
  severity/code/subject，带 message 的那条只在 `quiet` 模式下走）。这是既有全局行为，但让新的拒绝
  路径不可行动。是否改渲染层（简明 vs 可行动）待定。
- RTK 混杂（C 节）：三轮演练共有，作用于**每一个** Claude Code session，含架构师交互式跑的。
  想拿干净证据得摘 hook —— 侵入性改动，先问架构师。

### 下一步

1. 修 fixture 缺陷 4（canonical state 内部一致）与 5（补齐或被指向的路径）—— 两者都是"没人埋的
   异常"，且 4 会让 session 无路可走
2. 判据 5 的修法：在 `session-continuity.md` 写明"等待期写**意图**、不写结论"（比改判据更对，
   因为它保留了判据的目的）
3. `env record` 的写入路径 + `environment.schema.json`
4. 把 V0 complete 那张表补成真状态表

### 动手前必须知道

4. **Bash 输出被 RTK 改写：`git status` 干净时只剩一个 `ok`。** `rtk hook claude` 是**用户全局**
   `~/.claude/settings.json` 里的 `PreToolUse` hook，把 `git status` 之类改写成 `rtk git status`。
   干净仓库的 `git status --porcelain` **不产出真实输出**。对演练尤其重要：这是**没人埋的异常**。
   应对写在 `~/.claude/RTK.md`（`rtk proxy <cmd>` 走原始输出）。**别去查 git** —— D2 用
   `GIT_TRACE` + plumbing 交叉验证才把它澄清。
5. **fixture 里的 commit 用 `drill:` 前缀、session 用 `fix:`** —— 这是两者**唯一稳定**的区分。
   作者字段分不出来，因为 builder 把 `git config user.email` 写进了 fixture。上一轮指南里有一处
   把 fixture 的 commit 当成了 session 的产物，就是这么来的。
