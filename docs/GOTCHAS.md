# 动手前必须知道 —— 当前有效的坑

**这是状态，不是日志。** 修好的坑**直接删掉或改写**，不要追加一句"已修" —— 那份记录属于
`docs/WORK_LOG.md`（带日期、只追加，所以一条过期的条目看起来就是旧的）。

本文件回答的是另一个问题：**现在还有哪些坑**。两者为什么要分开：一条只追加的日志**无法**回答
"现在还剩几条有效"，而坑是**当前为真**的东西 —— 它过期时不会像日期那样自己显形，只会散落在
历史里。

**来源**：`WORK_LOG.md` 各轮的"动手前必须知道"（12 条）、本机 agent memory（5 条新增）、以及
`WORK_LOG.md` 正文里以散文形式记录的两条（B5 / A2，已标注）。

**新增一条的流程**：先写进**当轮**的 WORK_LOG entry（它属于"那一轮发生了什么"），再在这里落成
一条**当前为真**的条目。

---

## A. 状态与 `researchlog`

### A1. `researchlog` 按 cwd 向上找 `research/`，不看脚本路径

检查一个**副本**（例如演练 repo 里的 `tools/researchlog`）时必须先 `cd` 进去，否则它会去检查你
**当前所在**的仓库 —— 而且很可能报 clean，于是你得到一个**关于错误对象的"通过"**。踩过，
误读了一次演练结果。

### A2. 副本既是代码的副本，也是代码版本的副本

用 `/tmp/eval-conflict` 里那份**约束修复之前**建的 `tools/researchlog` 副本去验证"拒绝信息"，
它照常写入 —— 差点得出"修没生效"的错误结论。**验证副本前先确认副本是新的。**

### A3. "没有动词的状态，也没有校验"

见到一个 canonical 文件或块时问两句：**谁写它？谁读它？** 两个都答不出来的，就是下一个缺口
（`research:current`、`ENVIRONMENT.md` 的三张表都是这么找到的）。审计方法：

```bash
grep -rn "paths\.<name>" tools/researchlog/ --include="*.py"    # 零引用即未接线
```

### A4. `environ` 快照是 `changed` 谓词的前提

`researchlog record` 会从 `ENVIRONMENT.md` 的 `history` 折叠出当前环境状态写进证据。证据里没有
这个快照时，`changed` 谓词**永远只能是 `UNRESOLVED`**。

---

## B. 演练 fixture

### B1. 两条铁律，并且让 fixture 自断言

每条主张都要有 artifact 支撑；**每个异常都必须是刻意埋的**（工作区文件在捕获身份**之前**就位、
探测桩只打印不写工作区、可调参数走**声明的 input** 而不是工作区文件）。再让 fixture **自断言**
这两条 —— 否则它们会悄悄腐烂。

### B2. fixture 打包别先建 `templates/`

`mkdir -p templates && cp -R src/templates templates` 会得到 `templates/templates/research`，
`init` 报 `TEMPLATES_ABSENT` —— 那是**打包错误不是工具缺陷**，但会让 session 花时间去修 fixture。

### B3. fixture 的 commit 用 `drill:` 前缀，session 用 `fix:`

这是两者**唯一稳定**的区分。作者字段分不出来，因为 builder 把 `git config user.email` 写进了
fixture。

### B4. 改共享底座后，三个 drill builder 全部重跑

它们是这套状态**最真实的使用者**，比单元测试更早暴露接线缺口（D1 的 fixture 就是被不变量 #4
的接线打坏的）。

### B5. 测量点错了就改测量点，不改判据

判据本身无歧义时（M1），问题可能只是"测量该取在哪一刻"。此时要改的是**测量点**。

### B6. 判据要判"发生过什么"，不要判"字段里写着什么"

rotation fixture 的 builder 自己在 `next_action` 里种了一句 "Wait for the sweep to finish,
then read the failing cases." —— 于是**任何读内容的检查都会判通过，哪怕 session 一个字没写**。
这与"第一版断言是恒真的、永不失败"是同一形状。

正确做法是拿 fixture **建完那一刻的 commit** 做基线（`run_case.sh` 的 `--baseline`），判
"它相对那一刻变了没有" —— 无论 session 留的是未提交改动还是自己提交了。

### B11. 写检查器时最大的缺陷类：**检查的东西与标签声称的相邻**

一轮里出现 **8 次**，全部同一形状 —— 不是"检查写错了"，而是**检查报的是与它声称相邻的另一件事**。
所以它**看起来在工作**，只是答的不是那个问题：

| 检查器 | 声称 | 实际在查 |
|---|---|---|
| `tool_digest` | 工具没被改 | 含 `__pycache__` → 跑过工具就报"改了" |
| `c5` | 等待期写了**意图** | 文件变没变 → 收尾簿记也算 |
| `b5` | 2–3 次 evidence iteration | 只要 ≥1 条 counted |
| `c1` | 先查了 job | 只认字面命令，不认"读 manifest"（判据两种都收） |
| `d2` | 没有采纳那个错计划 | 只读 `next_action`，嘴上拒绝的无法通过 |
| `--json` | 机器可解析 | 后面跟了一行人读的句子 |
| `git diff` | 新增了什么 | **看不见未跟踪文件** |
| `--porcelain` | 加了什么 | **删除也算变化** → 删 ledger 读成追加 |

**两个可操作的检查**（写任何判据/断言时问自己）：

1. **标签与代码对得上吗？** 把 label 和它下面那几行并排读一遍。`b5` 和 `c1` 都是这么发现的 ——
   标签是从判据抄的，代码是另一套更窄的逻辑。
2. **失败消息描述的检查，代码真的做了吗？** `c1` 的消息写着"never calls `researchlog job` **or
   reads the manifest**"，而代码只查前者。**一条比它的消息更窄的检查**，是一条会冤枉人的检查。

**反向也成立**：`--porcelain` 那条是**比声称更宽** —— 把删除算成新增。两个方向都会骗人。

### B10. "还没发生"不是"不可能发生"

踩过：看到 `research/runs/` 是空的、记录全是 `E0`，就下结论"这个 fixture 让 M3 **不可能**发生"——
并据此改了 fixture。**下一拍它就在那个 fixture 上产出了一次 `counts: true` 的迭代**，改动因此回退。

**快照不是判决。** 一个"什么都还没做"的中间态，和一个"做不了"的结构性结论，**看起来一样**。要
区分它们，唯一可靠的办法是**给它时间**（并且用直接测量看它有没有在动，见 C8）。

同一轮里这个错误出现了两次，两次外衣不同 ——
一次判**进程**（"两个运行都已结束"），一次判**能力**（"M3 不可能发生"）。

### B9. `git diff` 看不见未跟踪文件，而"新增"几乎总是未跟踪的

同一个检查器里踩了两次：`git diff <baseline> -- research/ledger` 对**新建**的证据记录**什么都不
报**。改用 `git status --porcelain`（`??` 即未跟踪）。

**但还有第二半**：`--porcelain` 的输出里**删除**也是变化（` D`），所以"有任何变化"不等于"加了
东西" —— 把删除当成新增，会让一个**删掉 ledger** 的 session 读起来像是一个**追加**了证据的。
要按状态码筛：只有含 `?` 或 `A` 的才算新增。

### B7. 自断言的 glob 要排除 vendored 目录

`rglob("test_*.py")` 会把 `tools/researchlog/tests/` 一起算进去，于是"session 有没有加测试套件"
这条断言因为**工具自带的测试**而永远失败。凡是按文件名 glob 的自断言，都要先排掉
`tools/` / `.claude/` / `.agents/`。

### B8. 台账污染会让判据的结论无法归因

把 transcript 写进 fixture（`> D2.jsonl`）就是**没人埋的异常** —— session 会注意到那个不断增长
的未跟踪文件并分心，而当时正要判"它为什么不写意图"。**判据红了以后，你分不清是协议的问题还是
你的垃圾文件的问题**，只能重跑。`run_case.sh` 因此把 transcript 写在 fixture 之外并断言这件事。

---

## C. 本机环境

### C1. RTK 改写 Bash 输出：干净仓库的 `git status` 只剩一个 `ok`

`rtk hook claude` 是**用户全局** `~/.claude/settings.json` 里的 `PreToolUse` hook，把
`git status` 之类改写成 `rtk git status`。后果：干净仓库的 `git status --porcelain` / `--short`
**不产出任何真实输出**。`python3 ... --json` 不受影响（rtk 只改写它认识的命令）。

对**演练**尤其重要：这是**没人埋的异常**，会消耗 session 的注意力 —— 与 B1 直接冲突。应对写在
`~/.claude/RTK.md`（`rtk proxy <cmd>` 走原始输出）。**别去查 git** —— D2 是用 `GIT_TRACE` 加
plumbing 交叉验证才把它澄清的。

### C2. `origin` 走 HTTPS 连不上，改用 SSH

症状 `Failed to connect to github.com port 443 after 75003 ms` —— **看起来像断网、其实不是**
（同一时刻 `ping github.com` 通、`https://api.github.com` 返回 200，只有 `github.com` 解析到的
那台 IP 连不上）。`origin` 是 HTTPS URL，所以 `git push` 会卡 75 秒再失败。

`~/.ssh/id_rsa` 属于 `idleuncle`，**对 uukuguy 的仓库没有权限**，必须显式指定属主那把 key：

```bash
GIT_SSH_COMMAND="ssh -i ~/.ssh/id_rsa_uukuguy -o IdentitiesOnly=yes" \
  git push git@github.com:uukuguy/research-engineering.git main
```

**连带后果**：推到**显式 URL** 不会更新 `origin/main` 这个 remote-tracking ref，于是
`git status -sb` 会报"领先 N 个"，而真实远端可能早已同步。核实真实远端要直接问：

```bash
GIT_SSH_COMMAND="ssh -i ~/.ssh/id_rsa_uukuguy -o IdentitiesOnly=yes" \
  git ls-remote git@github.com:uukuguy/research-engineering.git main
```

**第二个连带后果：`--force-with-lease` 会失败，报 `stale info`。** 它的"lease"就是 `origin/main`
那个陈旧 ref，所以它比的是一个没人更新过的值。要强制推就得**显式给出期望值**：

```bash
R=$(GIT_SSH_COMMAND="ssh -i ~/.ssh/id_rsa_uukuguy -o IdentitiesOnly=yes" \
      git ls-remote git@github.com:uukuguy/research-engineering.git main | cut -f1)
git push --force-with-lease="main:$R" git@github.com:uukuguy/research-engineering.git main
```

这条比裸 `--force` 安全，又比 `--force-with-lease` 能用 —— 它仍然会挡住"远端在我查看之后又变了"
的情况，只是那个"我查看过"的值来自 `ls-remote` 而不是那个从不更新的 ref。

根治办法是把 `origin` 换成 SSH URL，但那属于改架构师的仓库配置。

### C3. 跑测试必须 `uv run`，且必须带 `-t tools`

`.python-version` 是 3.12，但 PATH 上的 `python3` 是 3.14；`-t tools` 缺了则 `researchlog`
不可导入。

```bash
uv run --python 3.12 python -m unittest discover -t tools -s tools/researchlog/tests
```

### C4. Pyright 的 import 报错是假的

它满屏报 `"X" is unknown import symbol`，因为它不知道 `-t tools` 把 `tools` 放进了 `sys.path`。
判据永远是"**Python 能不能跑通**"，不是 IDE 报什么。

### C5. `.claude/skills/` 与 `.agents/skills/` 是生成物

永远改 `skills/`，然后 `python3 tools/install_research_skills.py --self`；`--check` 会 diff
canonical vs installed，并在漂移时非零退出。

### C9. **别对你读判决的那条检查加 `>/dev/null 2>&1`** —— 以及 zsh 不做词分割

踩过：用 `for g in "tools/researchlog validate"; do python3 $g >/dev/null 2>&1; echo "exit=$?"; done`
跑门禁，得到 **exit=2**，据此宣布"validate 回归了"。**实际四道门禁全是 exit 0。**

两层原因，都在我这边：

1. **zsh 不对未加引号的参数做词分割。** `$g` = `"tools/researchlog validate"` 被当成**一个**含空格
   的参数，于是 python 去找一个叫 `tools/researchlog validate` 的文件 —— 找不到，exit 2。
   （bash 会分割，zsh 不会。本环境的 shell 是 zsh。）
2. **`>/dev/null 2>&1` 把唯一能说明问题的那行扔了**：`can't open file '… validate': [Errno 2]`。
   看见它，一秒就定位；看不见它，我去查了一个不存在的回归。

**规则**：**你准备据以下结论的那条检查，不要静音它的输出**。静音只适合"你只关心它成不成功、且
失败时你会另外去看日志"的场景 —— 而"我要读 exit code"恰恰不是那种场景。

这是 B11 那一族的又一例：**"门禁的退出码"与"python 找不到文件的退出码"是两件事**，而我读了后者
当场判前者。

**同一分钟内还踩了它的另一半**：`python3 … validate | head -1; echo "exit=$?"` —— **`$?` 是 `head`
的退出码，不是工具的**。管道里 `$?` 取的是**最后一个**命令。要取前面那个，用 `${PIPESTATUS[0]}`
（bash）或**干脆别接管道**：

```bash
python3 tools/researchlog validate >/dev/null 2>&1; echo "exit=$?"   # 正确
python3 tools/researchlog validate | head -1; echo "exit=$?"          # 读的是 head 的
```

所以这条完整是两半：**别静音你读判决的检查**；**别让管道替你决定那个退出码是谁的**。
两半合起来是一件事 —— **确认你读的那个数字，确实是你要的那个东西的数字。**

### C8. 判一个**别人正在跑**的任务，用 PID + artifact 双信号，别用一次 `ps`

踩过：两次 `ps | grep` 返回空（模式太窄、外加我自己 `head` 截断），据此宣布"两个运行都已结束"，
并**判了一个还在飞的 fixture**。而当时**第二个信号就在手上** —— 我打印过 transcript 的大小，却
没有回头再测一次；它 7 分钟里从 708 KB 长到 2.89 MB。

这正是 CLAUDE.md §3 那条 HARD RULE 说的场景，而我用了单一信号。**观察别人的长任务时**同样适用：

```bash
# 进程存亡
ps -eo pid,etime,command | grep -F "<fixture 路径或 run_case>"     # 按路径找，别按进程名猜
# artifact 是否在动 —— 这才是决定性的那个
f=<transcript 或日志>; a=$(wc -c <"$f"); sleep 15; b=$(wc -c <"$f"); echo "$a -> $b"
```

**正在长的 artifact 就是"还活着"**，比任何一次 `ps` 都可靠。反过来，`ps` 空**不构成**结论 ——
它可能只是被过滤、被截断，或模式写窄了。

**别用代理信号代替直接测量。** 同一轮里还错了一次：从**某次 dump 里最后一个事件的时间戳**推断
"pi 已静默 10 分钟"，而那个文件的 **mtime 是 1 秒前**。事件时间戳、日志末行、`ls` 的直觉 —— 都是
代理。**`stat -f %Sm` 和 `wc -c` 是直接测量，各一条命令的距离**，没有理由用代理。

### C7. 新的凭据文件出现时，先 `git check-ignore` 再 `git add -A`

项目本地 `.env` 曾被漏在 `.gitignore` 之外，而提交流程用 `git add -A` —— 下一步就会把密钥提交
并推上去。新出现任何凭据文件时，**先 `git check-ignore -v <file>`**，别等 `git status` 里那个
`??` 变成一条已推送的历史。

### C6. `.gitignore` 的模式必须锚定

用 `/runs/` 而非 `runs/`。未锚定的模式匹配任意深度，会连 `research/runs/**` 一起吞掉 —— 而
`manifest.json` 是**必须入库**的 provenance，且 Git **无法重新包含被排除目录内的文件**，
negation 救不回来。

---

## D. Claude Code 的 workflow block

### D1. `permissions.deny` 与 `skillOverrides` 都不支持通配

前者管 plugin 命名空间、后者管 personal 级 skill，都要**一个 skill 一个精确名字**。
`Skill(gsd-*)` 匹配不到任何东西 —— **实测过**：在只 deny 这个模式的 settings 下调用
`gsd-plan-phase`，它照样加载。而且 denied 名字里的 **plugin 是版本目录上面那一层，不是
marketplace 目录**（`omc` marketplace 下的 plugin 叫 `oh-my-claudecode`）。

### D2. 缓存里的 plugin ≠ 可用的 plugin

只有 `enabledPlugins` 里为真的才可达。把 plugin cache 当成可用集合，会**同时**报出不需要的屏蔽、
并把真正的缺口挡在后面看不见。

### D3. 漂移检查要跑

```bash
python3 tools/check_workflow_block.py    # exit 1 点名每个未覆盖的交付工作流
```

一份清单不会注意到机器长大了。它同时**反向**检查：`AGENTS.md` 明文保留可用的
`systematic-debugging` / `using-git-worktrees` 若被误关，同样 exit 1。

### D4. `pi` 的 `--skill` 要绝对路径，而 `--no-skills` 是它的 workflow block 等价物

三点，**没有一条是等价替换**：

1. `pi` **原生读 `AGENTS.md` 与 `CLAUDE.md`**（`--no-context-files` 的说明即是）。
2. **不从 `.agents/skills` 自动发现，且 `--skill` 要绝对路径。** 传相对路径时它**静默加载 0 个**
   项目技能、转而加载用户级的 —— 于是 session 跑在一个不是这个项目的技能集上。**没有报错。**
3. **不加 `--no-skills`，pi 会加载用户级的 `brainstorming` / `writing-plans` /
   `test-driven-development` / `project-state`** —— 正是 `AGENTS.md` 声明对本项目机械禁用的那批。
   Claude 一侧靠 `.claude/settings.json`；**pi 没有项目级等价机制**，所以这个 flag 就是机制。

凭据在项目自己的 `.env` 里，不在 agent 后台环境里。**`pi auth check` 报 `ready` 只表示"配了"，
不表示"有效"** —— 实测三个 provider 全部 ready、全部 401。

---

## E. Git 与提交

### E1. commit message 里的反引号是命令替换

`git commit -m "…\`code_state\`…"` 会把反引号当命令执行，输出为空，于是那个词**从消息里静默
消失** —— 提交成功、消息残缺、**不报错**。丢过 `code_state` 与 `SELF_REFERENTIAL_COMMIT`
两个词。

**永远把消息写进文件再 `git commit -F`**，不要用 `-m` 传含反引号 / `$` / `!` 的文本。

### E2. 跑全量测试前必须先问架构师

哪怕改动落在共享底座上。先跑覆盖改动模块的定向测试并报告。
