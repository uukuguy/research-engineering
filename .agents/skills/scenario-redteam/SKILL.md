---
name: scenario-redteam
description: 一个候选 claim 落地为架构锚点前的红队——6 项 checklist（surrogate leak / dataset drift / hidden confounder / single-anchor evidence / code-state drift / architect signal）。Trigger: record 是 promising/informative_failure / experiment-review 推荐 promote / architect DECISION FINAL 追溯到单 record。不要调我: 测量表面 → `evaluation-design` / 单 run 对照假设 → `experiment-review` / 方向反思 → `retrospective` / 换家族 → `research-search`。
---

# Scenario redteam

A defensive pass run *before* a result becomes an architectural anchor. A promising or
informative_failure result is exactly the kind of finding a careful reviewer will
question — and the answer should land in the record itself, not in a follow-up
session that has to reconstruct what was tried.

## Triggers

* The most recent record has `research_outcome: promising` or
  `informative_failure`.
* An `experiment-review` recommended promotion to Integration Mode.
* The architect has signalled `DECISION FINAL:` on something that traces back to a
  single evidence record.

## Integration Mode (what "promotion" means here)

`Integration Mode` is the transition from research track to production track, as defined
in `AGENTS.md` ("Working mode"): stable interfaces, selective regression, cleanup. The
candidate claim moving into Integration Mode is what "about to be promoted" refers to in
the trigger above. The redteam checklist below runs before that transition; once a
record clears all six, it is anchor-ready for the production track.

## The checklist

For each scenario below, the record must either name why it does not apply, or cite a
prior record that addresses it. A record that skips a scenario is, for purposes of
promotion, the same as one that fails the scenario.

1. **Surrogate leak.** Does the surrogate (mock, replay, reduced simulator) preserve
   the feature the claim depends on? See `references/surrogate-validity.md`.
2. **Dataset drift.** Has the dataset the record was produced against shifted since
   the record that introduced the hypothesis?
3. **Hidden confounder.** Is there a third variable that explains both the
   independent and the dependent variable?
4. **Single-anchor evidence.** Is the conclusion supported by one record, or by a
   chain? Promoted conclusions must point at the chain, not the chain's weakest link.
5. **Code-state drift.** Has the tool itself changed between the first appearance of
   the claim and the present one? See `references/git-research-infrastructure.md`.
6. **Architect signal not yet consumed.** Has any `CHALLENGE` or `VETO` from
   `ARCHITECT.md` been recorded against this line of work and not yet addressed?

A `scenario-redteam` run is the moment to surface each of the six; the red-team
output is a short note appended to the record's `observations`, not a separate
finding.

## Relationship to other skills

* `experiment-review` is run immediately after a result; `scenario-redteam` is run
  before promotion, and may draw on multiple records.
* `retrospective` looks at the trajectory; `scenario-redteam` looks at the next
  single claim that the trajectory is about to harden.

This skill is new in V1; the red-team material was historically part of
`experiment-review.md`. The next iteration folds the rest of that material in and
deletes the duplicate.

## Not this skill

- 测量表面可信度本身有问题 → 调 `evaluation-design` 而不是我。
- 一个 run 跑完要做 OBSERVATION/COMPARISON/INTERPRETATION/DECISION 四层判定 → 调 `experiment-review` 而不是我（promising 之后的对抗场景已归我）。
- 当前家族内的方向反思（5+ counted iterations belief_delta: none） → 调 `retrospective` 而不是我。
- 决定要不要换机制家族 → 调 `research-search` 而不是我。

我的边界是**claim 落地前的最后一道关**：6 项红队 checklist 全部清掉前，不让 record 进 Integration Mode。