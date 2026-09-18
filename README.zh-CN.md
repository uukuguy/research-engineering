# Research Engineering（研究工程协议）

一份**协议**和一套小工具，让 **AI 编程 agent** 做**应用 AI 研究**——而不只是写代码。
整个设计围绕一个论点：**当你还不确定能不能跑起来时，唯一值得保留的东西是你做过的尝试留下的证据（evidence）**。

> English version: [README.md](README.md)

## 这个项目解决什么问题

大多数 AI 编程 agent（Claude Code、Codex、`pi` 等等）的设计目标是**软件交付**。它们的工作流默认：

- 系统已经能跑。
- 测试能抓回归。
- 「Done」= 测试通过。

应用 AI 研究正相反：

- 系统可能还不存在，或者数据还没拿到，或者评估器不可信。
- 「先拿最便宜的证据」比「全套测试覆盖」重要。
- 「Done」是一次**信念更新**——一个能经受证据检验的 finding——而不是绿灯的 CI。

如果你把一个面向交付的 agent 扔到一个研究问题上，它要么花几个小时搭脚手架、根本没验证机制到底有没有；要么悄悄优化错指标，因为评估器看起来在工作。**Research Engineering** 就是那层让 agent 留在**研究**模式而不是交付模式的薄壳。

## 它到底是什么

三件事，规模都不大：

| 组件 | 干什么 | 在哪 |
|---|---|---|
| **Skills** | agent 上下文里的指令：bootstrap 一个研究仓库、跑主循环、为架构师写状态汇报。 | `skills/`（canonical）— 通过 installer 复制到 `.claude/skills/` 和 `.agents/skills/` |
| **记账工具** | `researchlog` — 一个零依赖的 CLI，维护 `research/ACTIVE.json`（执行指针）、证据 ledger、和持久状态三者同步。 | `tools/researchlog/` |
| **Canonical 状态文件** | `research/ACTIVE.json`、`CURRENT.md`、`ARCHITECT.md`、`BOUNDARIES.md`、`ENVIRONMENT.md`、`FINDINGS.md`。每次 session 开始 agent 都读这些；它们就是一个项目的持久记忆。 | `research/` |

agent 本身选 hypothesis、跑实验、解读结果。工具**永远不**选 hypothesis、永远不决定保留还是回退、永远不调模型、永远不擅自修复状态——这些都需要科学判断，一个会凭空「发明」这些内容的工具就是在发明证据。

## 两种模式，一个边界

整个设计围绕一个区分：

| | Research Mode（默认） | Integration Mode（promotion 之后） |
|---|---|---|
| 目标 | 信息增益，验证过的行为 | 稳定、可复现的基线 |
| 代码 | 一次性，最小正确性 | 长期维护 |
| 测试 | 只测保护实验有效性的 | 选择性回归 |
| 全量回归 | 不跑 | promotion 时必须跑 |

模式是「阶段」不是项目属性。同一个仓库在 promotion 边界可以切换模式；agent 在被架构师 promote 之前一直待在 Research Mode。**知道自己在哪个模式里，是整个游戏的全部**。

## 协议一张图

```
研究问题 / 技术不确定性
        ↓
研究 Subject   idea / mechanism / component / slice / system
        ↓
证据获取   reasoning / probe / replay / spike / simulator / judge
        ↓
观察 → 信念更新 → 下一次干预
```

核心论点：**证据是稳定抽象**，不是「候选+评估器」。一个项目可能只有一段问题描述、一个 SDK、一点数据就开始了。系统必须能撑住这个起点。

## Layout

```
README.md / README.zh-CN.md   本文件（英文 + 中文镜像）
AGENTS.md                     AI agent 的 always-loaded contract
CLAUDE.md                    AGENTS.md 的一行 import（Claude Code 用）
skills/                       canonical skill 源（8 个 skill）
  research-bootstrap/         零状态初始化
  research-engineering/        主循环；持有 references/ 的路由表
  research-status/            给架构师读的 Project Working Model
  evaluation-design/          V1 专家 skill：评估器不可信时
  experiment-review/           V1 专家 skill：拿一次 run 对照活 hypothesis 复盘
  research-search/            V1 专家 skill：重新打开搜索空间
  retrospective/              V1 专家 skill：慢循环
  scenario-redteam/           V1 专家 skill：红队一个候选声明
tools/
  install_research_skills.py   把 skills/ 复制到 .claude/skills 和 .agents/skills
  check_workflow_block.py      任何交付工作流 skill 未被覆盖时退出码 1
  researchlog/                 零依赖记账工具（20 个子命令）
research/                     本仓库自己的活研究状态
templates/research/            `researchlog init` 复制到新项目的骨架
docs/
  WORK_LOG.md                  工具开发的日志（按日期追加，新会话从这里读起）
  GOTCHAS.md                   当前活跃的陷阱——作为**状态**而非日志保留
  V0_ACCEPTANCE_GUIDE.md       V0 验收条目 + 实测结果
  V1_ACCEPTANCE_GUIDE.md       V1 验收条目 + 实测结果
  V1_CASES.md                  V1 drill 套件：可执行命令 + PASS 信号
  RESEARCH_ENGINEERING_V1.5_REVIEW.html   设计评审与修订日志
```

## 在另一个仓库里用

```bash
git clone https://github.com/uukuguy/research-engineering
python3 tools/install_research_skills.py --target /path/to/project
cd /path/to/project && python3 tools/researchlog init
```

`install_research_skills.py --check` 比对 canonical skills 与已安装副本，发现 drift 时退出码非零。`git pull` 之后跑一下，捕获 skill 屏蔽漂移。

## `researchlog` 的能力

```bash
python3 tools/researchlog init          # 建研究状态骨架
python3 tools/researchlog validate      # schema + 不变量检查
python3 tools/researchlog reconcile     # ACTIVE ↔ Git ↔ runs ↔ evidence
python3 tools/researchlog record        # 追加一条证据记录
python3 tools/researchlog run           # 跑一次实验并捕获 provenance
python3 tools/researchlog compare       # 两条 EV 之间的共有测量 + attribution
python3 tools/researchlog env           # 记录 / 查询环境变更
python3 tools/researchlog findings      # 持久信念（Established / Provisional / ...）
python3 tools/researchlog synthesize     # block 收尾时 1-2 页综合（给架构师看）
python3 tools/researchlog telemetry      # §21 productivity KPI 表
python3 tools/researchlog checkpoint     # 可恢复的 Git checkpoint
python3 tools/researchlog current        # 读 / 改 research:current block
python3 tools/researchlog boundaries     # 读 / 改 research:boundaries block
python3 tools/researchlog active         # rotate session、开关 block、设状态
```

每个子命令都返回 JSON envelope（`exit_code`、`findings`、`payload`），agent 看数字分支，永不解析散文。输出确定性——同样输入同样输出，答案不含 wall-clock 漂移。

## 核心不变量（它**不**做的事）

1. **证据是稳定抽象**，不是「候选+评估器」。别假设系统能跑、评估器可信。
2. **环境不可行 ≠ 假说被否**。`INFRA_FAILED`、`ENV_BLOCKED`、`ENV_UNSUPPORTED`、
   `RESOURCE_EXCEEDED` 跟 `research_outcome` 分开；只有 `SCIENTIFIC_NEGATIVE` 才能
   削弱 hypothesis。
3. **用 surrogate 前先验证它**。因果特征缺失 = `EVIDENCE_INVALID`，不是更弱的结论。
4. **原始证据只追加**。信念和当前状态可以重建；聊天上下文不是 source of truth。
5. **session 上下文是一次性的**。跟决策相关的所有东西都住在仓库里。

## 状态

**V1 工具层已于 2026-09-19 收口**。drill 套件 8/9 完成；剩 1/9（V1-D9、M6/M7 claude-pending）
在本沙箱使用的 minimax-compat endpoint 下是 `ENV_BLOCKED`——要等原生 Anthropic 订阅
上线才能解决。汇总：**45 PASS + 0 deferred + 4 ENV_BLOCKED**，共 49 个 criterion。
`tools/researchlog/tests/` 下 304 个测试全部通过。

三个文件承载工作的真实状态：

- **`docs/WORK_LOG.md`** — 先读这个。按日期追加的工具开发日志：做了什么、未完成、
  下一步做什么。
- `docs/V1_ACCEPTANCE_GUIDE.md` — V1 验收条目、drill 协议、实测结果。
- `docs/V1_CASES.md` — V1 drill 套件：可执行命令 + PASS 信号。
- `docs/GOTCHAS.md` — 当前活跃的陷阱，作为**状态**而非日志保留：修好的删掉，
  不留注释。

本仓库自己的 `research/ACTIVE.json` 是 **idle**——V1 工具层收口是**已交付**的东西，
不是正在跑的研究。新研究活动要等架构师的决策：扩 telemetry、切原生 Anthropic
端点、或给一个新 hypothesis。

## 兼容性

- **Python 3.12+**（见 `.python-version`）。
- **Claude Code**（默认）、**Codex**、**`pi`** — 协议不绑定某个 agent。installer 把
  skills 复制到 `.claude/skills/` 和 `.agents/skills/`；`pi` 原生读本文件。
- **单进程、单机**。无调度器、无服务端、无多租户状态。一个研究仓库、一个 agent
  循环、一份磁盘上的持久状态。

## 测试

```bash
PYTHONPATH=tools python3 -m unittest discover -t tools -s tools/researchlog/tests -v
```

304 个测试，无网络、无模型调用。运行时间约 30 秒。

## License

内部研究项目。设计谱系见 `docs/`。