# Evaluation Design

Load when no evaluator exists, or when a local metric rises while E4/E5 or the architect's
observation falls.

"How do we know this is better?" is a technical research problem, and a missing or
untrustworthy evaluation surface is a research problem — not a licence to optimize a bad
metric. A metric that improves while representative system behavior degrades is a signal
to investigate the evaluator.

## Triggers

- no local evaluator exists yet;
- the official evaluator is sparse, hidden, expensive, or rate-limited;
- local metrics disagree with E4/E5 results or with architect-observed behavior;
- a qualitative observation needs an operational measure;
- moving from E1/E2 to E3/E4 requires representative scenarios;
- evaluator leakage, reward hacking, or proxy overfit is plausible.

The architect's sentence "the answers always seem to over-rely on the first document" is
one of these triggers. The response is to build a citation-coverage or context-attention
probe, not to start editing prompts. Without the probe there is no way to tell whether a
prompt change helped, and no way to tell when the problem is fixed.

## Method

1. State the real objective or rubric, and the decision this evaluation has to support.
2. Identify the observable behaviors and the failure/success dimensions.
3. Propose the minimum set of metrics and qualitative signals that discriminate the
   current question. Not the maximum set that could be computed.
4. Define representative slices and scenarios, clean controls, and hard negatives.
5. Separate development and tuning surfaces from holdout and verifier truth where
   feasible.
6. State the proxy's limitations and the obvious gaming and leakage paths.
7. Build the smallest evaluator, probe, or scenario surface that works, and run
   calibration cases.
8. Compare against E4/E5 results or architect observations where available.
9. Record what conclusions this surface may and may not support.

## Evaluation validity contract

For each important evaluation surface, state:

```
target objective
measured observables
known blind spots
data / scenario provenance
tuning vs holdout separation
gaming / leakage risks
calibration evidence
current highest justified evidence level
```

The last one matters most for how the surface may be cited. A local proxy calibrated
against nothing is an E1 artifact. A local proxy that has been checked against a set of E4
episodes and a handful of architect observations is much stronger, and it should say which
comparison produced that.

## Do not promote a scalar proxy into the real objective

This is the central failure. It happens gradually: a convenient metric is adopted, results
improve against it, and at some point the metric stops being a proxy and starts being the
goal.

Signs it has happened:

- the metric improves monotonically while E4 behavior is flat or worse;
- experiments are being selected because they move the metric, not because they address
  the uncertainty;
- a caveat that used to accompany the number ("this does not capture the stop-go
  oscillation") has disappeared from the reports;
- an architect observation contradicts the metric and the metric wins by default.

When the architect says "cases 31/37/42 look like stop-go oscillation and the metrics do
not capture it", that is the evaluator being told it has a blind spot. The correct response
is to build the missing observable — state transition frequency, dwell time — and keep the
human observation in the ledger alongside it, not to explain the observation away.

## Scenarios and holdouts

- Representative slices, not the easy middle. The cases that matter are often the awkward
  ends of the distribution.
- Clean controls and hard benign negatives in the same suite, so that a mechanism that
  simply fires more often cannot look better.
- Keep generated adversarial scenarios out of the tuning set. Tuning against cases
  generated to break the system converts a red-team suite into an overfit surface.
- Development and holdout separation wherever it is feasible, **at the level the claim is
  actually being made at**. A comparative claim starts at E2, and E2/E3 is where proxy
  overfit is manufactured: the metric is cheap enough to optimize against and has never
  been checked against the behaviour it stands for. Separation is not an E4 concern that
  arrives late — by then the overfit has already happened.

  | Level | Separation that makes the claim honest |
  |---|---|
  | E0/E1 | none. A feasibility spike and a visualization compare nothing. |
  | E2/E3 | frozen replay snapshot, hashed, with the dev/holdout split read-only to the candidate. |
  | E4 | a held-out slice the candidate is not tuned against. |
  | E5 | the official judge. |

  At E2/E3 the hash matters as much as the split. Without it, "the same replay" is an
  assumption rather than a fact, and a metric that moved cannot be attributed to the
  candidate instead of to the inputs having shifted underneath it. The point throughout is
  that the candidate can be optimized hard against one surface while another stays
  independent of it.

## Comparability

If evaluator or metric semantics change materially, the change is an environment change.
Mark it, and rebaseline anchor evidence before attributing any delta to the system:

```bash
python3 tools/researchlog env record research/env-changes/ENV-CHG-006.json
python3 tools/researchlog env query research/env-changes/ENV-CHG-006.json
```

`env query` returns the evidence whose `invalidated_if` predicates the change satisfies.
An evaluator version bump is exactly the kind of thing an evidence record should have
declared: `"invalidated_if": ["evaluator.version != eval-v3"]`. See
`environment-feasibility.md § Comparability`.

## Trust tiers for the evaluator itself

The evaluation surface is code, and code that scores the candidate is worth protecting in
proportion to what depends on it:

| Tier | Mechanism |
|---|---|
| low | `BOUNDARIES.md` entry plus a hash — prevents accidental edits |
| medium | sibling checkout, a verify command a human owns |
| high | container or separate OS user, evaluator and holdout read-only |
| stronger | protected remote verifier, architect-controlled holdout |
| strongest | official judge credentials invisible to the agent |

A prompt-level instruction not to modify the evaluator is not protection. If the claim
being made depends on the evaluator being untouched, it needs an out-of-band control —
file permissions, a separate checkout, a separate user, or a judge the agent cannot read.

## Anti-patterns

| Symptom | What is happening |
|---|---|
| local metric up, E4 down | proxy overfit; investigate the evaluator, not the candidate |
| a new scalar adopted without calibration | an untested proxy is being treated as ground truth |
| all scenarios pass | the suite stopped being representative, or the hard cases moved to training |
| the evaluator's semantics changed and old results still compared | missing comparability mark and rebaseline |
| the candidate can read judge-only labels | leakage; isolate the truth surface |

## Output

An evaluation surface is a research subject in its own right: `subject.type:
"evaluation_surface"`. Its construction is an experiment like any other, with its own
`EXP-*` and `EV-*` records, and its calibration against E4/E5 or architect observation is
the evidence that justifies citing it.

Canonical evaluation records and state are English. A human-facing evaluation review is
Chinese, keeping metric, proxy, scenario, and verifier terms in their original English
form, and referencing canonical IDs rather than restating them.
