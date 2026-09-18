# research-engineering（研究工程协议）

> 一套面向 AI agent 做**应用 AI 研究**的开源协议与工具集 —— 系统还不存在、
> 评估器可能错、"完成"是信念更新而非 CI 全绿。

[![status](https://img.shields.io/badge/V1%20tool%20layer-已收口-green)](#状态)
[![tests](https://img.shields.io/badge/测试-304%20全过-brightgreen)](#状态)
[![drill](https://img.shields.io/badge/drill%20套件-8%2F9-blue)](#状态)
[![python](https://img.shields.io/badge/python-3.12%2B-blue)](#状态)
[![license](https://img.shields.io/badge/license-MIT-blue)](#协议)

[English](README.md) · [中文](README.zh-CN.md)

---

## 这是什么

大多数 AI 编程 agent（Claude Code、Codex、pi 等）的设计目标是**交付软件**。
它们默认系统能跑、测试能抓回归、"完成"= build 全绿。

应用 AI 研究把以上每条假设都打破：系统可能还不存在；评估器可能是错的；
数据可能还没拿到。"先拿最便宜的证据"压倒"全套测试覆盖"；"完成"是**经得起
证据检验的 finding**，不是绿灯的 CI。

`research-engineering` 是那层让 AI agent 留在**研究**而非**交付**模式上的薄壳。
它给 agent 一份持久状态协议、一个确定性记账工具、和一组小巧的 skill——
足够把"试了什么、学会了什么、下一步做什么"跨 session 边界地记下来。

它**不**替 agent 选 hypothesis、不替 agent 决定保留还是回退、不调用模型、
不擅自修复状态。这些都需要科学判断——一个会凭空发明这些内容的工具，
就是在发明证据。

---

## 为什么存在

把面向交付的 agent 扔到研究问题上，反复出现三种失败模式：

1. **脚手架陷阱**。Agent 搭出干净的仓库骨架、把所有类型填齐、build 全绿——
   根本没去验证机制到底有没有成立，因为没人信任评估器、也没记录任何证据。
2. **指标博弈**。评估器看起来在工作，agent 就去优化它。数字往上走。
   没人去查下面的因果声明是不是还成立。
3. **信念失忆**。每个新 session 都从空白聊天开始。Agent 重新推导上周学到了
   什么、推翻上一个 hypothesis、把已经做过的工作再做一遍。

`research-engineering` 的存在理由是：这三种全是**状态问题**。修法是
**持久的、只追加的证据**——能跨 session 边界活下来——加上一个
**研究 / 集成模式区分**，让 agent 不会把没验证过的 hypothesis 当成已交付功能。

---

## 快速开始

```bash
# 1. clone（或把 tools/ 和 skills/ 拷到你自己的仓库里）
git clone https://github.com/uukuguy/research-engineering
cd research-engineering

# 2. 把 skill 装到你 agent 的发现目录
python3 tools/install_research_skills.py --target /path/to/your-project

# 3. 初始化一个研究仓库（创建 research/ACTIVE.json + 骨架）
cd /path/to/your-project
python3 /path/to/research-engineering/tools/researchlog init

# 4. 跑一次自检（验证 schema、状态、git 一致性）
python3 tools/researchlog reconcile

# 5. 记第一条证据
python3 tools/researchlog record \
    --question "机制成立吗？" \
    --subject-type mechanism --subject-id M-001 \
    --level E1 --execution-status completed \
    --research-outcome inconclusive --belief-delta none \
    --confidence low \
    --observation "第一次观察" --no-experiment
```

完事。仓库里现在有第一条证据，ACTIVE.json 已更新，下一个 session
能从持久状态接续——不需要聊天上下文。

---

## 它怎么工作

### 研究 vs. 集成模式

整个设计围绕一个区分：

|                    | **研究模式**（默认）                | **集成模式**（promotion 之后）        |
| ------------------ | ------------------------------------- | -------------------------------------- |
| 目标               | 信息增益、验证过的行为               | 稳定、可复现的基线                     |
| 代码               | 一次性，最小正确性                    | 长期维护，stable 接口                   |
| 测试               | 只测保护实验有效性的                  | 选择性回归                              |
| 全量回归           | 不跑                                  | promotion 时必跑                        |
| Promotion 判据     | 一个 finding 经得起证据检验           | 架构师 review                            |

模式是**阶段**，不是项目属性。同一个仓库在 promotion 边界切换模式；
agent 在被架构师 promote 之前一直待在研究模式。**知道自己在哪个模式里，
是整个游戏的全部**。

### 协议

```
   研究问题 / 技术不确定性
                   │
                   ▼
           研究 Subject
   (idea / mechanism / component / slice / system)
                   │
                   ▼
           证据获取
   (reasoning / probe / replay / spike / simulator / judge)
                   │
                   ▼
       观察 → 信念更新 → 下一次干预
```

核心不变量：**证据是稳定抽象**，不是「候选+评估器」。一个项目可能只有
一段问题描述、一个 SDK、一点数据就开始了——系统必须能撑住这个起点。

### 架构

```
┌─────────────────────────────────────────────────────────────┐
│  Agent loop (Claude Code · Codex · pi)                       │
│  每次 session 开始读 AGENTS.md                                │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   ┌─────────┐         ┌─────────┐         ┌──────────────┐
   │ Skills  │         │  tools/ │         │   research/  │
   │  (8)    │         │research │         │ ACTIVE.json  │
   │         │         │   log   │         │ CURRENT.md   │
   │  路由表  │         │         │         │ ARCHITECT.md │
   │         │         │ 20 个子 │         │ FINDINGS.md  │
   │         │         │ 命令    │         │ ledger/      │
   │         │         │         │         │ runs/        │
   └─────────┘         └─────────┘         └──────────────┘
```

**Skills**（8 个）住在 `skills/`，由 installer 复制到 `.claude/skills/`
和 `.agents/skills/`。主路由根据观察决定加载哪个 skill——不是 agent
自己偏好决定。

**`tools/researchlog`** 是一个零依赖的 Python CLI。每个子命令返回
JSON envelope——agent 看 `exit_code` 分支，读 `findings`，永不解析散文。
同样输入同样输出，答案不含 wall-clock 漂移。

**`research/`** 承载持久状态。Agent 在每次 session 开始读它，把它当成
唯一的 source of truth——按设计，聊天上下文是一次性的。

---

## 命令

最常用的 `researchlog` 子命令：

```bash
researchlog init            # 建研究状态骨架
researchlog validate        # schema + 不变量检查
researchlog reconcile       # ACTIVE ↔ Git ↔ runs ↔ evidence
researchlog record          # 追加一条证据记录
researchlog run             # 跑一次实验并捕获 provenance
researchlog compare         # 两条 EV 之间的共有测量 + attribution
researchlog findings        # 持久信念（Established / Provisional / Refuted / ...）
researchlog synthesize      # block 收尾时 1-2 页综合（给架构师看）
researchlog telemetry       # §21 productivity KPI 表
```

完整 20 个子命令的参考在 `docs/V1_ACCEPTANCE_GUIDE.md` 和工具的 `--help`。

---

## 文档

| 文档 | 内容 |
| --- | --- |
| [`docs/WORK_LOG.md`](docs/WORK_LOG.md) | 工具开发的日志（按日期追加）。想跟进工作的话**先读这个**。 |
| [`docs/V1_ACCEPTANCE_GUIDE.md`](docs/V1_ACCEPTANCE_GUIDE.md) | V1 验收条目、drill 协议、实测结果。 |
| [`docs/V1_CASES.md`](docs/V1_CASES.md) | V1 drill 套件——每个 drill 有可执行命令 + PASS 信号。 |
| [`docs/GOTCHAS.md`](docs/GOTCHAS.md) | 当前活跃的陷阱。**作为状态**而非日志保留：修好的删掉。 |
| [`docs/RESEARCH_ENGINEERING_V1.5_REVIEW.html`](docs/RESEARCH_ENGINEERING_V1.5_REVIEW.html) | 设计评审与修订日志。 |

AI agent 的 canonical contract 是 [`AGENTS.md`](AGENTS.md)——always-loaded。
详细协议住在 skills 里，按需加载。

---

## 如何贡献

这是个活跃的研究项目。「如何贡献」的诚实形态是：

1. 先读 [`docs/WORK_LOG.md`](docs/WORK_LOG.md)，看什么在飞、什么刚收口。
2. 改任何东西之前先读 [`docs/GOTCHAS.md`](docs/GOTCHAS.md)——陷阱是状态，
   不是日志。
3. 协议改动：先在 `docs/WORK_LOG.md` 写一条；`AGENTS.md` 里的「核心不变量」
   段是合同。
4. 新 skill：加到 `skills/`（canonical），再跑
   `tools/install_research_skills.py --target <your test repo>`。
5. 测试在 `tools/researchlog/tests/`——运行：
   `PYTHONPATH=tools python3 -m unittest discover -t tools -s tools/researchlog/tests`。

---

## License

MIT。 见 [LICENSE](LICENSE)。

---

## 状态

<a name="状态"></a>

- **V1 工具层已于 2026-09-19 收口**。drill 套件 **8/9** 完成。
- **45 PASS + 0 deferred + 4 ENV_BLOCKED**，共 49 个验收 criterion。
- **304 个测试**在 `tools/researchlog/tests/` 下全过。
- 剩下的 4 项 ENV_BLOCKED 是 M6/M7 claude-pending，本沙箱用的 minimax-compat
  endpoint 触发的——原生 Anthropic 订阅上线后会消解。
- 本仓库自己的 `research/ACTIVE.json` 是 **idle**——V1 收口是**已交付**
  的产物，不是正在跑的研究。

**不在本项目 scope 内**：项目自身的活研究活动。新研究要等架构师的
决策（扩 telemetry、切端点、或给一个新 hypothesis）。