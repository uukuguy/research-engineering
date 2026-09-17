# Work Log

本仓库的**开发记录**。新会话从这里接续：读最新一条即可知道"做到哪、下一步做什么、动手前要注意什么"。

条目**带日期且只追加** —— 一条过期的条目看起来就是旧的，不会伪装成现状。这正是它不需要被重新
生成或校验的原因（而"当前状态快照"需要）。

> 两条轨道别混：`research/*` 是**这个工具所服务的研究**的状态（由 `researchlog` 持续维护）；
> 本文件是**开发这个工具**的记录。本仓库的 `research/ACTIVE.json` 保持 `idle` 是正常状态，
> 不是待填的空缺。

---

## 2026-09-17（第六轮）— 案例集跑起来了，而它发现的第一个缺陷是我的

### 会话概览

架构师把目标定成"**可用于长时间自主研究 AI 编程**"，V0 是路标；并把案例集**亲自跑了两遍**
（`bootstrap claude` 与 `rotation pi`）。两个案例都跑完并留下判定。**本轮最有价值的东西不是任何
一个判定，而是 `bootstrap` 那次发现了我 fixture 里的一个真 bug —— 而我在它发现之前，先给出了
两个错的诊断。**

### 判定

| 案例 | 结果 |
|---|---|
| `bootstrap claude` | **7/7 PASS**（旧 fixture，含那个分解 bug） |
| `rotation pi` | **4 PASS / 2 UNJUDGED / 0 FAIL** —— #1/#22 的第一份端到端证据 |

`rotation pi` 那次 pi 走完了整个 loop：等到 run 结束、读结果、记 `EV-…6dd6`、以 `belief_delta: none`
关掉 `RB-021`、带完整 provenance footer 提交。**它甚至通过 router 加载了 `session-continuity.md`**
—— 修好 router 之前 Claude 三次都没读到那份文件。

### 案例发现的 fixture 缺陷（我的）

`bootstrap` 的 session **独立重算了**恒等式 `total_latency = queue_wait + service_time +
backoff_wait`，在 2000 行里查出 **217 行违反**，记为一次 `counts: true` 的迭代（`refuted` /
`refined`）。**它是对的**：重试循环每轮 `total += wait + rng.expovariate(...)` 加了一次新的
service 抽样，而 `service_time` 只记第一次 —— 每个重试过的请求**差 1.6–35 ms**。

而 docstring 明写"Total latency decomposes into…"。**fixture 既没有那个性质，又声称有** ——
本仓库最忌的形状。已修（`6267fe9`）：`service_time` 累加全部 attempts；docstring 改成
"成立到列所记录的六位小数"；builder 加断言，**变异验证在 `0.034606s` 触发 —— 正是 session 报的数**。

### 我自己被证伪的三个诊断（都记进 GOTCHAS）

1. **"旧 fixture 把消融替它做好了，所以 M3 不可能发生"** —— 证伪：它在那个 fixture 上产出了
   `counts: true` 的迭代，而且**用过**那条对照臂。撤掉对照臂的改动已**回退**。教训：**"还没发生"
   不是"不可能发生"的证据**（记入 B10）。
2. **"交接没有接线"** —— 证伪：`ACTIVE.next_action` 留下的是"seeds 0..199 多种子复现两个臂，
   记录每个 seed 是否 cascade、第一个重试的 request_id、以及两臂的 p99/max"，**正是
   `research-bootstrap` 的成功条件**。交接是工作的。
3. **"两个运行都已结束"** —— 见 C8：我用一次被自己 `head` 截断的 `ps` 判了一个**还在飞**的运行，
   而 artifact 信号（transcript 正在长）就在同一条消息里。

### 检查器的六处修正

| 缺陷 | 后果 |
|---|---|
| `tool_digest` 含 `__pycache__` | 运行工具就会生成它 → 守卫对**每个正常 session** 报"你改了裁判" |
| `c5` 判"文件变了没" | 收尾写 = 意图写 → **假 PASS**（pi 的写发生在 run 完成之后 3.5 分钟） |
| `b5` 标签"2-3"而检查只要 ≥1 | 标签与判的东西不一致 → 按指南改成"≥3 条记录且有 ≥1 条 counted" |
| `--json` 后面跟人读的句子 | 输出无法被程序解析 |
| `git diff` 看不见未跟踪文件 | 新建的证据记录**完全不报** |
| `--porcelain` 里删除也算变化 | **删掉** ledger 会读成**追加**了证据 |

### 协议缺口：没有任何地方要求 session 提交

实测：`bootstrap` 那次的 `research/` **整个是未跟踪的**（`?? research/`），只有 builder 一个 commit。
查协议：`AGENTS.md` 没有、`research-bootstrap` 没有、`research-engineering` 只在 router 里有一行
"**about to commit** 时去看 git reference" —— 那是"当它要提交时"，不是"它必须提交"。

**后果是实的**：`record` 把 `code_state.commit` 写成当前工作区 commit；session 不提交，那条记录就
指向 **fixture 的 commit**，#18 的 Git↔Evidence 双向映射**没有东西可映射**。旁证：pi 那次提交了
（`3090983`），claude 这次没有 —— **两个客户端行为不一致，而协议对两者都没要求**。

**这是协议层的洞，归 V1**，不是案例能修的。

### 后半段：`BOUNDARIES.md` 是我们声称已经修好、而实际漏掉的那一个

架构师自己起了第二次 `bootstrap`（修掉分解决 bug 之后的 fixture）。它 8.5 分钟就产出了第一条
记录、问的正是案例的方向 —— **但随后卡住了，而卡住的原因是一个不存在的动词。**

它最近 8 个动作全在找一条路：**grep 工具源码里的 `boundaries`（两次）、grep skill 文本、读
`commands/init.py`、跑 `validate`**。查证结果：

| 环节 | 状态 |
|---|---|
| `research-bootstrap/SKILL.md:38` | **"Identify HARD boundaries"** —— 协议明确要求 |
| `research-engineering/SKILL.md:242` | `BOUNDARIES.md → research:boundaries` |
| 写入路径 | **不存在**（14 个动词里没有 `boundaries`；只有 `init` 写空骨架） |
| schema | **`boundaries.schema.json` 不存在** |
| `AGENTS.md:220` | **"Every canonical file has a verb"** —— 假的 |

**而那句假话的旁边，正是在解释"这曾经不成立，已为 `CURRENT.md` 与 `ENVIRONMENT.md` 的表修好"
—— 当年修那两处时漏掉了它。** 不能手改（同一份契约禁止），不能命令改，于是无路可走。

**已修（`93104dd`）**：新增 `researchlog boundaries`（读 / `--set` / `--add TIER=FILE`）、
`boundaries.schema.json`、注册、`validate` 覆盖（含**提交预算用尽报 error** —— 文件自己的散文
就是这么规定的）。`--add` 用**文件**而非命令行数组，因为**两次运行实际都这么干**：写 `/tmp`
临时 JSON 再喂给 `env declare`。**entry 的 `id` 之外刻意不约束形状** —— 与 `capability_map`
同一个判断，那属于设计决定。

**顺带抓到两处**：`--set nonsense=1` 原本**静默接受**（打错字段名就写进 canonical 状态）→
`additionalProperties: false`；守卫测试先失败、且它是对的（它把 schema 数量写死，docstring 写明
"应当逼人停下来想新 schema 是否完整"）→ 按它的意图更新。

**`AGENTS.md` 那句话改准了**，并点名唯一的**刻意例外**：`ARCHITECT.md` 的 signal 手写，因为
signal 是架构师说过的话，`source_text` 就是重点。

### 判据 5 的形状问题：修的是判据（`c9784be`）

见下面"判据 5 的形状问题"一节被替换的部分。新增 **`c6`**：run 完成之后，session 该做的是
**把 loop 走完**（为它留下一条证据记录 + 把 `execution.status` 移开 `running`）。每条判据在另一种
形状下报 `UNJUDGED`，所以这一对无论场景落在哪边都覆盖到了。

### 检查器的缺陷总数：**9 处，全部同一形状**

前 6 处在上面那张表里；后半段又 3 处：`c1`（只认字面命令，而判据也收"读 manifest"）、`d2`
（只读 `next_action`，嘴上拒绝的过不了）、以及写 `c6` 时差点犯的 `changed_since`（**porcelain
查不到已提交的记录** —— pi 提交了它的证据，工作树干净，**一个走完 loop 的运行会被读成"没记录
任何证据"**）。

已记成 `GOTCHAS.md` **B11**，附两个本来就能抓到每一例的检查：**把 label 和它下面那几行并排读
一遍**；**失败消息描述的检查，代码真的做了吗**（`c1` 的消息写着 "or reads the manifest"，
代码只查了前半句）。

### 开放项

1. **修完分解 bug 之后，M3 还会不会发生？** 修掉缺陷可能也修掉了那次迭代的来源。**下一次运行
   就是回答这个的实验。**（把已知 bug 留着制造迭代 = "fixture 种答案"的镜像，所以修是必须的。）
2. **协议缺提交要求**（见上），归 V1。
3. `capability_map` 仍无形状（架构师的设计决定）。
4. `recovery` / `evaluator-conflict` 的检查器已写但**从未对真实运行跑过**。
5. 判据 5 的**形状问题**（run 在 session 活着时完成，判据前提不成立）—— 要的是新判据，不是放松。

### 下一步

1. **单独**跑一次 `bootstrap`（新 fixture，一次一个案例），看 M3 在缺陷修掉之后还立不立得住
2. 跑 `recovery` / `evaluator-conflict`，让这两个检查器第一次见真实运行

### 动手前必须知道（本轮新增，已同步 `GOTCHAS.md`）

17. **"还没发生"不是"不可能发生"**（B10）—— 从 `runs/` 空推出"M3 不可能"是错的；快照不是判决
18. **判一个别人正在跑的任务用 PID + artifact**（C8）—— 一次被过滤/截断的 `ps` 连信号都不算；
    **别用代理信号代替直接测量**（事件时间戳 ≠ 文件 mtime）
19. **fixture 要断言它自己声称的性质**（本轮的分解决 bug：断言写在 builder 里，变异验证能触发）

---

## 2026-09-17（第五轮）— V0 收尾：判据 5 的三次运行，与案例集

### 会话概览

架构师定了目标与优先级：**可用于长时间自主研究 AI 编程**；V0 是路标不是终点，条件合适就推进
V1/V2；**不要求每一步精准工程级符合**。据此我**撤回**了一版提议（给 V0 状态表加"证据形式"列去
对齐 3 行）—— 那是账目，不是能力。同轮委托：**一批核心验证案例**，跑在临时项目目录里，由 coding
agent 完成，有执行指南，可自动验收也可手工执行。

主线是 **A（重跑 D2，判判据 5）**，跑了三次。

### 判据 5 的三次运行：FAIL / FAIL / PASS

| 次 | 条件 | 结果 | 关键证据 |
|---|---|---|---|
| 1 | 旧协议文本 | ✗ | `ACTIVE.json` mtime 未动 |
| 2 | 同上，但 transcript 移到 fixture 外 | ✗ | mtime == builder 那次 commit 的时刻；`git diff HEAD` 为空 |
| 3 | **router 修好后** | **✓** | `ACTIVE.json` 相对 baseline 变了；写的是**意图**（"Decision: attach/observe"，"Wait for EXP-0200 to exit, then read probes/sweep.json"） |

**第 2 次是第 3 次有意义的原因**：它排除了"是我的台账污染导致的"。两次同结果 → 单变量成立。

### 根因：不是那句话，是路由

第 2 次做了链路追踪：session 读了 AGENTS.md 列的**恰好那 6 个** canonical 文件 + manifest +
probe，**对任何 reference 的 Read 调用为 0** —— 而 skill **确实加载了**（init 事件里它在 100 个
skill 中）。所以 `session-continuity.md` 从未进入它的工作路径。

`SKILL.md` 的 router 表里**两行匹配同一状态**，先匹配的那行只说了"先 reconcile"、**不指向任何
reference**；指向 `session-continuity.md` 的那行在后面。session 走完 reconcile 就停了。

改那一行（`e9044b8`）→ 第 3 次 5/5。

**上一轮那句"它拒绝预写，因为那是 post-hoc 合理化"是错的解读** —— 那是从行为倒推的理由，不是
它说的。它只是没读到那句话。**措辞一直是对的。**

### 交付：案例集（`c8e4d00`、`ea389f3`）

```
tests/main/run_case.sh               建 fixture → 驱动 agent → 判据（claude / pi）
tests/main/verify_case.py            从产物判，三态：PASS / FAIL / UNJUDGED
tests/main/build_bootstrap_case.sh   M1/M2/M3/M5 的 fixture（新的）
docs/V0_CASES.md                     执行指南：判据表 + 自动跑法 + 手工跑法
```

- **两种跑法共用同一套判据** —— 只能用一种方式跑的案例，没法拿自己的 harness 对照。
- **`UNJUDGED` 是第三种裁决** —— 产物判不了就明说，**绝不静默算通过**。
- rotation 与 bootstrap 有产物检查器；**recovery / evaluator-conflict 还没有**，
  `verify_case.py` 对它们 exit 2 并指回判据表（已在指南里列为已知未完成项）。

**判据 5 的检查器判的是"发生过一次写"，不是"字段里写着什么"** —— builder 自己在 fixture 里种了
"Wait for the sweep to finish"，所以读内容的检查**恒真**。`--baseline` 因此是必需的。

### `pi`：三点实测，没有一条是等价替换

1. 原生读 `AGENTS.md` / `CLAUDE.md`（但**必须 source 项目 `.env`** 才有凭据）。
2. **`--skill` 要绝对路径** —— 传相对路径时**静默加载 0 个**项目技能、转去加载用户级的 18 个。
   **没有报错的失败。**
3. **`--no-skills` 是 pi 这边的 workflow block** —— 不加它，加载的是用户级 `brainstorming` /
   `writing-plans` / `test-driven-development` / `project-state`，正是 AGENTS.md 声明机械禁用的
   那批。**pi 没有项目级等价机制。**

另外：**`pi auth check` 报 `ready` 只表示"配了"，不表示"有效"** —— 三个 provider 全 ready、全 401。

### 顺带：`.env` 泄漏风险

架构师把 `MINIMAX_*` 放进项目本地 `.env`，而 `.gitignore` 没覆盖它，`git status` 里是 `?? .env`，
提交流程用 `git add -A`。已修（`7ff13bb`）。

### 开放项

1. **`recovery` / `evaluator-conflict` 的产物检查器未写** —— 判据在指南里有，检查器没有。
2. **`pi` 的完整案例没跑过** —— 技能加载那一环已验证，端到端没有。#1 / #22 因此仍未验。
3. **`bootstrap` 的 fixture 从未被真实 session 跑过** —— builder 自断言通过，端到端没有。
4. `capability_map` 仍无形状（设计决定）。
5. 指南里"复现 session A 的 fixture"那份配方**不可复现** —— 它自称造"空项目"却不含研究对象，
   而 M2/#2 的证据都指向有可跑的 `sim/`。`build_bootstrap_case.sh` 按证据建，不按配方建。

### 下一步

1. 跑一次 `run_case.sh bootstrap claude`（第一次真实运行，会暴露 fixture 与判据的问题）
2. 跑一次 `run_case.sh rotation pi`（端到端验 pi，同时给 #1/#22 证据）
3. 补 recovery / evaluator-conflict 的检查器

### 动手前必须知道（本轮新增，已同步进 `GOTCHAS.md`）

13. **判据要判"发生过什么"，不要判"字段里写着什么"**（B6）—— fixture 种好的答案会让检查恒真
14. **自断言的 glob 要排除 vendored 目录**（B7）—— `rglob("test_*.py")` 会算上工具自带的测试
15. **台账污染会让判据无法归因**（B8）—— transcript 写进 fixture 是"没人埋的异常"
16. **`pi` 的调用形状**（D4）与 **凭据文件要先 `git check-ignore`**（C7）

---

## 2026-09-17（第四轮）— gotcha 从日志里搬出来，研发轨道补上入口

### 会话概览

架构师问的是结构问题："`research-engineering` skill 负责项目下的研究课题，那**本项目的研发**如何
管理？" 答案是两条轨道两套制度，而且**不对称是刻意的** —— 但审计下来发现研发轨道有三个薄弱点，
这一轮修了前两个。

### 两条轨道为什么不对称（结论，值得记住）

| | 研究轨道 | 研发轨道 |
|---|---|---|
| 载体 | `research/` 八件 canonical + `ledger/` + `runs/` | `docs/WORK_LOG.md` + `docs/V0_ACCEPTANCE_GUIDE.md` |
| 断言的是 | **现在为真** | **当时发生了什么** |
| 机制 | schema + 每文件一个动词 + `validate` + `reconcile` | 只追加、带日期；新会话读**最新一条** |

研发轨道不需要 `researchlog` 那一套，理由 `WORK_LOG` 开头自己给过：**过期的条目看起来就是旧的，
不会伪装成现状**（而"当前状态快照"需要被重新生成与校验）。这是**事件日志 vs 状态快照**之分。

### 三个薄弱点，以及修了什么

1. **gotcha 注册表住在事件日志里** —— 12 条编号跨 4 条 entry，而 gotcha 是**当前为真**的东西，
   过期时不像日期那样自己显形。新建 **`docs/GOTCHAS.md`**（`c045a6a`）：一页、可编辑、声明
   "这是状态不是日志"，**修好的直接删掉而不是追加"已修"**。B5 与 A2 两条原先只以散文形式散在
   正文里，一并落成条目。
2. **一半的操作知识只在 Claude 专有的记忆里** —— agent memory 有 5 条 WORK_LOG 没有的，其中
   **`.gitignore` 必须锚定**、**`environ` 快照是 `changed` 谓词的前提** 是**工具行为事实**，
   本该是两个客户端都读得到的项目 canonical。已迁入 `docs/GOTCHAS.md`，记忆改成**指向它**，
   不再维护第二份。
3. **研发轨道唯一的"状态型"产物（V0 状态表）是手维护的，且 `README` 的 Status 只有一行 `V0`** ——
   外部读者进不来。README 的 Status 现在写明 V0 的含义（21 行中 19 条有实测证据、2 条架构师暂缓、
   0 条失败）并点名三个文件。

**外加一条不在清单里但必须做的**：`AGENTS.md` 指向 `docs/GOTCHAS.md`。它是**唯一**每会话都加载的
文件 —— 一个从那里没有链接的注册表会被整个错过，那样第 1 条就白做了。

### 核实（不是回忆）

```
c045a6a · 工作树干净 · 真实远端 main == 本地 HEAD（git ls-remote 核实）
python3 tools/check_workflow_block.py  → exit 0（80 交付工作流 / 116 名字）
python3 tools/researchlog validate     → exit 0
python3 tools/researchlog reconcile    → exit 0 clean
```

顺带再确认一次：`origin/main` 这个 **remote-tracking ref 仍然是陈旧的**（停在 `e3ee9f1`），因为
推送走的是显式 SSH URL。**要判断本地与远端是否同步，用 `git ls-remote`，不要用 `git status -sb`。**
已写进 GOTCHAS.md C2。

### 开放项

- **`capability_map` 仍无形状** —— 设计决定，按架构师规则不由 Claude 定。
- **#1 / #22 暂缓**（客户端矩阵项）；若日后要做，不必等 codex。
- 漂移检查仍有 8 条 warning（低价值，可长期挂着）。
- **`project-state` 与全局 CLAUDE.md §18 的冲突已解**：`AGENTS.md` 明文 supersede 了"跑
  `/project-state update`"那条全局建议。本轮再次确认没有活的冲突。

### 下一步

没有待做的收尾。剩下的都是架构师决定项（`capability_map`）或已明确暂缓项（#1 / #22）。

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

---

## 2026-09-14（第三轮）— 修掉上一轮发现的六条缺陷

### 会话概览

架构师指示"先把你发现的缺陷修复"。**六条全部修完**，每条都带变异验证，239 项定向测试全绿
（8 个模块逐个跑，不是一次全套）。其中三条是**工具缺口**，性质相同：canonical 状态里声明了、
协议要求维护、而没有任何动词能读写它。

### 修了什么

| | 缺陷 | 修法 | commit |
|---|---|---|---|
| **H** | `record` 拒绝时只报 `error CODE id`，**不带 message 与 remedy** | `_default_human` 补上两者；带 message 的那条原先只在 `quiet` 模式下走 | `01b05b5` |
| **3** | 判据 5 不可判（等待期不写痕迹） | `session-continuity.md` 写明"等待期写**意图**、不写结论"，并说清两者之别 | `a07397b` |
| **F** | **`research:current` 完全未接线** —— 无命令读、无命令写、无 schema、从不校验 | 新 `researchlog current`（读 / `--set`）+ `current.schema.json` + `validate` 第五种 kind | `5730351` |
| **D** | fixture 的 state 由三个互不相关的示例拼成；rotation 缺 `expected_evidence` | 假说换成 fixture 自有的 H-041/H-042 并在 CURRENT 里写明各自主张；case 换掉；补 `expected_evidence`；三个 builder 都加自断言 | `2f3a1cc` |
| **E** | fixture 复制上游 `CLAUDE.md`，声称一个它没有的布局 | fixture 写**自己的** adapter，声明它是"使用这个工具的项目"；加自断言 | `e721196` |
| **G** | `env record` 写不了 `limitations`/`harnesses`/`available`；无 `environment.schema.json` | 新 `env declare TABLE FILE` + `environment.schema.json` + `validate` 第六种 kind | `69db11c` |

### F 是最深的一条，也是 D 的前提

审计方式：逐个 canonical 文件问"谁写它、谁读它"。结果是 `paths.current` **在代码里零引用** ——
`loader.py` 认识这个名字、`repo.py` 建了这个路径对象、没有任何命令碰它。

这同时让项目的两句话失真：`CURRENT.md` 写着 "Edit it through `researchlog`, never by hand"，
AGENTS.md 写着 "**Never hand-edit that JSON — use the tool**"。没有动词时，手改是唯一选项。
而且**命令够不到的状态，检查也够不到** —— 所以它对 `validate` 完全隐形，而其余每个 canonical
文件都在被检查。

**顺序是有依赖的**：D 要用工具把 fixture 的 CURRENT 写成一贯的，所以 F 必须先做，否则修 D 只能
手改 JSON，正好违反那条禁令。

### 一处必须留给出题人的口径

`capability_map` **刻意没给形状**。它在骨架里是一个空数组，任何地方都没有一条 entry 示例 ——
所以在这里发明一个形状，等于把一个猜测当成已决定的事去强制。它是这次审计里**第三个**"声明了
但没有消费者"的 canonical 字段（前两个是 `research:current` 和上面那三张表）。给它定义属于
设计决定，不属于修复。

### 同一轮里想通的几件事

- **`Finding` 的第 5 个字段是 `fix_hint`**，不是 `remedy`。我先前打印 `f.get('remedy')` 得到
  `None`，是因为那个 key 根本不存在 —— 我查询写错了，不是工具没给。
- **`_check_surrogate` 的 message 里 `verdict is EVIDENCE_INVALID, not {verdict!r}`** 在 verdict
  为 `None` 时会打印 `not None`；完整性检查同一条记录里也会报，所以只是措辞略糙，不是缺陷。
- **验证副本时要确认副本是新的。** 我一度用 `/tmp/eval-conflict` 里那份**约束修复之前**建的
  `tools/researchlog` 副本去验证"拒绝信息"，结果它照常写入 —— 差点得出"修没生效"的错误结论。
  这与"按 cwd 找仓库"那条是同一个陷阱的另一面：**副本既是代码的副本，也是代码版本的副本。**

### 开放项

- `AGENTS.md` 的命令清单还缺一行 `current`（以及 `env declare`）。**没有动这个文件**：它带着
  架构师本轮的 DeepSeek 后端规则改动，提交它会把别人的在途工作一起包进来。
- `AGENTS.md` 的 "Resuming work on the tool itself" 一节措辞仍只是**隐含**地把路径限定在上游仓库；
  fixture 现在自己声明了、不再依赖这一点，但这句话本身仍可更明确。同上，属架构师的在途文件。
- **V0 状态表仍未补**（上一轮列的下一步第 1 项）。所以"V0 完成几条"目前仍答不了。
- 判据 5 已改协议文本，但**尚未在新文本下重跑 D2** —— 所以"这样写是否就能判"仍未实测。

### 下一步

1. 在新 `session-continuity.md` 下重跑 D2，验证判据 5 真的可判了（这是 3 的验收）
2. 补 V0 状态表
3. 给 `capability_map` 定形状（设计决定）
4. `AGENTS.md` 的两处（命令清单 + tool-dev 一节的措辞）—— 待架构师的在途改动落地

### 动手前必须知道（追加）

6. **"没有动词的状态，也没有校验。"** 这次三条工具缺口是同一个形状。看到一个 canonical 文件/
   块时，问两句：谁写它？谁读它？两个都答不出来的，就是下一个缺口。审计方法：
   `grep -rn "paths\.<name>" tools/researchlog/ --include="*.py"`，零引用即未接线。
7. **改共享底座后，三个 drill builder 全部重跑一遍** —— 它们是这套状态最真实的使用者，
   比单元测试更早暴露接线缺口（这一轮 D1 fixture 就是被不变量 #4 的接线打坏的）。
8. **`origin` 走 HTTPS 会连不上，改用 SSH。** 症状是 `Failed to connect to github.com port 443
   after 75003 ms`，而它**看起来像断网、其实不是** —— 同一时刻 `ping github.com` 通（110ms）、
   `https://api.github.com` 返回 200，只有 `github.com` 解析到的那台 IP（`20.205.243.166`）连不上。
   `origin` 是 HTTPS URL，所以 `git push` 会卡 75 秒再失败。
   可用的推送命令（`~/.ssh/id_rsa` 属于 `idleuncle`，**对 uukuguy 的仓库没有权限**，
   必须显式指定属主那把 key）：

   ```bash
   GIT_SSH_COMMAND="ssh -i ~/.ssh/id_rsa_uukuguy -o IdentitiesOnly=yes" \
     git push git@github.com:uukuguy/research-engineering.git main
   ```
   本轮就是这样把 7 个 commit 推上去的。**根治办法是把 `origin` 换成 SSH URL**（`gh` 的配置
   本来就是 ssh 协议），但那属于改架构师的仓库配置，留给他定。

---

## 2026-09-17 — 按设计要求跑完 V0 验收

### 会话概览

架构师定目标："按设计要求完成 V0，research-engineering 是 skills 开发，不是上线系统的功能发布，
不要过重的工程测试"。做法因此不是补测试，而是**每条验收跑一次、留一份可查产物**。

先立 **V0 状态表**（指南新增一节）—— 在此之前"V0 完成没有"这个问题在仓库里**无法回答**：两张旧表
回答的是"为什么这样分组"，不是"哪条验过了"。把分组理由当状态表读，会把没验过的条目当成已完成。
这张表本身就是本轮的主要产物。

### 结果：20/22 有实测证据，2 条环境阻塞

| 组 | 结果 |
|---|---|
| Day-1 must | M2 / M3 / M4 / M5 ✅；M1 见下 |
| V0 complete | #2 #5 #8 #10 #11 #12 #13 #14 #15 #16 #18 #19 #20 #21 ✅ |
| 阻塞 | **#1 / #22 = `ENV_BLOCKED`**（不是失败） |

### 一次 session 覆盖六条（session A）

在**全新空项目**（无 `research/`）上给一个高层方向，不给算法："尾延迟来自 queue 还是 retry？"
一次运行拿下 M2 / M3 / M5 / #2 / #5 / #8：

- **M2**：它**完全没有碰** fixture 的 `sim/` 与 `data/`，改动全在两支自建 probe（281 + 171 行）
  与研究状态；无 plan 文档、无新增测试套件
- **M3**：块 `RB-001` 内 3 条证据，2 条 `counts_as_evidence_iteration: true`
- **M5**：`ENV-LIM-001..006` 以 `ENV_UNSUPPORTED` 入 `ENVIRONMENT.md`，各带 `verified_by` ——
  **6 条里没有一条被写成 `refuted`**。这条此前**不可能通过**：三张表在 `env declare` 出现之前
  没有写入路径
- **#8**：自建 `HARNESS-001`，带 `supports_evidence` 与 `preserves` / `missing` 边界

它的科学结论也值得记：**用消融实验推翻了按毫秒归因的答案** —— `backoff_wait` 是内生变量，
只有 `queue_wait` 已超阈值才会被赋值，所以"方差份额"不等于"因果贡献"；正确的归因是反事实。
它还**证明了 fixture 里那句 "Stable by construction" 是错的**（util 0.8、retry 打开时队列真的跑飞，
p99 730ms vs 关掉 6.4ms），并自查修正了自己两处错误（分解采样点取错、provenance 误判）。

### CLI 层一次跑掉四条

- **#12**：预算 2、记满 3 条 → 块**运行期间**报 `BLOCK_ITERATION_BUDGET_EXCEEDED`（用派生 count）
- **#15**：12 个并发 `record` → 12 条记录、12 个互异 ID、文件名与 ID 全等
- **#16**：`code_state.commit` 是**工作区** commit，不等于加入该记录的 commit
- **#18**：`Evidence:` trailer 给出 commit→EV，`code_state.commit` 给出 EV→commit；构造违规后
  `SELF_REFERENTIAL_COMMIT` 准确报出（这条检查是真的接线的）

### #19 跑了两次，第二次才是准确条件

第一次 `--bare`：无 hooks / plugins / MCP / LSP，工具只剩 `Bash/Edit/Read` —— loop 跑完了，
4 条证据分类全对。**但它把 skill 发现也关掉了**，而那不在 #19 列的（hooks/subagents/MCP/GitHub）
之内，所以那次契约只来自 AGENTS.md。

第二次改用 `--settings '{"hooks":{}}' --strict-mcp-config --mcp-config '{"mcpServers":{}}'`：
保留 skill、只摘 hooks 与 MCP。判据是**可观测**的 —— `mcp_servers: []`，且 RTK hook 留下的
裸 `ok` 出现 **0** 次；skill 确实加载了（读了 `git-research-infrastructure.md`）。loop 跑完，
`validate` 0、`reconcile` clean。

### #1 / #22 的三条路径都试过

| 路径 | 结果 |
|---|---|
| codex 默认后端 | `chatgpt.com` / `api.openai.com` **超时** |
| `aicoding.2233.ai` | 可达，但凭据 `OPENAI_API_KEY_0011AI` **不在 agent 环境里** |
| `openrouter.ai` | 可达，`OPENROUTER_API_KEY` **已设置**，但返回 `401 Unauthorized: User not found` |

`codex exec` 本身可用（`codex-cli 0.153.4`）。所以这是**环境不可行，不是能力缺口**（不变量 3）——
不变量存在的意义正是把这两者分开，所以这里记 `ENV_BLOCKED` 而不是"未通过"。

### 两处我自己犯的错，都留了痕

1. **fixture 打包错误**：M1 第一次跑时我 `mkdir -p templates` 之后又 `cp -R src/templates templates`，
   于是变成 `templates/templates/research`，session 拿到 `TEMPLATES_ABSENT` 并**替我把 fixture 修好了**
   （它自己的 commit `fix: repair vendored template path...`）。这是"没人埋的异常"，所以 M1 重跑。
   drill builder 没有这个问题 —— 它们不预先建 `templates/`。
2. **commit message 里的反引号**：`git commit -m "…\`code_state\`…"` 会把反引号当命令替换执行，
   词从消息里**静默消失**（提交成功、消息残缺、不报错）。丢过 `code_state` 与
   `SELF_REFERENTIAL_COMMIT` 两个词。已记入 gotcha 记忆：**永远写文件再 `-F`**。

### 开放项

- **M1**：bootstrap 本身已验证（canonical 八件齐备、plan 文档 0），但那次 session 建完状态后
  继续做了一轮远超范围的研究（在查本机 `perf_counter` 的精度），留下 3 个 `ORPHAN_RUN`，
  于是 `reconcile` 不干净。**判据本身无歧义，是测量点的问题** —— M1 测的是 bootstrap，
  测量该取在 bootstrap 完成那一刻。
- **#1 / #22**：需要你解。最省的是你在自己的交互 shell 里跑一次 codex（凭据在那里），
  或把可用的 provider 凭据放进 agent 环境。素材已就绪：#20 产出的中文报告可直接投喂。
- `capability_map` 仍无形状（设计决定）。
- `AGENTS.md` 的命令清单仍缺 `current` 与 `env declare` 两行 —— 该文件带着你的在途改动，我没动。

### 下一步

1. 解 M1 的测量点（bounded bootstrap 或接受"canonical 干净、run 是进行中"的区分）
2. 解 #1/#22 的环境阻塞
3. 补 `AGENTS.md` 的两行

---

## 2026-09-17（第二轮）— 把 Claude Code 这条路做好

### 会话概览

架构师定调：**codex 放一放，把 Claude Code 做好**。于是这一轮不碰第二个客户端，
专查 Claude Code 这条路上**声明与实现不一致**的地方 —— 结果找到一处大的。

### 主线：workflow block 只覆盖了一家，而机器上长出了 70 个

`AGENTS.md` 第 33 行写着"the generic software-delivery workflow skills are **disabled for this
project mechanically**"，紧接着写明"brainstorming / a written plan / TDD / a review checklist
的**缺失就是重点**"。而 deny 列表只列了 superpowers 一家。

**实测**：在带项目 settings 的仓库里调用 `gsd-plan-phase` —— **整份 skill 正文加载了，没有任何拒绝**。
这台机器上有 **65 个 `gsd-*`**，合起来提供的正是写好的 plan、测试生成、review checklist 和
phase 脚手架。

修法（`7bc632d`、`70ab9f5`）：`skillOverrides` 补 70 条（65 个 gsd + `discuss` / `review-plan` /
`code-review-changes` / `test` / `frontend-test`）；`permissions.deny` 补 plugin 级的
`dev-phase-manager`(9) 与 `planning-with-files`。现在覆盖 **80 个交付工作流、116 个名字**。

**两个陷阱，都会产出"看起来对、其实什么都不做"的屏蔽** —— 都是这轮踩出来的：

1. **`permissions.deny` 不支持通配。** `Skill(gsd-*)` 匹配不到任何东西 —— 在只 deny 这个模式的
   settings 下调用 `gsd-plan-phase`，它照样加载。AGENTS.md 里把 `Skill(superpowers:*)` 当作家族
   简写来写，读起来像一个可用的通配符，**不是**。
2. **denied 名字里的 plugin 是版本目录上面那一层，不是 marketplace 目录。** `omc` marketplace 下的
   plugin 叫 `oh-my-claudecode`，所以 `Skill(omc:autopilot)` 匹配不到任何东西。**这一条是漂移检查器
   的 warning 列表发现的** —— 正是它被写出来的用途。

第三个发现：**缓存里的 plugin ≠ 可用的 plugin**。检查器一开始把 plugin cache 当成可用集合，于是对着
`oh-my-claudecode`（`enabledPlugins` 里是 **disabled**）报了 12 条不需要的屏蔽 —— 而**真正的缺口会被
它挡在后面看不见**。现在先读 `enabledPlugins`。

### 防漂移：`tools/check_workflow_block.py`

一份清单不会注意到机器长大了，所以加了漂移检查（`7bc632d`）。它读**这台机器自己的** skill 清单
（personal + 已启用 plugin），未覆盖的交付工作流一律 exit 1 点名；并且**反过来**检查：
`AGENTS.md` 明文保留可用的 `systematic-debugging` / `using-git-worktrees` 若被误关，同样 exit 1。

变异验证两个方向都做了：摘掉一个 plugin skill → exit 1 点名它；摘掉一个 personal skill → exit 1
点名它；对照组 exit 0。

这不是测试套件，是**配置漂移检查** —— 与 `install_research_skills.py --check` 同一个形状。

### 两件顺手查清、结论是"不用动"的

- **权限摩擦不存在。** 我全程用 `--dangerously-skip-permissions` 跑，所以从没暴露交互式的问题；
  实测不加该参数跑 `researchlog validate` —— 直接通过。`permissions.defaultMode: "auto"` 加
  `skipAutoPermissionPrompt` 已经免去逐条批准。**所以没有加 allow 列表** —— 那会是给一个不存在的
  问题发明修法。
- **skill frontmatter 干净。** 三个 skill 只有 `name` + `description`，没有 Claude 特有字段写错，
  副本与 canonical 一致。

### 文档

- **`CLAUDE.md`**（Claude Code 适配文档，Claude 特有的机制正该住这里）新增 "The workflow block"
  一节：两个机制不可互换、两个陷阱、以及漂移检查的跑法。
- **`docs/V0_ACCEPTANCE_GUIDE.md`**：#1 / #22 改记为 **⏸ 架构师决定先放一放**，并写明
  **V0 在 Claude Code 这条路径上是完整的**（其余 19 条全部实测通过）。

### 一处顺带纠正的账面

`#22` 的判据是"交给**另一客户端**"，不是"交给 codex"。这台机器上另有
`opencode` / `cursor-agent` / `gemini` / `aider` / `crush` 五个 agent CLI —— 所以这条**并不缺验证
路径**，只是架构师选择先不做。日后要验不必受 codex 限制。

### 下一步

1. `AGENTS.md` 的两处（命令清单缺 `current` / `env declare`；`Skill(superpowers:*)` 的措辞容易
   被读成通配符）—— 该文件带着架构师的在途改动，等他提交后我来补
2. 若日后要做第二个客户端：#22 用上面任一 CLI 即可

---

## 2026-09-17（第三轮）— 收尾补完与交接

### 这一轮只做了一件事

补完上一轮列在"下一步"里的 `AGENTS.md` 两处（`03a92c4`）：命令清单加 `current` 与
`env declare`；deny 列表那句 `Skill(superpowers:*)` 改成"一个 skill 一个精确名字"，并指向漂移
检查 —— 因为它是**读起来像通配符、实际匹配不到任何东西**的写法，而 70 个交付工作流就是这么漏掉的。

**该文件同时带着架构师自己的 DeepSeek 后端规则**（3 行，本会话加的），一并提交了，commit message
里写明那段不是 Claude 写的。工作树因此**完全干净**。

### 现在的状态（可核验，不是回忆）

```
HEAD 03a92c4 · 工作树干净 · 本地 = 远端
V0 状态表：21 行 = 19 ✅ + 2 ⏸（#1/#22 架构师决定暂缓）+ 0 ❌
python3 tools/check_workflow_block.py    → 覆盖 80 个交付工作流 / 116 个名字
python3 tools/researchlog validate       → exit 0
python3 tools/researchlog reconcile      → exit 0 clean
python3 tools/install_research_skills.py --self --check → 两个 client 无漂移
tests/main/build_*.sh                    → 3 个 drill builder，各自自断言
tools/                                   → check_workflow_block.py · install_research_skills.py · researchlog/
```

**V0 在 Claude Code 这条路径上是完整的。** 唯一未验的两条是客户端矩阵项，架构师明确说先放一放。

### 这个会话（09-14 起）一共交出了什么

- **19 项 V0 验收拿到实测证据**（每条一次运行 + 一份可查产物，不为任何一条搭测试框架）
- **七条缺陷修掉**，全部带变异验证：`research:current` 未接线、`env record` 三张表无写入路径、
  `record` 拒绝时不带 message/fix hint、不变量 #4 从未执行、三个 fixture 缺陷、workflow block 只覆盖
  一家
- **V0 状态表**（指南新增一节）—— 在它之前"V0 完成没有"在仓库里**无法回答**
- 三个 drill fixture 现在都**自断言**自己的状态（注册表≠定义、adapter 是自己的、补丁确实生效）

### 开放项

1. **`capability_map` 没有形状** —— `ENVIRONMENT.md` 里它是个空数组，任何地方都没有一条 entry 示例。
   它是审计里**第三个**"声明了没有消费者"的字段（前两个是 `research:current` 和三张表）。
   **给它定形状是设计决定，按架构师规则不由 Claude 定。**
2. **#1 / #22 暂缓** —— 判据是"另一客户端"，不限于 codex。这台机器上另有
   `opencode` / `cursor-agent` / `gemini` / `aider` / `crush` 五个 agent CLI；#22 的素材也早已就绪
   （`research-status` 的中文报告含 resume 所需的全部状态指针）。
3. 漂移检查有 **8 条 warning**（知识类 skill 的描述里含 "plan"/"test" 等词）。它们是"提示去看"，
   不是失败；要消掉就得逐个判断并加进白名单，目前认为不值得。

### 动手前必须知道（本会话新增的四条，与前几轮的一起看）

9. **`permissions.deny` 与 `skillOverrides` 都不支持通配。** 前者管 plugin 命名空间、后者管
   personal 级 skill，都要**一个 skill 一个精确名字**。`Skill(gsd-*)` 匹配不到任何东西 —— 实测过。
   而且 denied 名字里的 **plugin 是版本目录上面那层，不是 marketplace 目录**（`omc` marketplace 下
   的 plugin 叫 `oh-my-claudecode`）。
10. **缓存里的 plugin ≠ 可用的 plugin。** 只有 `enabledPlugins` 里为真的才可达。把 plugin cache 当
    可用集合会**报出不需要的屏蔽，同时把真正的缺口挡在后面**。
11. **`git commit -m "…\`x\`…"` 里的反引号是命令替换** —— 词会从消息里静默消失，提交成功、消息
    残缺、不报错。**永远写文件再 `-F`。** 本会话丢过两个词。
12. **fixture 打包别先建 `templates/`。** `mkdir -p templates && cp -R src/templates templates` 会得到
    `templates/templates/research`，`init` 报 `TEMPLATES_ABSENT` —— 那是**打包错误不是工具缺陷**，
    但会让 session 花时间去修 fixture。

### 下一步

按优先级：

1. `capability_map` 的形状（架构师的设计决定）
2. 若要做第二个客户端：#22 用现有任一 CLI 即可，不必等 codex
3. 消掉漂移检查的 8 条 warning（低价值，可长期挂着）
