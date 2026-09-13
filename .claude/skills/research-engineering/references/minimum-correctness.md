# Minimum Correctness Envelope

Load when a mutation touches a HARD boundary, a unit/coordinate/schema contract, or an
evaluator — or when a test is about to be added.

TDD is valuable in production engineering. Applied to every disposable hypothesis
mutation — RED-GREEN-REFACTOR, a unit test per new function, a plan, a full regression —
it collapses research throughput. This is not an argument against testing. It is a change
in what tests are for:

> Tests protect the credibility of the experiment, and the behavior already proven worth
> keeping. Nothing else.

## The five gates

| Gate | Question | Examples | When |
|---|---|---|---|
| **G0 Executability** | will this produce evidence at all? | syntax, imports, startup, no immediate crash, expected artifact appears | every empirical run |
| **G1 Boundary Integrity** | would a basic contract error invalidate the conclusion? | shape, schema, coordinate frame, units, timestamp, control range, API contract | whenever relevant — a few assertions |
| **G2 Research Validity** | does this evidence actually answer the question? | baseline and control present, correct data version, no obvious confound, provenance recorded | before any claim |
| **G3 Candidate Robustness** | does it still hold outside the motivating case? | clean guard cases, representative slice, a few repeats, latency and cost | only once promising |
| **G4 Integration Promotion** | is it worth becoming a stable platform? | clean-checkout reproduction, broader regression, key regressions, ablation, judge integrity | promotion or submission |

G4 is Integration Mode. It is not a gate that a Research Mode iteration passes through.

## Gates evolve with the evidence level

**E0** — confirm you are reading the right rules, SDK version, and source. Separate fact
from inference.

**E1** — the script executes. Look at one raw input by hand. Check shape, units,
coordinates, timestamps. State the probe's limits in the record.

**E2** — replay and config pinned. Control condition retained. Interface and output
semantics reproducible across two runs.

**E3** — every module marked real or mocked, explicitly. Cross-module boundary traces and
latency recorded, because the mocks are where the conclusion leaks.

**E4** — representative scenarios, clean cases, the safety or rubric vector, repeats and
seeds where the result is stochastic.

**E5** — judge isolation, submission budget respected, no tuning against hidden truth.

## Gate-2 is where most invalid evidence is caught

Two checks belong here that are easy to skip:

**Surrogate validity.** If any part of the path is a substitute, the surrogate contract is
mandatory and its verdict gates the outcome. An `EVIDENCE_INVALID` verdict cannot confirm
or refute. See `surrogate-validity.md`.

**Environment comparability.** A changed simulator tick rate, physics version, TensorRT
cache, CUDA kernel, model weight cache, or external API version can make a result look
better without anything improving. Before a comparative claim:

- were the runtime and environment identical for both arms?
- if the environment changed materially, was the anchor baseline rerun?
- is the environment delta recorded?
- are two incomparable results being attributed to the mechanism?

Do not paste a dependency dump into context. `researchlog snapshot` records a compact
fingerprint, and only a material delta earns a record:

```json
{
  "schema_version": "1.0",
  "kind": "environment_change",
  "change": "simulator physics 30Hz -> 60Hz",
  "comparability": "requires_rebaseline",
  "affected_capabilities": ["control_latency", "collision_dynamics"]
}
```

## The four tests worth keeping

1. **Hard boundary assertion** — coordinate frames, units, schema, safe action range.
   These are the errors that silently invalidate a conclusion rather than failing loudly.
2. **Experiment validity assertion** — data leakage, a wrong split, judge truth leaking
   into the candidate's input.
3. **High-value bug reproduction** — a bug that recurred more than once, locked by a
   test small enough that nobody resents it.
4. **Promoted mechanism regression** — Integration Mode only.

Everything else is optional. Transient helpers, throwaway parsers, and every function in
a probe do not get unit tests. A probe is expected to be deleted.

## What not to default to

- test-first for every mutation;
- a unit test per new function;
- a written plan before each experiment;
- full regression per iteration;
- production-level review of a disposable prototype;
- backward compatibility for a PROVISIONAL interface;
- refactoring code that is going to be thrown away;
- asking the architect to approve the next routine step.

## Gate-0 and Gate-1 in practice

```bash
# G0 — does it run at all, and did it produce the artifact it promised?
python3 research_probes/recovery/replay.py --cases recovery-12 --dry-run

# G1 — the few assertions that decide whether a result means anything
python3 -m unittest research_probes.recovery.tests.test_boundaries -v
```

A G1 check earns its place by the question "if this were wrong, would my conclusion be
wrong too?" Coordinate frame confusion, a millisecond/second mismatch, a control command
outside the safe range, and a schema mismatch all pass that test. A missing test for a
helper's edge case does not.

## Where stronger discipline belongs

Superpowers, GSD, selective TDD, and full regression are not deleted from this project.
They are relocated:

```
Research Mode
  ↓ promising mechanism
Promotion Gate
  ↓
Integration Mode
  ↓
planning / selective TDD / regression / review
  ↓
Stable baseline
  ↓
Research Mode
```

The engineering cost is paid once, on the mechanism that survived, instead of on every
mutation that did not. Applying it earlier is the single most common way a research loop
slows to a crawl while looking busy.
