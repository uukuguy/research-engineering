# Evidence Model

Load when choosing the next experiment, or when a result's evidence level is not obvious.

## Research Subject

There is no `parent runnable candidate`. There is a subject, and it can be anything:

```
question  idea  mechanism  algorithm  component  architecture_spike
harness  instrumentation  evaluation_surface  partial_stack
vertical_slice  system  submission_candidate
```

A 40-line NumPy probe on day one and a full robot stack three weeks later are described
by the same protocol. `ACTIVE.subject` and every evidence record's `subject` use
`{"type": ..., "id": ...}` with a type from that list.

Note what is on it: `harness`, `instrumentation`, and `evaluation_surface` are research
subjects in their own right. Building a replay converter is not chores, it is research
that raises the evidence throughput of everything after it.

## Choosing the level

Ask what the cheapest artifact is that can *materially reduce this uncertainty*, then
check that the level it reaches is enough to answer the question. Those are two separate
checks and both must pass.

| Uncertainty | Cheapest thing that answers it | Not this |
|---|---|---|
| Is there a signal at all? | E1 probe, one plot | a component with a config system |
| Which of two mechanisms is better? | E2 replay benchmark with a fixed suite | a full system A/B |
| Does information survive the causal path? | E3 slice with explicit mocks | an E2 microbenchmark |
| Does it hold on the real distribution? | E4 scenario suite | more E2 tuning |

The failure mode in both directions is real. Under-reaching produces a confident
conclusion the evidence cannot carry. Over-reaching burns a week to learn what a plot
would have shown — three weeks with no executable evidence is the classic version of
this, and it is tracked as a project risk, not a schedule problem.

Concrete: to learn whether cross-modal disagreement is a usable integrity signal, run a
replay over recorded camera and LiDAR frames and plot disagreement against attack onset.
Do not build the trust estimator, the world state, and the governor first.

## Recording a result

One immutable record per meaningful result, written by the tool:

```bash
python3 tools/researchlog record --help
python3 tools/researchlog record --from-orphan EXP-0142   # mechanical fields prefilled
```

```json
{
  "schema_version": "1.0",
  "evidence_id": "EV-20260911T101530Z-a7f3",
  "experiment_id": "EXP-0142",
  "question": "Does motion-aware release reduce recovery oscillation without delaying safe stop?",
  "subject": {"type": "component", "id": "recovery-policy"},
  "hypothesis_ids": ["H-037", "H-039"],
  "evidence_level": "E3",
  "target_evidence_level": "E4",
  "observations": ["case17 oscillation amplitude 0.42 -> 0.11 rad/s", "safe-stop latency unchanged at 180ms"],
  "measurements": {"oscillation_amplitude": 0.11, "stop_latency_ms": 180},
  "execution_status": "completed",
  "research_outcome": "promising",
  "confidence": "moderate",
  "hypotheses_differentiated": ["H-037"],
  "belief_delta": "refined",
  "counts_as_evidence_iteration": true,
  "invalidated_if": ["env.sim_physics_hz != 30", "inputs.replay_suite changed"],
  "limitations": ["no actuator dynamics: E3 slice uses a mock controller"],
  "artifacts": [{"path": "research/runs/EXP-0142/artifacts/trace.jsonl", "role": "trace"}],
  "code_state": {"branch": "research/recovery", "commit": null, "base_commit": "83ab21c", "dirty": true, "diff_sha256": "9f1c..."},
  "environment": {"id": "ENV-local-v1", "fingerprint": "sha256:41d0...", "comparability": "COMPATIBLE"}
}
```

`measurements` must be flat `str -> scalar`. `compare` needs a well-defined set of common
measurements between two records, and that is undefined the moment nesting appears.

`evidence_id` is minted collision-resistant (`EV-<UTC timestamp>-<4 hex>`); the real
guarantee is `O_CREAT|O_EXCL`, not the random suffix. Never allocate an ID by reading the
last one and incrementing — two worktrees doing that produce a semantic collision at
merge. Hand-written short IDs (`EXP-0142`) remain valid input; the tool simply never
mints them.

## The two axes

`execution_status` and `research_outcome` are independent, and the tool enforces the
separation as a hard error.

| `execution_status` | scientific content |
|---|---|
| `completed` | the run did what it was supposed to do |
| `interrupted` | session boundary, client restart, signal, shutdown |
| `infra_failed` | should have worked; crash, script bug, transient service |
| `env_blocked` | capability exists; a prerequisite, dependency, or access is missing |
| `env_unsupported` | the environment cannot express the required phenomenon |
| `resource_exceeded` | over the memory / CPU / storage / wall-clock envelope |
| `invalid` | ran, but the evidence does not answer the question |

| `research_outcome` | meaning |
|---|---|
| `confirmed` / `refuted` | asserts something about a hypothesis |
| `inconclusive` | evidence is valid; it does not settle the question |
| `informative_failure` | the mechanism failed, and the failure is the finding |
| `promising` | directional support; not yet a claim |
| `failed` | the attempt failed without information |
| `none` | nothing to report |

`NON_SCIENTIFIC_REFUTATION` fires when any non-scientific execution status is paired with
`confirmed` or `refuted`. That is the single most important constraint in the design: an
OOM, an unsupported SDK, or a killed session must never appear in `FINDINGS.md` as "the
mechanism does not work". If you hit it, the fix is to record the limitation, not to
reclassify the execution.

`confidence` (`low` / `moderate` / `high` / `certain`) is a third, independent axis. A
result can be `inconclusive` with `high` confidence — "we now know this experiment cannot
settle it" is a real and valuable finding.

## What counts as an iteration

```python
execution_status == "completed"
and research_outcome in {confirmed, refuted, inconclusive, informative_failure, promising}
and (hypotheses_differentiated != [] or belief_delta != "none")
```

Two decoys worth internalizing, because both look like progress and neither is:

- `infra_failed` + `refuted` + a differentiated hypothesis → **false**. The first clause
  fails, and the record is rejected outright anyway.
- `completed` + `inconclusive` + no differentiation + `belief_delta: none` → **false**.
  A valid run that taught nothing is not an iteration.

The field is derived and the tool rejects a supplied value that disagrees. It is an
auditability mechanism: it makes "I counted this run as progress" checkable against the
record's own fields. It does not make under-reporting impossible.

## Bounding the conclusion

Every conclusion carries the level that produced it. Write the bound into the record, not
into a summary:

- An E2 replay shows a mechanism beats its alternative **in replay**. It says nothing
  about closed-loop behavior.
- An E3 slice with a mock actuator can show the safety governor blocks a tampered
  command. It cannot show that the physical system is safe — the actuator dynamics are
  absent by construction.
- E4 shows behavior on the scenarios you chose. Whether the scenario suite represents the
  real distribution is an `evaluation-design` question, not an evidence-level question.

When the level is below what the question needed, the surrogate contract becomes
mandatory — see `surrogate-validity.md`.

## Multi-level promotion

```
Idea → Probe → Component → Partial stack / Subsystem
     → Vertical slice → System candidate → Promoted baseline
```

Each step does the minimum engineering needed to enter the next one. A probe that works
does not imply full TDD and a complete regression suite; that inference is how a working
research loop stalls.

Promotion happens when the evidence justifies stabilizing a mechanism, and the architect
agrees. The object of promotion is the validated mechanism, not the research branch.
Git-side mechanics are in `git-research-infrastructure.md`.
