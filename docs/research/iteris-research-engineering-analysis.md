# Iteris、Research Engineering 与 Danus 的关系及改进建议

日期：2026-09-20

## 分析范围

本文依据以下材料作出判断：

- `research-engineering/docs/research-engineering-complete-design-v1.5.pdf`
- `research-engineering` 的 `AGENTS.md`、主 Skill、专家 Skill、`researchlog` 实现、状态文件、验收报告与测试
- `iteris` 的项目说明、Agent 运行代码、任务与事实存储、监督器和独立验证实现 https://github.com/frenzymath/iteris 本地项目在 sandbox/agentic-2026/Danus/iteris
- Danus 当前的研究目标、可信事实链和最小通用内核设计 https://github.com/uukuguy/Danus 本地项目在 ~/sandbox/agentic-2026/Danus/Danus

对 `research-engineering` 的实测结果如下：

- `researchlog` 的 304 项单元测试全部通过。
- `researchlog validate` 通过。
- `researchlog reconcile --json` 报告状态一致。
- 当前仓库有 3 条 Evidence、0 条持久 Finding、0 个 run manifest。
- 5 项研究效率指标中，当前只有累计 Evidence iteration 可以计算；首次 E1、首次 E3、Session Recovery Accuracy，以及“不经架构师纠正选出区分性实验”的比例都还没有有效结果。

这些结果说明工具层已经比较扎实，但不能单独证明这套方法确实提高了长期研究的质量和效率。

## 结论

Iteris 确实和 Research Engineering 更接近，但只说“更接近”并不完整。

更准确的定位是：

> Iteris 是一个面向计算数学、具备实际运行和调度能力的研究工作台；Research Engineering 是一套面向应用 AI 研究、可以嵌入不同编程 Agent 的研究操作层。Iteris 的整体形态更像 Research Engineering，可信性内核则更像 Danus。

Research Engineering 不是一个实验日志。它要把通用 Coding Agent 改造成能够持续研究的技术合伙人，设计范围包括研究对象、证据等级、研究环境、评价方法、快慢两层循环，以及研究与集成两种工作模式。它的核心循环是：

```text
技术不确定性
→ 最便宜的有效证据
→ 观察
→ 信念更新
→ 下一次干预
```

不过，它刻意停在“薄控制层”：Skill 负责判断和研究循环，`researchlog` 只负责确定性的记录、校验和对账，不选择假说，不决定保留或回退，也不调用模型。

Iteris 已经跨过了这条边界。它能够启动主 Agent 和探索、执行 Agent，维护任务池和事实库，管理长时间运行的进程，并在 evolve/family 场景下执行自动调度。它还有独立验证 Agent，求解模型和验证模型可以不同；普通命令不能直接制造 verified fact，必须先取得匹配的验证结果。

因此，Iteris 处在两者之间：它具有类似 Research Engineering 的长期研究工作台形态，同时具有类似 Danus 的“未经独立验证的结论不能进入可信事实层”。

## 三者的区别

| 方面 | Research Engineering | Iteris | Danus |
|---|---|---|---|
| 研究对象 | 应用 AI 系统、机制、评价方法和实验环境 | 计算数学问题 | 数学证明 |
| 最小可信单元 | Evidence，以及由 Evidence 支撑的 Finding | 经过验证的 Fact | verifier 接受的 Fact |
| 核心关注 | 尽早把技术不确定性变成有效实验 | 长期推进一个数学研究目标 | 确保数学结论经过独立验证后才能复用 |
| 运行方式 | 主要依靠 Skill 和状态协议；工具只负责记录和校验 | 主 Agent、任务池、探索/执行 Agent、进程管理、Dashboard、evolve/family 调度 | 主 Agent、worker swarm、全局记忆、事实图和 verifier |
| 人的作用 | 总架构师给方向、边界、纠偏和 promotion 决策 | 提出目标、查看进展、review 和 veto | 操作者提出问题并作战略干预 |
| 独立验证 | 当前没有真正独立的 Evidence verifier | 有独立验证 Agent，也支持不同模型和多席 panel | verifier 是唯一真值入口 |

## Iteris 由谁监督

此前把 Iteris 概括为“把复杂研究推进起来并持续监督”，容易让人误以为始终有一个额外的监督 Agent 位于主 Agent 之上。实际情况需要分开看：

- 单项目主要由长期运行的 goal agent 自我协调。
- 人通过 monitor、dashboard、review 和 veto 查看与干预。
- 独立 verifier 负责判断结论能否进入可信事实层。
- 程序化 supervisor 主要用于 evolve/family 等多项目、多方向场景，负责观察状态、处理停滞、控制预算和调度空闲名额。

所以，Iteris 的“监督”不是一个角色包办，而是由人、主 Agent、运行监督器和独立验证器共同完成。

## 对 Research Engineering 的核心改进建议

### 一、暂停扩展 V2 功能，先验证它是否真的提高研究效率

这是最高优先级。

现在已经证明的是：状态文件、记账工具、恢复流程和验收程序能够工作。尚未证明的是：使用 Research Engineering 的 Agent 比普通 Coding Agent 更快得到可靠结论、更少重复工作，也更少误信无效实验。

下一阶段不应继续增加 Skill、Dashboard 或多分支调度，而应做三组真实、受控的研究案例：

1. 没有可运行系统，需要从零构造 probe。
2. 本地指标失真或实验环境不够，需要发现并修正评价方法。
3. 跨多次 session，从 E1 推进到 E3，并完成一次 promotion 判断。

每组都应做对照：普通 Coding Agent 与 Research Engineering 使用同一题目、同一模型和相近预算。只比较真正反映研究质量的结果：

- 第一条有效证据出现的时间；
- 架构师纠正次数；
- session 切换后的重复工作量；
- 无效 surrogate 被当成结论的次数；
- 最终 Finding 经独立复核后仍成立的比例。

在这轮结果出来前，准确的说法应当是“V1 工具层已经验证”，而不是“Research Engineering 方法已经验证”。

### 二、在 Evidence 与 Finding 之间增加独立的证据准入

这是当前最关键的可信性缺口。

`researchlog record` 能严格检查 schema、字段约束和 Git 记录，但 observation、research outcome、belief delta 和 confidence 仍由做实验的同一个 Agent 填写。即使从孤立的 run manifest 恢复记录，也要求当前 Agent 自己补充科学解释。

这保证了记录完整，不能保证解释成立。建议增加只追加的独立审查记录：

```text
原始 Evidence
    ↓
独立 Evidence Review
    ↓
允许支撑 Established / Refuted / Promotion
```

具体边界如下：

- E0/E1 保持轻量，不必每条都审。
- E2 以上、`Established`、`Refuted`，以及进入 Integration Mode 前必须有独立 review。
- Review 应绑定 Evidence、run manifest 和 artifacts 的内容摘要，避免审查后内容发生变化。
- Review 不替 Agent 决定研究方向，只检查：
  - 实验实际运行了什么；
  - baseline/control 是否存在；
  - 当前环境或 surrogate 是否真的能回答该问题；
  - observation 与 interpretation 是否混在一起；
  - 结论是否超过 Evidence 能支持的范围。
- Review 失败不删除原始 Evidence，只是不允许它成为成熟 Finding 的依据。

可以借用 Iteris 的独立验证形式，但不能直接照搬数学事实的验证语义。Research Engineering 需要审查的是实验有效性、因果解释和结论范围，而不是把所有研究结论都当成可判真假的数学命题。

### 三、把控制规则变成机器可读的“下一项义务”

Research Engineering 的很多关键规则目前存在于 Skill 文字中：何时 retrospective、何时 rebaseline、何时停止一个 block、何时不能 promotion。规则本身已经比较完整，但跨客户端执行时仍依赖模型是否正确理解和遵守。

建议增加只读命令，例如：

```bash
researchlog obligations --json
```

它不选择假说，也不决定下一次实验，只从 canonical state 推导当前必须先完成的事项，例如：

```text
RESUME_RECONCILIATION_REQUIRED
RUN_REVIEW_REQUIRED
BLOCK_SYNTHESIS_REQUIRED
ENVIRONMENT_REBASELINE_REQUIRED
EVIDENCE_REVIEW_REQUIRED
PROMOTION_BLOCKED
ARCHITECT_DECISION_REQUIRED
```

这不会把 `researchlog` 变成调度器，却能让重要的状态转换不再只靠自然语言理解。跨客户端验收也应检查这些结构化状态，而不是检查模型是否复述了某句 Skill 原文。

这项工作需要同时补齐测量基础：

- 每条 Evidence 直接记录 `session_epoch`，不要靠时间区间猜它属于哪个 session。
- session 恢复结果写成只追加事件，才能计算 Session Recovery Accuracy。
- Architect Signal 进入可查询事件流，才能计算“不经架构师纠正的区分性实验比例”。
- `sessions.jsonl` 的坏行必须显式报告，不能静默跳过，否则 KPI 会在不报警的情况下失真。
- Evidence iteration 的判定只保留一个实现，避免记录逻辑与 telemetry 逻辑逐渐分叉。

## 最终判断

Research Engineering 已经有完整而且有辨识度的研究思想，也已经有可靠的记录、恢复和校验工具。它下一步最不需要的是继续堆功能。

真正决定项目能否成立的是三件事：

1. 用真实研究案例证明这套方法确实提高研究质量和效率。
2. 让重要结论经过独立证据审查后才能成为成熟 Finding。
3. 把关键状态转换变成跨客户端都能执行和检查的结构化规则。

完成这三件事后，Research Engineering 才会从一套讲得通、做得扎实的研究协议，变成一套已经证明能够帮助 Agent 做好长期研究的基础设施。
