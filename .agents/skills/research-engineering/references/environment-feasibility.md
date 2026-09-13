# Environment Feasibility

Load when the desired evidence cannot be produced by the current environment — when an
`ENV_BLOCKED`, `ENV_UNSUPPORTED`, or `RESOURCE_EXCEEDED` classification is on the table.

The research environment is not infrastructure. It determines which questions can be
answered, at what strength, with what credibility. Track it as a first-class object:
System Maturity (what exists), Evidence Maturity (how reliably we know it), and Research
Environment Maturity (what we can verify here) are three independent axes and never
collapse into one completion percentage.

## Infeasibility is never evidence against a hypothesis

| State | Precise meaning | Weakens a hypothesis? |
|---|---|---|
| `INFRA_FAILED` | this run should have worked here; crash, script bug, or transient service failure produced no valid evidence | no |
| `ENV_BLOCKED` | the environment supports it in principle; a dependency, config, permission, service, or credential is missing | no |
| `ENV_UNSUPPORTED` | the current simulator / SDK / research surface cannot express the phenomenon at all | no |
| `RESOURCE_EXCEEDED` | the design exceeds the memory, CPU, storage, wall-clock, or budget envelope | no |
| `EVIDENCE_INVALID` | a substitute runs, but does not preserve the causal feature the question needs | no |
| `SCIENTIFIC_NEGATIVE` | valid environment, valid evidence, the question is answered, and the mechanism genuinely did not work | **yes** |

Only `SCIENTIFIC_NEGATIVE` may weaken a hypothesis. The tool enforces this: pairing
`env_unsupported` (or any other non-scientific execution status) with `refuted` or
`confirmed` is a hard error, `NON_SCIENTIFIC_REFUTATION`. If you hit that error, the
record is wrong, not the rule.

The consequence to internalize: an OOM, a missing SDK feature, or a killed session must
never reach `FINDINGS.md` as a durable belief that an algorithm does not work.

## The state machine

Infeasibility is not a stopping state, and it is not an automatic escalation either.

```
research question / hypothesis
        ↓
desired causal evidence
        ↓
can this environment produce VALID evidence?
       / \
     yes  no
      │    │
      │    ├─ classify the infeasibility
      │    ├─ reshape execution
      │    ├─ decompose the question
      │    ├─ drop to a lower level via a valid surrogate
      │    ├─ build a harness / instrumentation
      │    ├─ upgrade the environment if the leverage is high
      │    └─ escalate only across a policy / resource boundary
      ▼
     run
        ↓
bound the conclusion to the level actually reached
        ↓
resume research
```

The governing rule: **seek the closest valid evidence, not merely the easiest runnable
substitute.** "This mock runs" is not the criterion. "This mock preserves the causal
feature the claim depends on" is.

Whether a reduced surface is valid is a `surrogate-validity.md` question. Do not answer
it here by intuition.

## Worked example — control tampering

The competition rubric scores post-planner control-channel tampering. The simulator can
inject LiDAR and camera attacks but cannot corrupt commands between the planner and the
actuator.

Wrong responses: record the experiment as failed; or escalate immediately for a simulator
plugin; or declare the safety boundary unnecessary because it cannot be tested.

Right response:

```
Desired E4 evidence unavailable
→ mark ENV_UNSUPPORTED, record it in ENVIRONMENT.md
→ identify the causal feature that must be preserved: command integrity across the
  planner→actuator boundary, with timing and ordering intact
→ build an E2 replay shim: planner command → tamper → safety gate
→ extend to an E3 partial stack with the real planner and a mock actuator
→ write the limitation into the evidence record: no actuator dynamics, so no
  physical-safety claim
→ continue research
```

Escalate only if control-integrity becomes the dominant score ceiling *and* closing it
requires a simulator plugin, new hardware, or new permissions — that is an environment
investment decision, and it is the architect's.

## Environment investment

`harness`, `instrumentation`, and `evaluation_surface` are research subjects. A thin
instrument that unlocks twenty future experiments is worth building before running the
twenty-first.

```
Environment investment value
≈ future research unlocked × expected reuse ÷ implementation cost
```

No formal scoring required. A 30-minute replay converter that unblocks a whole direction:
build it now, no approval needed. Two days rewriting a simulator for one low-probability
idea: that is an investment decision.

You may build low-cost research infrastructure inside the FREE and PROVISIONAL scopes
without asking. Replay converters, trace instrumentation, small attack injectors, local
adapters, and disposable mocks are ordinary work, not requests. Escalate only for new
hardware, licenses, paid APIs, official credentials, physical robots, substantial
simulator surgery, or a HARD boundary change.

## Comparability

More dangerous than "the experiment will not run" is "the experiment runs and the number
looks better". Environment drift is the confound that most often gets attributed to the
algorithm.

Material changes include: simulator or physics engine version; physics timestep / tick
rate; sensor model, noise, or randomization distribution; dataset or replay snapshot;
model checkpoint or external API version; inference backend, quantization, or compiler
mode; evaluator implementation or metric semantics; hardware, when latency or resource
metrics are part of the conclusion.

```
COMPATIBLE     direct comparison allowed
REBASELINED    comparison allowed after rerunning anchor baselines
INCOMPARABLE   do not attribute a cross-environment delta to the mechanism
```

After a material change, rerun a few anchor baselines — marked with `"anchor": true` in
their evidence records — rather than a full regression. `researchlog snapshot` records
the compact fingerprint; you never paste a dependency dump into context.

## Invalidation closure

Each evidence record declares what must stay true for it to remain valid:

```json
"invalidated_if": [
  "env.sim_physics_hz != 30",
  "inputs.replay_suite changed",
  "evaluator.version != eval-v3"
]
```

This turns comparability from a judgement call into a lookup. When the environment
changes:

```bash
python3 tools/researchlog env record research/env-changes/ENV-CHG-004.json
python3 tools/researchlog env query research/env-changes/ENV-CHG-004.json
```

`env query` returns the invalidation closure: the evidence that said it depended on the
thing that changed. Predicate semantics (namespaces, operators, `changed`, the
no-`and`/`or` rule, `UNRESOLVED` fail-open) are in `surrogate-validity.md § Predicate
language` — the tool's `PREDICATE_SYNTAX` error rejects a malformed predicate at write
time, so a predicate that parsed is a predicate that means something.

`UNRESOLVED` — a path absent from the current fingerprint — does not invalidate anything
and must be reported, not swallowed. Failing open avoids crying wolf; reporting avoids
hiding real staleness.

## `ENVIRONMENT.md` lifecycle

Update it only when one of these happens:

1. a previously unknown capability or limitation is discovered;
2. a new reusable harness or adapter changes the evidence level obtainable;
3. a material environment change affects comparability;
4. a capability moves between blocked / unsupported and available.

Each entry should carry `verified_by: EV-...`. Six weeks later, the question "where did we
learn that control tampering is unsupported here?" should be a lookup, not a memory.

The capability map is the part worth keeping current:

```markdown
| Capability | Highest valid evidence | Status | Verified by |
|---|---|---|---|
| vision attack | E4 | available | EV-... |
| lidar attack | E4 | available | EV-... |
| control tampering | E2/E3 | replay/partial only | EV-... |
| real robot | E5 | unavailable | external constraint |
```

Its `research:environment` block is written through `researchlog`; the prose around it is
yours to maintain, in English.
