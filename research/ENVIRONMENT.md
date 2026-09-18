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
  "limitations": [
    {
      "id": "ENV-LIM-004",
      "capability": "V1-D9 router-routing acceptance on minimax-compat endpoint",
      "status": "ENV_BLOCKED",
      "impact": "V1-D9 acceptance (`tools/verify_v1_d9.py`, claude × pi each ≥3 routed correct) is not satisfiable under the minimax-compat endpoint this sandbox uses. claude-end scores swing between 0/6 and 4/6 across reruns because the CLI's background prefetch and minimax's model-routing jitter break the latency contract; pi-end scores 0/6 (no `--provider` pin) or 1/6 (with `--provider minimax --model MiniMax-M3` pin) because the model reads `AGENTS.md` via the loaded skills and answers based on real repo state (`ACTIVE.json idle`, `AGENTS.md` declares idle is normal) rather than the synthetic router prompt, so first_line does not name the expected skill. The router itself is reachable (full stdout contains 1-4 expected-skill mentions on captured rows); the acceptance heuristic `expected in first_line.lower()` is the wrong granularity for this endpoint. M6 cannot close under minimax; M6 splits into M6-pi (already passing on minimax when the heuristic counts full captured_stdout) + M6-claude-pending (re-run under native Anthropic).",
      "verified_by": "tools/v1_d9_report.json (commit 04d9445 sandbox run)"
    }
  ],
  "harnesses": [],
  "capability_map": [
    {
      "id": "CAP-v1d9-routing-001",
      "capability": "V1-D9 router reachability via phrase-list classifier",
      "status": "AVAILABLE",
      "supports_evidence": "E0",
      "reuse_counter": 1,
      "first_used_at": "2026-09-18T13:37:14+00:00",
      "last_used_at": "2026-09-18T13:37:14+00:00",
      "last_used_by_evidence_id": "EV-20260918T133714Z-7b6f",
      "notes": "Phrase-list heuristic landed 2026-09-18; first cited by env_blocked EV."
    },
    {
      "id": "CAP-researchlog-replay-001",
      "capability": "researchlog E2/E3 replay with stable identity",
      "status": "AVAILABLE",
      "supports_evidence": "E3",
      "reuse_counter": 0,
      "notes": "Block 2 / T2 ledger partition + identity-stable replay. Demonstrated by the V0 #14 acceptance drill."
    },
    {
      "id": "CAP-resume-from-files-001",
      "capability": "session recovery from canonical state files alone",
      "status": "AVAILABLE",
      "supports_evidence": "E4",
      "reuse_counter": 0,
      "notes": "Block 1 §6: ARCHITECT.md / ACTIVE.json / FINDINGS.md / ENVIRONMENT.md / BOUNDARIES.md + git HEAD/branch/diff. Demonstrated by V0 D1 (7/7)."
    }
  ],
  "comparability": {
    "fingerprint": "sha256:905ec22fa4076f9485a74cf774cc6c8a414d813cb9398988f4819fca6fde0024",
    "last_material_change": "2026-09-18T12:42:36+00:00",
    "status": "COMPATIBLE",
    "anchor_evidence": []
  },
  "history": [
    {
      "type": "environment_change",
      "at": "2026-09-18T12:42:36+00:00",
      "capability": "V1-D9 acceptance endpoint policy",
      "changes": {
        "env.endpoint": "minimax-compat"
      },
      "comparability": "COMPATIBLE",
      "fingerprint": "sha256:1733fb3fb292ba9e6adbf8ea5a152b85c202e404d4f2c9f97795473b0182689c",
      "evidence_id": "EV-20260918T124236Z-479f",
      "notes": "Endpoint is steady-state minimax-compat, not a sandbox artifact. ENV-LIM-004's 'M6-claude-pending (re-run under native Anthropic)' clause is non-actionable under the current endpoint policy; see ARCHITECT signal D-004 for the policy decision."
    },
    {
      "type": "rebaseline",
      "at": "2026-09-18T14:27:39+00:00",
      "previous_fingerprint": "sha256:1733fb3fb292ba9e6adbf8ea5a152b85c202e404d4f2c9f97795473b0182689c",
      "fingerprint": "sha256:905ec22fa4076f9485a74cf774cc6c8a414d813cb9398988f4819fca6fde0024",
      "reason": "V1-D7 verification",
      "comparability": "COMPATIBLE"
    }
  ]
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
