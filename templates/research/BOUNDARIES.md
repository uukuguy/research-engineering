# Research Boundaries

Three tiers. Which tier something sits in decides who may change it.

- **HARD** — changing one of these requires the architect. Competition rules, external
  data policy, official metric semantics, verified SDK coordinate and unit conventions,
  the physical actuator safety envelope, evaluator and holdout truth, official
  credentials, spend and compute caps, and the submission budget.
- **PROVISIONAL** — the agent may change these when evidence supports it, but must
  record the change. Current world-state representation, module boundaries, the
  safety/planner interface, replay formats, architecture ownership.
- **FREE** — the agent's own business, no permission and no record beyond the usual
  evidence trail. Algorithms, models, thresholds, internal structures, prototypes,
  instrumentation, probes, synthetic scenarios, cheap local harnesses.

The `research:boundaries` block is the machine-readable source of truth.

```json research:boundaries
{
  "schema_version": "1.0",
  "hard": [],
  "provisional": [],
  "free": [],
  "submission_budget": null,
  "submissions_used": 0
}
```

## Submission budget

`submission_budget` exists because official submissions are scarce — often three to
five for an entire competition — and they are the one resource that cannot be
recovered by working harder. Set it during bootstrap. Reaching the budget is an error,
not a warning: it stops and asks rather than spending the last attempt.

Leave it `null` for projects with no external submission step.
