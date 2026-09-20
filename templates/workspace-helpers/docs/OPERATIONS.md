# ESA Study — 操作手册 (RE workspace 通用)

本 README 是 workspace operator 启动 / 监控 / 调控 RE 工作 session 的
操作锚点,具体项目无关。覆盖:

- **快速启动** (新 session 几行起活)
- **实时观察** (operator 不参与 session,但能看 progress)
- **退入 / 重启** (session 关闭后不掉状态)
- **信号机制** (operator 想要打断 / 改方向怎么投)

> 该 cwd 的具体研究对象(ESA etc.)由 `references.json` 登记;
> 该 cwd 的具体 active block + iteration count 由 `.research/ACTIVE.json`
> 决定;operator 看到的是该 cwd 自身的 state。

## 0. cwd 状态速读

```bash
make state                # ACTIVE + ledger count + reference count
make ledger               # newest EV landing, top 10
make ledger-details       # dump first 20 lines of each recent EV
make references           # registered external targets (JSON)
make telemetry            # 5 KPIs
make reconcile            # one-shot reconcile check

# Original CLI 也可调(若需要特定 sub-flag):
PYTHONPATH=<protocol-tools> python3 -m researchlog active --show
```

## 1. 启动 session

新 tab 跑:

```bash
make session-spawn         # claude --model fable --bare in cwd
make session-spawn-codex   # codex in cwd
```

session 内 prompt 给 AI:

> "读 `.research/` + 跑 RE 协议 loop。从 `AGENTS.md` 起:本 cwd 的
> `.research/` 是 state 仓库;`references.json` 列出哪些 read-mostly
> 外部路径;`ARCHITECT.md` 列出当前 operator signals;当前 block 由
> `ACTIVE.json` 告知(open or closed)。"

AI session 自己读 `research-engineering` 主 skill + 它的 8 个专家 skill。

**注**:`make install-global` 没启用前(实际正式发布版前不装 global),
各 session 没法从 `~/.claude/skills/` 读 RE skill,只能从 cwd `.claude/skills/`
读。本 cwd 没装 skill 到 `.claude/skills/`,所以本 cwd 启动 session 后
**不会自动**应用 research-engineering skill —— 但 cwd 里有 `AGENTS.md` +
本 README + `Makefile`,AI 可以从文件层读。

**实操提醒**:本 cwd 是为 RE protocol 准备的 state 仓库,它的 `AGENTS.md`
明确 RE 协议 boundary,AI session 自然接受 `AGENTS.md` 优先于 `SKILL.md` 的
trigger-description。本会话架构(RE 协议本体 + RE workspace)以 `AGENTS.md`
为入口,与 `SKILL.md` 的 trigger-description 互不干扰。

要切换到全局 skill 装(已经过 stable 的话):

```bash
make install-global   # 但这是协议本体的 PR 该工作的,cwd 不该主动装
```

`make install-local` 装到 cwd 本地 `.claude/skills/`:

```bash
make install-local
```

## 2. 实时观察 (operator 不打断 session)

新 tab(独立于 session tab)实时 tail:

```bash
make watch            # 5 s loop of `state`,等价 `watch -n 5 state`
make ledger           # 单次看,top-10 EV
make references       # 单次看 references
```

更直观的:operator 一边跑 `git log --oneline` 在 cwd 看每条 commit
是 EV 落点 + commit message:

```bash
cd <cwd> && git log --oneline --abbrev-commit -10
```

每条 EV 的落盘形式:

  commit <hash1>: 自动由 `researchlog record` P1 触发
  commit <hash2>: operator 或 AI 自己 `git commit`(audit finding 之类)

## 3. 投 Operator Signal

如果 operator 想打断 session 改方向,**不要** 直接 Edit chat — 在
cwd 写 `ARCHITECT.md` (semantic signal):

```bash
# 例子: 想要暂停 ESA H1 + restart
cat >> .research/ARCHITECT.md << 'SIG'

```json research:signal
{
  "id": "D-NNN",
  "type": "DIRECTION",
  "statement": "ESA H1 暂停;先 close RB-XYZ 然后开 RB-NNN 接续",
  "scope": "next_research_block",
  "expiry": "after_3_evidence_iterations"
}
```
SIG
```

下次 AI session resume (`make state` 看到 `reconcile` 会校验
`ARCHITECT.md` 有过期 signal),会看到 D-NNN 自动 apply。

## 4. Session 退入 / 重启

session 退(operator 关掉 claude tab 或 exit):

- `.research/` 内 state、git working tree、`sessions.jsonl` 都 **保留**
  (everything on disk,no in-memory state)
- ACTIVE.json 仍 idle (上次 close-block belief_delta=none)

下次 session 重启(新 tab 或 reset 后 start):

```bash
make session-spawn
# prompt: "读 .research/ACTIVE.json + cwd;从哪里继续?"
```

AI 自己 derive:
  - 当前 block id (open / closed)
  - ledger last EV 与 observation
  - 已知 open QUESTIONS / HYPOTHESES
  - session epoch 是新派的(若 sessions.jsonl 是上条 "started" 之后无 active
    session,"rotated" 触发新 epoch)

## 5. KPI 监测

5 个 KPI 在 `make telemetry`:

```
cumulative_evidence_iterations       累计做了多少次 hypothesis-changing iteration
time_to_first_e1                    第一个 E1 出现时间
time_to_first_e3                    第一个 E3 出现时间
session_recovery_accuracy            session rotation 后能不能正确 derive 上次工作
discriminating_experiment_without_architect_correction
                                    不靠 Architect 打断的区辨性实验比例
```

前 3 个有数据(随实验进行实时涨);后 2 个要 ARCHITECT signal 真的被消费
后才算。

## 6. 协调(本研究域 cwd 与协议本体)

本 cwd 是 RE workspace;RE 协议本体在
`<protocol-source>`(具体路径看 `make help` 输出)。

AI session 需要协议层改动 / bug fix / 加 verb / 改 schema 时:

  - AI **不写** 本 cwd 内的 researchlog 协议代码 (协议代码位于
    `<protocol-source>/tools/`)
  - AI 实装完成后跑 `make install-global` (该路径未启用前) 或者
    cwd 上 `make install-local` 装本地副本

但 AI session 仍可**调用** 本 cwd `researchlog` 命令(probe / list /
read),那些调用不会污染协议本体。

## 7. 已知边界 / 哪些不能做

- **不可改主仓**: 主仓 git 不被本 cwd 写入。如需改主仓,recipe 走主仓
  own governance(不在本协议范围)。
- **不可搬大文件主仓 data**: cwd 不复制主仓 data,绝对路径 read,
  AI session 自身的产物落 `.research/runs/EXP-*/`。

如要扩展到主仓真正 M20 仿真器管道 / 跑 BL / 接 GPU 工作流:
迁云 Linux x86 主机后用主仓的 `Makefile.gpu`(`Makefile.gpu`)。本 cwd 不动。

## 8. cross-ref

- RE 协议本体: `<protocol-source>`(用 `make help` 找到路径)
- 主仓(read-mostly): `references.json` 列出的 path
- 锚点文档与决定: `<protocol-source>/docs/architecture-decisions/`
- V0/V1 验收指南: `<protocol-source>/docs/{V0,V1}_ACCEPTANCE_GUIDE.md`
- 本 cwd 自身 git history: `git log` from cwd
