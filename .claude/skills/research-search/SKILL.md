---
name: research-search
description: Load when search space must be reopened — no live hypothesis exists, the dominant failure has moved and the research has not followed it, or a phase boundary shows the current mechanism family is exhausted. Owns the question of what to try next, not how to run it. New in V1 (no V0 reference).
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