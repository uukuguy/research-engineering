# Experiment Review

Load when a run just finished and two or more hypotheses are live.

The failure this file prevents is a beautiful causal story produced in one pass from a
single run. "The collision happened, so the LiDAR detector failed" is not an
interpretation, it is a guess wearing an interpretation's clothes. Review keeps
observation, comparison, interpretation, and decision in separate layers so they can be
checked one at a time.

## Four layers

```
OBSERVATION     what the run produced, stated without causes
COMPARISON      how it differs from the baseline, control, or prior run
INTERPRETATION  which hypotheses this supports or contradicts, and how strongly
DECISION        keep / modify / branch / discard / re-run with a better instrument
```

Write them in that order and do not let a later layer edit an earlier one. If the
observation section already explains why, the review has failed.

**Observation** carries values, not summaries. "Latency improved" is not an observation.
"`p95 stop_latency_ms` 210 → 180 across the 12 replay cases; case 31 unchanged at 240" is.
Traces that record lengths, counts, or exit codes instead of the values flowing through
them cannot support diagnosis later; fix the trace before re-running.

**Comparison** needs a control. An absolute number with no baseline, no clean case, or no
prior run is not a comparison, and a delta with no control is where confounds enter.

**Interpretation** names hypotheses by ID. It also names what the run cannot distinguish —
that list is usually longer than the list of what it settled.

**Decision** is one of `keep / modify / branch / discard`, plus the next experiment.

## The three axes

Record all three. They are independent, and collapsing them is the most damaging error
available in this file.

```json
{
  "execution_status": "completed",
  "research_outcome": "promising",
  "confidence": "moderate"
}
```

- `execution_status` — did the run do what it was supposed to do.
- `research_outcome` — what was learned about the hypothesis.
- `confidence` — how strongly.

An environment or infrastructure failure is not evidence about a hypothesis, and the tool
rejects the combination outright (`NON_SCIENTIFIC_REFUTATION`). See
`evidence-model.md § The two axes` for the full vocabularies.

`inconclusive` with `high` confidence is a legitimate and common result: the experiment
ran, and we now know with certainty that it cannot settle this question. That is worth
more than a `confirmed` at `low` confidence, and it is the correct record when a
discriminating experiment turns out not to discriminate.

## Does this count as an iteration

```python
execution_status == "completed"
and research_outcome in {confirmed, refuted, inconclusive, informative_failure, promising}
and (hypotheses_differentiated != [] or belief_delta != "none")
```

The block contract counts on this. A valid run that changed no belief is not progress, and
the tool rejects a hand-written count that disagrees (`EVIDENCE_ITERATION_COUNT_FALSE`,
`EVIDENCE_ITERATION_COUNT_DRIFT`).

## Competing hypotheses

When more than one mechanism could explain the observation, write them down before
choosing what to run. Each needs:

```
falsifiable claim       what would be observed if this is true
mechanism               why it would produce that observation
predictions             including predictions that differ from the rivals
falsifier               the observation that would kill it
cheapest discriminating evidence   the run that separates it from the strongest rival
rough cost
```

Rank them yourself and pick the next experiment. Handing A/B/C to the architect is not
collaboration, it is deferring the job.

The discriminating experiment is the one that separates two live hypotheses — not the
experiment that accumulates more support for the one you already favor. If a proposed run
would produce the same result under both, it is not worth running yet.

```
H-037  recovery release condition is too slow          predicted: release delay unchanged
                                                       under reduced oscillation
H-039  recovery state ownership is split incorrectly   predicted: release delay drops when
                                                       ownership is unified, even with the
                                                       same release condition
→ discriminating run: hold the release condition fixed, vary only ownership
```

## After a promising result

A mechanism that looks good is the moment to look for its counterexamples, not the moment
to declare it solved. Run these before promoting anything:

- extreme timing, and timing at the boundary of the designed range;
- slow drift and abrupt fault;
- intermittent behaviour, freeze, and delay;
- composition of several perturbations at once;
- an attack or disturbance during the recovery phase;
- hard benign negatives — clean cases that look like the failure;
- distribution shift;
- an attack with no obvious cross-modal disagreement.

Keep the clean controls in the same run. And generated adversarial scenarios must not
quietly become a training set: tuning against cases you generated to break the system is
how a red-team suite turns into an overfit surface. Hold them out, or regenerate.

## Recording

```bash
python3 tools/researchlog record --from-orphan EXP-0142   # prefills mechanical fields
```

```json
{
  "evidence_id": "EV-20260911T101530Z-a7f3",
  "experiment_id": "EXP-0142",
  "evidence_level": "E3",
  "target_evidence_level": "E4",
  "observations": [
    "case17 oscillation amplitude 0.42 -> 0.11 rad/s",
    "safe-stop latency unchanged at 180ms across all 12 cases",
    "case31 unchanged at 240ms"
  ],
  "measurements": {"oscillation_amplitude": 0.11, "stop_latency_ms": 180},
  "execution_status": "completed",
  "research_outcome": "promising",
  "confidence": "moderate",
  "hypothesis_ids": ["H-037", "H-039"],
  "hypotheses_differentiated": ["H-037"],
  "belief_delta": "refined",
  "supports": ["H-037"],
  "contradicts": [],
  "limitations": ["no actuator dynamics: mock controller in the E3 slice"],
  "invalidated_if": ["env.sim_physics_hz != 30", "inputs.replay_suite changed"]
}
```

`measurements` stays flat. `compare` computes common measurements between two records, and
that is only defined for a flat scalar map:

```bash
python3 tools/researchlog compare EV-20260911T101530Z-a7f3 EV-20260911T140200Z-b21c
```

## A run that failed well

```json
{
  "execution_status": "completed",
  "research_outcome": "informative_failure",
  "confidence": "high",
  "observations": [
    "attack onset raises the angular residual within 2 frames",
    "sparse clean scenes trigger the same residual on 31% of frames"
  ],
  "belief_delta": "refined",
  "limitations": ["unconditioned temporal deficit does not separate attack from legitimate sparsity"]
}
```

The correct conclusion is not "raise the threshold". It is: the missing-evidence signal
exists, and unconditioned temporal deficit cannot discriminate an attack from a legally
sparse scene. That is a finding, and it is worth more than a tuned number.

## Escalation

If the review cannot separate the hypotheses and the failure is complex — multiple
plausible layers, timing or state propagation involved, similar cases behaving
differently — that is a `diagnosis.md` trigger, not a reason to run more of the same
experiment.
