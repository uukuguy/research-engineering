# V1 Expert Skill 现状对照表

> 5 个 V1 expert skill 的 SKILL.md 现状审计。deep fix 的输入材料。
> 不靠"推断"，全部从 `cat .claude/skills/<skill>/SKILL.md` 抽取。

## 1. evaluation-design

**Frontmatter description**（一字不改）：

> Load when no evaluator exists for the hypothesis, or a local metric rises while E4/E5
> or architect observation falls. Owns the question of whether the existing measurement
> surface is honest, what to build instead, and how to write a calibration contract that
> survives the next iteration. V1 Block 3 / S1: body lifted from research-engineering's
> V0 reference and merged in.

**正文实际说了什么**（按段落抽取）：

| 段落 | 核心命题 |
|---|---|
| Triggers | 6 条：no local evaluator / official evaluator sparse · hidden · expensive · rate-limited / local metric 与 E4/E5 或 architect 观察分歧 / 定性观察要量化 / E1/E2 → E3/E4 要 representative scenarios / leakage · reward hacking · proxy overfit 可能 |
| Method | 9 步：写 objective → 列 observable → 选最小 metrics → 定义 slices/controls/negatives → 分 dev/tuning vs holdout → 写 limitations 和 gaming 路径 → 建最小 evaluator 跑 calibration → 对 E4/E5 或 architect 观察 → 写 may/may not conclude |
| Evaluation validity contract | 7 项必填：target objective / measured observables / known blind spots / data · scenario provenance / tuning vs holdout separation / gaming · leakage risks / calibration evidence / current highest justified evidence level |
| Do not promote a scalar proxy | 4 个"已经发生"的征兆 |
| Scenarios and holdouts | 5 段 + 4-level 表（E0/E1 → E2/E3 → E4 → E5） |
| Comparability | env change → env record / env query |
| Trust tiers for the evaluator | 5-tier 表（low → strongest） |
| Anti-patterns | 5 行对照表 |
| Output | subject.type: "evaluation_surface" |

**触发的本质**：测量表面本身是否可信。

**触发的反义**：不关心机制本身好不好，只关心**用来评价机制的尺子**准不准。

---

## 2. experiment-review

**Frontmatter description**（一字不改）：

> Load when a run just finished and ≥ 2 hypotheses are live. Walks what the run actually
> said against the registered hypotheses, decides which one(s) it differentiated, and what
> belief change to record. V1 Block 3 / S1: body lifted from research-engineering's V0
> reference and merged in.

**正文实际说了什么**：

| 段落 | 核心命题 |
|---|---|
| 四层 | OBSERVATION → COMPARISON → INTERPRETATION → DECISION（不可逆序） |
| 三轴 | execution_status / research_outcome / confidence — 不可坍缩 |
| Does this count as an iteration | 计数公式：status=completed ∧ outcome ∈ {confirmed, refuted, inconclusive, informative_failure, promising} ∧ (hypotheses_differentiated ≠ ∅ ∨ belief_delta ≠ none) |
| Competing hypotheses | 7 字段：falsifiable claim / mechanism / predictions / falsifier / cheapest discriminating evidence / rough cost / 排名 |
| After a promising result | 8 项必跑的对抗场景 |
| Recording | `record --from-orphan EXP-0142`，完整 EV-* 模板 |
| A run that failed well | informative_failure 的标准记录形态 |
| Escalation | review 不能分开 → diagnosis trigger，不跑更多同实验 |

**触发的本质**：一个 run 跑完后，**对照假设**做事实/对照/解释/决策四层判定。

**触发的反义**：不评判测量表面（那是 evaluation-design），不评判方向（那是 retrospective/research-search），只评判"这次实验对活假设意味着什么"。

---

## 3. research-search

**Frontmatter description**（一字不改）：

> Load when search space must be reopened — no live hypothesis exists, the dominant
> failure has moved and the research has not followed it, or a phase boundary shows the
> current mechanism family is exhausted. Owns the question of what to try next, not how
> to run it. New in V1 (no V0 reference).

**正文实际说了什么**：

| 段落 | 核心命题 |
|---|---|
| 开头 | "The slow loop's complement. retrospective asks whether the experiments being run are the right ones; research-search asks whether the mechanism family being explored is the right one at all, and what to swap it for." |
| Triggers | 4 条：no live hypothesis / dominant failure 已移 / phase boundary 8–15 / architect `DIRECTION` 或 `CHALLENGE` |
| The questions | 4 个问题 |
| Relationship to other skills | 与 experiment-review / retrospective / evaluation-design 的边界声明（**这是 V1 唯一在 SKILL.md 正文里显式声明 skill 间边界的**） |

**触发的本质**：搜索空间是否要重开——**机制家族**对不对，要不要换家族。

**触发的反义**：不评判一个 run（experiment-review），不评判方向策略（retrospective），不评判测量（evaluation-design），只评判"我们玩的这个机制家族值不值得继续玩"。

---

## 4. retrospective

**Frontmatter description**（一字不改）：

> Load when the last 5 counted iterations all carry belief_delta: none, or at a phase
> boundary. The slow loop: asks whether the experiments being run are the right ones at
> all. V1 Block 3 / S1: body lifted from research-engineering's V0 reference and merged
> in.

**正文实际说了什么**：

| 段落 | 核心命题 |
|---|---|
| 开头 | "This is the slow loop. The fast loop asks 'what is the next experiment'. The retrospective asks whether the experiments being run are the right ones at all." |
| Triggers | 6 条：8–15 counted iterations / 5+ 相似变化无进展 / local metric vs 物理/仿真观察 分歧 / 新证据动摇架构假设 / 长时间 exploitation 单家族 / dominant failure 已移 |
| The questions | 6 个问题 |
| What a plateau looks like | 平台期形态 + 4 项检查清单 |
| Reopening the search space | 6 步外部知识流程 |
| Branch diversity | 多分支保留 |
| What the retrospective writes | FINDINGS.md + CURRENT.md，不写 raw evidence |
| Research budget | 4 个问题（高价值不确定性？努力/分数比？哪个 failure 解锁最多？instrument 投资？） |
| Escalation | HARD boundary / 战略 tradeoff / 环境投资 |
| Recording | 自身不产生 EV-*，触发的新架构 spike 或 discriminating experiment 才产生 |

**触发的本质**：当前这一系列实验**方向**对不对（不是"机制家族"对不对）。

**触发的反义**：不评判"换家族"（research-search），不评判单 run（experiment-review），不评判测量（evaluation-design），只评判"我们在这一族机制里玩了这么久，玩的方向对不对"。

---

## 5. scenario-redteam

**Frontmatter description**（一字不改）：

> Load after a promising or informative_failure result, or when an architectural decision
> is about to be promoted to Integration Mode. Walks the candidate claim through the
> failure scenarios a careful reviewer would raise — surrogate leaks, dataset drift,
> hidden confounders, single-anchor evidence — and forces the record to address each one
> before it lands. New in V1 (no V0 reference, but the red-team material lived inside
> `experiment-review.md`).

**正文实际说了什么**：

| 段落 | 核心命题 |
|---|---|
| 开头 | "A defensive pass run before a result becomes an architectural anchor." |
| Triggers | 3 条：最近 record 是 promising/informative_failure / experiment-review 推荐 promote / architect `DECISION FINAL:` 追溯到单 record |
| The checklist | 6 项必查：surrogate leak / dataset drift / hidden confounder / single-anchor evidence / code-state drift / architect signal not yet consumed |
| Relationship to other skills | 与 experiment-review / retrospective 的边界声明 |

**触发的本质**：一个候选 claim 在落地（成为架构锚点）之前，**假扮攻击者**过一遍 6 项必查。

**触发的反义**：不评判 run 的假设对照（experiment-review），不评判方向（retrospective），不评判家族（research-search），不评判测量（evaluation-design）——**只评判"这个 claim 落地前还有没有漏洞没补"**。

---

## 边界对照（5 个 skill 的互斥点 + 灰色地带）

### 互斥点（明确）

| 触发的本质 | 对应 skill | 不该调它的场景 |
|---|---|---|
| 测量表面本身是否可信 | `evaluation-design` | 假设对照、方向、家族、claim 落地 |
| 单 run 对照假设的判定 | `experiment-review` | 测量、方向、家族、claim 落地 |
| 机制家族是否要换 | `research-search` | 测量、单 run、方向、claim 落地 |
| 当前系列实验方向是否对 | `retrospective` | 测量、单 run、家族、claim 落地 |
| Claim 落地前的红队 | `scenario-redteam` | 测量、单 run、方向、家族 |

### 灰色地带（潜在模糊）

#### 模糊点 1：`research-search` vs `retrospective`

**两者都是"慢循环"**。

- `research-search` description 写："asks whether the mechanism family being explored is the right one at all, and what to swap it for"
- `retrospective` description 写："asks whether the experiments being run are the right ones at all"

正文里 `research-search` 自承：

> `experiment-review` is the fast loop within one mechanism family. `research-search` decides whether to leave the family.
> `retrospective` questions the strategy within the current line of work. `research-search` questions the line of work itself.

正文里 `retrospective` 自承：

> The fast loop asks "what is the next experiment". The retrospective asks whether the experiments being run are the right ones at all.

**对照读**：
- "experiments being run are the right ones" = `retrospective`
- "mechanism family being explored is the right one" = `research-search`

**模糊处**：当一系列实验**已经在单家族内 exploit 但还没到 5 次 belief_delta: none**——是 retrospective 触发条件吗？`retrospective` triggers 第 2 条写"5 or more similar changes with no substantive progress"，但 `research-search` triggers 第 1 条写"the research has spent its last belief budget and the next iteration is genuinely novel"——这两个触发条件**有交集**（5 次无进展 = 已用完 belief budget）。

#### 模糊点 2：`experiment-review` vs `scenario-redteam`

**两者都涉及"过一遍结果"**。

- `experiment-review` triggers: "a run just finished and ≥ 2 hypotheses are live"
- `scenario-redteam` triggers: "most recent record has `research_outcome: promising` or `informative_failure`"

**对照读**：
- 每次 run 完（≥2 hypotheses）→ `experiment-review`
- run 完且结果是 promising/informative_failure → `experiment-review` 先做，再可能触发 `scenario-redteam`

正文 `scenario-redteam` 自承："experiment-review is run immediately after a result; scenario-redteam is run before promotion"

**模糊处**：experiment-review 自身也有 "After a promising result" 段，要求"run these before promoting anything"——列了 8 项必跑对抗场景。这 8 项**与** scenario-redteam 的 6 项 checklist **有部分重叠**（distribution shift / extreme timing / hidden confounders 在两边都出现）。

正文 `scenario-redteam` 开头说："the red-team material was historically part of `experiment-review.md`. The next iteration folds that rest of that material in and deletes the duplicate."

**这是显式 TODO**——但当前没做。

#### 模糊点 3：`evaluation-design` vs `experiment-review`

**两者都涉及"评判证据"**。

- `evaluation-design` 是"测量表面本身可信吗"
- `experiment-review` 是"这次 run 对假设意味着什么"

**模糊处**：当一个 experiment-review 判定"promising"，但 architect 观察与之矛盾——下一步是 `experiment-review` 的"再跑一个区分性实验"，还是 `evaluation-design` 的"测量表面有盲点"？

正文 `evaluation-design` 第 16 行："When the architect says 'cases 31/37/42 look like stop-go oscillation and the metrics do not capture it', that is the evaluator being told it has a blind spot. The correct response is to build the missing observable..."

正文 `experiment-review` 第 187 行："If the review cannot separate the hypotheses and the failure is complex ... that is a `diagnosis` trigger, not a reason to run more of the same experiment."

**对照**：architect 观察 vs metric 不一致 → evaluation-design；review 不能分假设 → diagnosis（不在 5 个 V1 expert skill 内，是另一个机制）。

**这个边界相对清晰**——一个是测量层问题，一个是推理层问题。

#### 模糊点 4：`scenario-redteam` 触发条件的精确度

description 写"Load when an architectural decision is about to be promoted to Integration Mode"——但**没有显式定义 Integration Mode 是什么**。这个边界靠其他 skill 的引用（evaluation-design、experiment-review 提到 "promote"），但当前没有 README/INDEX 明确"Integration Mode = 什么"。

#### 模糊点 5：5 个 skill 全部缺一段"互斥声明"

只有 `research-search` 和 `scenario-redteam` 在 SKILL.md 正文里写了 "Relationship to other skills" 段。`evaluation-design` / `experiment-review` / `retrospective` **没有**显式声明和其他 4 个的边界——它们靠 description 的 trigger 区分，但 trigger 只说"什么时候调我"，没说"什么时候不要调我"。

---

## 总结：deep fix 需要做的事

按优先级排：

1. **补全 5 个 skill 的"不触发场景"**（互斥声明）——3 个 skill 缺这段
2. **处理 research-search vs retrospective 的灰色地带**——触发条件交集需要明确划界（建议：以"是否还在当前机制家族"为分界，retrospective 在家族内，research-search 在家族间）
3. **处理 experiment-review vs scenario-redteam 的历史遗留重复**——SKILL.md 已自承 TODO：fold in and delete duplicate
4. **scenario-redteam 的"Integration Mode"补定义**——要么在 SKILL.md 里写，要么在 README/INDEX 里
5. **重写 5 个 description**——按"互斥点"写 trigger，避免"load when X"的单一触发模式，让 router 一眼分得清

---

## 不要在这次 deep fix 里做的事

- 改 5 个 skill 的**实质方法**（method / checklist）——那是机制层，不在边界重审范围
- 改 router 表（在 research-engineering 里）——deep fix 只动 skill 自身
- 改 ENV-LIM-004 / V1-D9 verify_v1_d9.py heuristic——那是 V1 acceptance 验收，独立轨道
