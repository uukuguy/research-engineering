# Current Research State

This is research-level working memory: what we are trying to learn, what we currently
believe, and what the next empirical action is. It is not a timeline and not a log.

The `research:current` block below is the machine-readable source of truth. Edit it
through `researchlog`, never by hand. The prose here explains how to read the file; it
does not restate the facts, so the two cannot drift apart.

```json research:current
{
  "schema_version": "1.0",
  "objective": null,
  "evidence_maturity": {
    "highest_stable_level": null,
    "system_wide_level": null,
    "note": null
  },
  "environment_maturity": {
    "environment_id": null,
    "highest_supported_by_capability": {},
    "blocked_or_unsupported": [],
    "pending_rebaseline": []
  },
  "working_pieces": [],
  "provisional_system_shape": null,
  "architecture_frozen": false,
  "highest_value_uncertainties": [],
  "active_research": [],
  "current_frontier": [],
  "next_empirical_action": "Session handoff (2026-09-19): V1 tool-layer 闭环。下一 session 接手:读 ACTIVE/CURRENT/WORK_LOG → 跑一次 reconcile 确认 8/9 drill 仍绿 → 若 Architect 已触新 hypothesis 或 V1-D6 #4 feature work,继续;否则停在 idle 等 A-3/A-4/M6-claude-pending/V1-D6 #4 决策。"
}
```

## How to read this

Three maturities are tracked separately and must never be collapsed into one
percentage. A system can be fully built (System Maturity high) while a new mechanism
inside it is still only E1 (Evidence Maturity low), and the environment may be unable
to verify a whole class of question regardless of either.

- **System Maturity** — how far the thing itself has been built.
- **Evidence Maturity** — how well we actually know it works, per claim.
- **Research Environment Maturity** — what the current lab can measure at all.

`architecture_frozen` is false unless `ARCHITECT.md` says otherwise. A provisional
shape that has never been challenged is a suspicion, not a design.
