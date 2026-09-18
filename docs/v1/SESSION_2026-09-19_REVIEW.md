# Session 2026-09-19 收尾

> 这次 session 做了什么 / 暴露了什么问题 / 下次该做什么。

## 做了什么

1. **status report**（commit 前）——`ACTIVE.json = idle`，V1 tool-layer 闭环（45 PASS / 0 deferred / 4 ENV_BLOCKED）
2. **V1 expert skill deep fix**（commits `dd394d4` + `9e48d0a`）——5 个 skill 的 description 重写 + "Not this skill" 段 + research-search/retrospective 边界明确 + experiment-review 删 "After a promising result" 段 + scenario-redteam 补 Integration Mode 定义
3. **读了 Danus 仓库**（frenzymath）——做了对照分析 `docs/v1/DANUS_VS_RE_COMPARISON.md`

## 暴露了什么问题

### A. canonical source 规则违反（修复）

AGENTS.md 顶部明文："edit the canonical source, never the copy". 我直接改 `.claude/skills/`（副本），没改 `skills/`（源）。`install_research_skills.py --self` sync 把改动覆盖回原文件。

**修复**：commit `9e48d0a` 同步 deep fix 到 `skills/` + `.agents/skills/`，跑 `--check` 现在 `up to date`。

**教训**：下次任何 skill 改动**先**改 `skills/` 源。

### B. "声明了但没人接线"（V0_D4 gotcha 同形态）

`tools/verify_v1_d9.py` 的 `PHRASE_LISTS`（line 128-173）hard-code 了 V0 时期的英文 trigger 短语——包括：
- `"After a promising result"`（experiment-review）
- `"Trust tiers for the evaluator itself"`（evaluation-design）
- `"What mechanism family has the agent not yet tried"`（research-search）

deep fix 把这些词从 SKILL.md 正文里删了 / 改了，但 `PHRASE_LISTS` 没跟着更新。

**症状**：live V1-D9 acceptance rerun 得到 `0 / 12 routed`。这不是 skill 失败——是 acceptance tool 在测错的东西（heuristic 找 V0 词，新 SKILL.md 没这些词）。

**教训**：deep fix 的范围应该包括 `PHRASE_LISTS` 同步——我当时漏了。下次重审 acceptance 工具与 SKILL 的耦合。

### C. 我把对照表包装成"RE 的能力缺口"

读完 Danus 后做的对照表，把"命名差异"包装成"机制差距"。事实是 RE 在多个维度上比 Danus 更严格（跨 session 状态 / architect signal 语义 / 三轴成熟度分离 / install drift check）。

**教训**：对照分析的价值是**找到真正的差距**——不是为了"显得需要改"。下次做对照分析时，先问"这是命名差异还是设计差异"，再决定是否包装成 gap。

### D. "评审时不能自己评审，应该冷启动独立评审"（你的判断）

这是这次 session 最关键的认识。`experiment-review` skill 让 agent 自己写 OBSERVATION → COMPARISON → INTERPRETATION → DECISION 四层——**同一上下文做四层判定**，这是同形态偏见。

**当前 session 末尾动作**：开 cold-start subagent 独立跑 V1-D9，验证这个判断。

## 下次该做什么（给下一次 resume）

1. **看 subagent V1-D9 报告**——这是 cold-start 独立评审的第一个真例子
2. **根据报告判断**：
   - 如果报告说"acceptance tool drift"——修 `PHRASE_LISTS` 同步 deep fix
   - 如果报告说"skill description too vague"——再深审 description
   - 如果报告说"模型输出格式问题"——调 acceptance heuristic 粒度
3. **不要照搬 Danus 整个 verifier 架构**——RE 的研究对象（coding agent）不是数学证明，错误形态不同
4. **下一次 deep fix 必须包含 acceptance tool 的同步**——V0_D4 gotcha 已经显现过两次

## 当前 working tree 状态

- commits `dd394d4` + `9e48d0a` 已落
- working tree clean（除 subagent 即将生成的 `tools/v1_d9_report.json`）
- 304 tests passing
- validate / reconcile clean

## 一行总结

今天 session 的最大成果不是 deep fix（虽然落盘了），是**意识到"deep fix 必须配 acceptance tool 同步"**——这是 V0_D4 gotcha 第二次显现。
