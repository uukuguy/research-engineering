---
name: research-search
description: 机制家族本身对不对，要不要换家族——慢循环里"跨家族"那一半。Trigger: no live hypothesis / dominant failure 已移 / phase boundary 8-15 / architect DIRECTION 或 CHALLENGE。不要调我: 测量表面 → `evaluation-design` / 单 run 对照假设 → `experiment-review` / 当前家族内的方向反思 → `retrospective` / claim 落地前 → `scenario-redteam`。
---

# Research search

The slow loop's complement. `retrospective` asks whether the experiments being run are
the right ones; `research-search` asks whether the mechanism family being explored is
the right one at all, and what to swap it for.

## Triggers

* No live hypothesis is registered. The research has spent its last belief budget and
  the next iteration is genuinely novel — there is no `hypotheses_differentiated` to
  fill.
* The dominant failure has moved: a class of failures that used to be the bottleneck
  is no longer the bottleneck, and the new bottleneck has not been characterised.
* A phase boundary (8–15 counted evidence iterations since the last one) shows the
  current mechanism family is exhausted without a clear next move.
* The architect has signalled `DIRECTION` *or* `CHALLENGE` indicating a strategic
  move away from the current line of work.

## The questions

```
What mechanism family has the agent not yet tried?
What mechanism family has it tried that is no longer worth investing in?
What observable in the lab would change the answer to either?
What is the cheapest probe that discriminates between "new family" and
"deeper in the old one"?
```

## Relationship to other skills

* `experiment-review` is the fast loop within one mechanism family. `research-search`
  decides whether to leave the family.
* `retrospective` questions the strategy within the current line of work.
  `research-search` questions the line of work itself.
* `evaluation-design` is consulted when the question is "what should I measure?" —
  `research-search` is consulted when the question is "what should I try at all?".

This skill is new in V1; the body of `evidence-model.md` carries the V0 material
that partially overlaps. The next iteration folds that overlap in and deletes the
duplicate.

## Not this skill

- 测量表面可信度本身有问题 → 调 `evaluation-design` 而不是我。
- 一个 run 跑完要做 OBSERVATION/COMPARISON/INTERPRETATION/DECISION 四层判定 → 调 `experiment-review` 而不是我。
- **当前机制家族内**一系列实验的方向是否对（5+ counted iterations belief_delta: none / phase boundary） → 调 `retrospective` 而不是我。我的触发是**跨家族**：决定要不要换家族，retrospective 是"在当前家族里再想想"。
- 一个候选 claim 要落地为架构锚点之前做 6 项红队 → 调 `scenario-redteam` 而不是我。

**与 `retrospective` 的分界**：我在家族之间，retrospective 在家族之内。家族边界模糊时优先调 retrospective（先在当前家族内再确认一次）。