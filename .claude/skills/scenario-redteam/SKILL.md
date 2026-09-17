---
name: scenario-redteam
description: Load after a promising or informative_failure result, or when an architectural decision is about to be promoted to Integration Mode. Walks the candidate claim through the failure scenarios a careful reviewer would raise — surrogate leaks, dataset drift, hidden confounders, single-anchor evidence — and forces the record to address each one before it lands. New in V1 (no V0 reference, but the red-team material lived inside `experiment-review.md`).
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