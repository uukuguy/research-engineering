# Research Environment

What the lab can measure. This is an inventory of instruments, not a list of
requirements — it describes what evidence is obtainable *here*, right now.

The distinction matters because "we cannot run that experiment" is not evidence about a
hypothesis. It is a statement about the laboratory, and it belongs in this file rather
than in `FINDINGS.md`.

```json research:environment
{
  "schema_version": "1.0",
  "environment_id": null,
  "available": {
    "compute": [],
    "simulator": [],
    "data": [],
    "external_services": []
  },
  "limitations": [],
  "harnesses": [],
  "capability_map": [],
  "comparability": {
    "fingerprint": null,
    "last_material_change": null,
    "status": "COMPATIBLE",
    "anchor_evidence": []
  },
  "history": []
}
```

## Limitations and harnesses

A limitation records that a phenomenon cannot be expressed here at all, with the
capability affected and the evidence that established it:

```json
{
  "limitations": [
    {
      "id": "ENV-LIM-001",
      "capability": "post-planner control tampering",
      "status": "ENV_UNSUPPORTED",
      "impact": "E4 physical-safety evidence is unobtainable for control-channel attacks.",
      "verified_by": "EV-20260911T101530Z-a7f3"
    }
  ]
}
```

A harness records a substitute that *is* available, and — more importantly — what it
does not preserve:

```json
{
  "harnesses": [
    {
      "id": "HARNESS-001",
      "capability": "post-planner command corruption replay",
      "supports_evidence": "E2/E3",
      "preserves": ["planner command schema", "timing and ordering"],
      "missing": ["actuator dynamics"],
      "verified_by": "EV-20260911T101530Z-a7f3"
    }
  ]
}
```

The `preserves` and `missing` lists are what make the harness usable honestly: they
become the surrogate contract on any evidence drawn from it.

## Comparability

`fingerprint` is a compact digest of everything that could move a result — simulator
and physics versions, tick rate, sensor models, data snapshots, model checkpoints,
inference backend, evaluator semantics, and performance-relevant hardware.

- `COMPATIBLE` — direct comparison is allowed.
- `REBASELINED` — comparison is allowed after re-running the anchor baselines.
- `INCOMPARABLE` — do not attribute a cross-environment delta to the mechanism.

Only update this file when research capability or comparability actually changes:
a new capability or limitation, a new reusable harness, a material environment change,
or an availability flip in either direction.
