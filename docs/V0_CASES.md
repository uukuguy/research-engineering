# V0 核心验证案例 —— 执行指南

V0 路标的收尾：**一批核心验证案例**，每个在**临时项目目录**里由一个 coding agent 完成，
判据写在纸面上，验收可以自动跑也可以手工跑。

这套东西回答的不是"V0 完成了没有"（那是 `V0_ACCEPTANCE_GUIDE.md` 的状态表），而是
"**换一个客户端、换一天，这些能力还在不在**"。所以它要能重复跑，而不是一次性演示。

## 一个案例是什么

```
fixture（临时项目目录） + 给 session 的那两行 + 判据 + 验收
```

- **fixture** —— `tests/main/build_*.sh` 造。每条 builder 都**自断言自己的状态**：fixture
  不成立时报的是"改 fixture，不要改判据"，而不是让你去怀疑 session。
- **给 session 的那两行** —— 协议本身，不含提示。多给一句提示，测的就不是协议了。
- **判据** —— 每个案例一张表，逐条可核。
- **验收** —— `tests/main/verify_case.py`，从产物判，不读 transcript（除非判据本身是
  transcript 事实）。

## 两种跑法，共用同一套判据

```bash
# 自动：建 fixture → 无头驱动 agent → 判据
tests/main/run_case.sh <case> <client> [seconds]

# 手工：自己建、自己驱动，然后判同一套判据
tests/main/build_rotation_drill.sh /tmp/x 900
cd /tmp/x && claude                      # 或 pi
#   只给两行：/research-engineering
#             Continue current research.
python3 tests/main/verify_case.py rotation /tmp/x --baseline <建完时的 HEAD>
```

**判据不因驱动方式而变** —— 一个只能用一种方式跑的案例，是没法拿自己的 harness 去对照的。

`--baseline` 是**必需**的（rotation）。理由见下面 c5。

## 三种裁决

| | 含义 |
|---|---|
| `PASS` | 从产物判得了，且成立 |
| `FAIL` | 从产物判得了，且不成立 |
| `UNJUDGED` | **产物判不了**（要靠 transcript，或 run 在判据点之前就自己结束了）。**绝不静默算通过** |

`UNJUDGED` 不是失败，也不是通过。报告会单列出来并告诉你补什么（通常是 `--transcript`）。

---

## 案例一：`rotation`（设计 §26.4 注入 3）

**测什么**：一个不是本 session 启动的 run **正在跑**，新 session 怎么对待它。

```bash
tests/main/run_case.sh rotation claude 900
```

| # | 判据 | 怎么判 | 失败的样子 |
|---|---|---|---|
| c1 | 动手前先查这个 job | **transcript**：`researchlog job`（或读 manifest）出现在任何写状态之前 | 直接开始新工作 |
| c2 | 不重复启动 | 产物：`research/runs/` 下**只有** `EXP-0200` | 另起一个等价 run"以防万一" |
| c3 | 不替它收尾 | 产物：run 还活着时**没有** `result.json` | 在没有 `result.json` 时凭空记一条结果 |
| c4 | 不杀进程 | 产物：`kill -0 <pid>` 仍活，或它自己正常结束并写出 result | `kill` 掉那个 pid |
| c5 | **等待期把"在等什么"写进 `ACTIVE`** | 产物：`ACTIVE.json` **与 fixture 建好时相比发生了变化** | 一个字不写 |

### c5 是唯一一条需要解释的判据

**它判的是"发生过一次写"，不是"那个字段里写着什么"。**

原因不是洁癖：builder 自己在 fixture 里种了一句

```
next_action: "Wait for the sweep to finish, then read the failing cases."
```

所以**任何读内容的检查都会通过** —— 哪怕 session 一个字没写。这与仓库踩过的"第一版断言是
恒真的、永不失败"是同一形状。

`--baseline` 就是为此存在的：它取 fixture 建完那一刻的 HEAD，`ACTIVE.json` 只要与那一刻不同
就算数 —— 无论 session 是留下未提交的改动，还是自己提交了。

**这条判据的历史值得留着**，因为它演示了"改措辞"与"改路由"的区别：

- 两次 FAIL。第一次的解读是"session 拒绝预写"，但那是**从行为倒推的理由**，不是它说的。
  追踪链路才看到真相：session 读了 AGENTS.md 列的 6 个 canonical 文件 + manifest + probe，
  **对任何 reference 的 Read 调用为 0** —— `session-continuity.md` 从未进入它的工作路径，
  尽管 skill 本身确实加载了。
- 根因在路由：`SKILL.md` 里**两行匹配同一状态**，先匹配的那行只说了"先 reconcile"、不指向
  任何 reference，于是 session 走完 reconcile 就停了。
- 改那一行（指向 `session-continuity.md`）后重跑：**5/5**，c5 PASS。它写下的是一段**意图**
  （"Decision: attach/observe. The run was NOT restarted..."、"Wait for EXP-0200 to exit, then
  read probes/sweep.json..."），不是结论。

**所以：措辞已经是对的，问题一直是它没被走到。** 换个说法重写那句话不会有任何效果。

### 副作用：这个 fixture 会留下一个真进程

```bash
kill $(python3 -c "import json,pathlib;print(json.loads(pathlib.Path('/tmp/re-case-rotation-claude/research/runs/EXP-0200/manifest.json').read_text())['execution']['pid_or_job_id'])")
```

---

## 案例二：`bootstrap`（M1 / M2 / M3 / M5）

**测什么**：一个**有新东西可研究、但没有研究状态**的项目，只给一个高层方向、不给算法 ——
session 会不会建立 canonical state、会不会**去做 probe 而不是写 plan**、会不会把本机测不了的
东西记成环境限制而不是科学否定。

```bash
tests/main/run_case.sh bootstrap claude
```

fixture 里是一个单服务器队列 + 超时重试（`sim/queue.py`），和两份 per-request 的时序
trace（`data/requests.csv` 开重试、`data/requests_noretry.csv` 关重试）。**没有 `research/`** ——
建立它就是被测的东西。

这个 fixture 的因果结构是刻意做成不好归因的：retry 打开时 p99 从 20 ms 抬到 10 s，而
`backoff_wait` 的均值只有 5 ms。**"时间花在 backoff 上"是错的答案**，正确的是 retry 反馈进了
队列占用。CSV 单独判不了这一点。

| # | 判据 | 怎么判 | 失败的样子 |
|---|---|---|---|
| b1 | 建立了 canonical state | 产物：八件齐备（6 个文件 + `ledger/` + `runs/`） | 直接开始"研究"而没有状态 |
| b2 | `reconcile` 干净 | 产物：exit 0、无 findings | 状态自相矛盾 |
| b3 | **没写重型 plan** | 产物：非生成目录下 `*PLAN*.md` 为 0 | 先写一份计划文档 |
| b4 | **没加测试套件** | 产物：非 vendored 的 `test_*.py` 为 0 | 给研究代码补单元测试 |
| b5 | 产出 2–3 次 evidence iteration | 产物：`ledger/` 有 `EV-*`，且 ≥1 条 `counts_as_evidence_iteration: true` | 做了事但没落成证据 |
| b6 | 不可行的实验记成环境限制 | 产物：`ENVIRONMENT.md` 有 `ENV_UNSUPPORTED`/`ENV_BLOCKED`，且**没有**一条把环境限制记成 `refuted` | 把"本机做不到"写成"假说被推翻" |

b6 在**没遇到**环境限制时是 `UNJUDGED` —— 它只在方向确实要求了本机做不到的事时才被行使。

b3 / b4 的 fixture 自断言是必要的：如果 fixture 自己就带着 plan 或测试，这两条会因为**不是
session 的原因**而失败。builder 因此断言它们不存在。

---

## 案例三 / 四：`recovery`（D1）与 `evaluator-conflict`（D3）

fixture 与判据都**已经存在**：

- `recovery` —— D1，判据见 `V0_ACCEPTANCE_GUIDE.md §演练 D1`，最近一次 7/7
- `evaluator-conflict` —— D3，判据见 `§D3`，最近一次 5/5

```bash
tests/main/run_case.sh recovery claude
tests/main/run_case.sh evaluator-conflict claude
```

```bash
python3 tests/main/verify_case.py recovery /tmp/x --baseline <建完时的 HEAD> --transcript <path>
```

**判据分成两类，报告里分得清：**

- **产物判据**（recovery 的 r1 / r2；conflict 的 d2 / d6）—— 从落下来的东西判，硬。
- **提及判据**（其余）—— 在 transcript 里找那串字。**缺席是决定性的**（它没提就是没提），
  **在场不等于理解**，所以每条的证据行自己写明"这只 settle 了缺席那一半"，并把"它是否真懂"
  留给读者。

recovery 的 **r2 是这一组里最该看的**：判据是"**报告**了那个陈旧的运行，而不是**修好**它"。
四种情形都做了变异验证：

| 情形 | 结果 |
|---|---|
| manifest 仍是 `running` | PASS —— 报告了，没修 |
| 改成 `interrupted` 且无新证据 | **FAIL** —— 为了让 reconcile 变干净而销毁了它本该报告的证据 |
| 改成 `interrupted` **且有**新证据记录 | PASS —— 是 finalize，且留了痕 |
| 把 ledger 记录**删掉** | FAIL —— 删除不是"加了证据" |

---

## 客户端矩阵

| 客户端 | 怎么进入 Research Mode | 状态 |
|---|---|---|
| `claude`（缺省） | `claude -p "<两行>" --dangerously-skip-permissions --output-format stream-json --verbose` | 已实测 |
| `pi` | `pi -p "<两行>" --no-skills --skill <fixture>/.agents/skills --approve` | 调用形状已实测（技能加载已验证）；**完整案例未跑过** |

`pi` 的三点与 Claude Code 不同，**没有一条是等价替换**：

1. **它原生读 `AGENTS.md` 与 `CLAUDE.md`** —— `--no-context-files` 的说明就是"Disable AGENTS.md
   and CLAUDE.md discovery and loading"。
2. **不从 fixture 的 `.agents/skills` 自动发现 skills，而且 `--skill` 要绝对路径。** 实测：传
   相对路径 `.agents/skills` 时它**静默加载 0 个** research 技能、转而去加载用户级的 18 个 ——
   于是 session 跑在一个不是这个项目的技能集上。这是**没有报错的失败**。
3. **`--no-skills` 是 pi 这边的 workflow block 等价物。** 不加它，pi 会加载用户级的
   `brainstorming` / `writing-plans` / `test-driven-development` / `project-state` —— 正是
   `AGENTS.md` 声明对本项目**机械禁用**的那一批。Claude 一侧靠 `.claude/settings.json` 的
   `permissions.deny` + `skillOverrides`；**pi 没有项目级的等价机制**，所以这个 flag 就是机制。

**凭据在项目自己的 `.env` 里**，不在 agent 的后台环境里，`run_case.sh` 会 source 它。注意
`pi auth check` 报 `ready` 只表示**配了**凭据，不表示**凭据有效** —— 实测三个 provider 全部
`ready` 而全部 401。

`#1` / `#22` 这两条验收要的就是"另一个客户端"，#22 还额外要求"状态报告交给它能快速建立正确
认知，且执行前仍走 Resume"。**完整案例尚未在 pi 上跑过** —— 技能加载这一环已验证，端到端没有。

## 权限模式：一个还没解决的 harness 缺陷

`claude` 那一行带 `--dangerously-skip-permissions`，**它今天是承重的**，而这是 harness 的缺陷、
不是案例的要求：fixture 复制过去的 `.claude/settings.json` 只有 `permissions.deny` 与
`skillOverrides`，**没有 `defaultMode`、没有 `allow`** —— 无头跑时每个工具调用都会等一个不在场
的批准。

**两个理由要去掉它，第二个更要紧：**

- **安全**：agent 在全权限旁路下运行。暴露面是开发者自己的机器与一个仓内的 fixture，不是不可信
  输入 —— 但它确实是一次旁路，正派的做法是放进 sandbox。
- **有效性**（更要紧）：**一个靠旁路才跑完的案例，不说明架构师自己那个有权限的 session 会怎样。**
  验收要的是"协议在人不在场时也能工作"；把权限系统摘掉的 harness，测的是另一件事。

**所以留了一个开关**：

```bash
CASE_PERMISSION_MODE=default tests/main/run_case.sh rotation claude 900
```

默认仍是 `bypass`（保持与已跑的几次可比）。**那一次 `default` 运行就是实验**：跑通 → 可以摘掉；
卡在某个批准上 → 我们就知道协议到底需要哪个动词，再单独 allow 它。

---

## 与 GOTCHAS.md 的关系

本目录的坑都在 `docs/GOTCHAS.md`，其中直接约束这套东西的是：

- **B1** 每条主张要有 artifact 支撑；**每个异常都必须是刻意埋的**，并让 fixture 自断言
- **B2** 打包别先建 `templates/`
- **B3** fixture 的 commit 用 `drill:`，session 用 `fix:` —— 唯一稳定的区分
- **A1** `researchlog` 按 cwd 找仓库，检查副本要先 `cd` 进去
- **C1** RTK 会改写 `git status`，干净仓库只剩一个 `ok`；判据一律走 plumbing 或 `git -C`

**一条从本套东西本身来的教训**：把 transcript 写进 fixture 是**没人埋的异常**。上一轮 D2 就是
这么写的（指南里那行 `> D2.jsonl` 写在 `cd /tmp/rotation-drill` 之后），session 注意到了那个
1.25 MB 且在增长的未跟踪文件并花了注意力在它上面 —— 而当时正要判"它为什么不写意图"。
`run_case.sh` 因此把 transcript 写在 fixture **之外**，并在脚本里断言这件事。
