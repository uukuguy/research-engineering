# Surrogate Validity

Mandatory when a conclusion rests on a surrogate, mock, replay, or reduced simulator.

A surrogate is not a weaker version of the real experiment. It is a different experiment
that answers a different question, and the whole job here is to state exactly which
question that is.

## When the contract is mandatory

The tool requires a `surrogate_contract` when either holds:

- `surrogate: true` on the record, or
- `evidence_level` ranks below `target_evidence_level`.

`target_evidence_level` is the level the question actually needed. `evidence_level` is
what you reached. When the second is lower, the gap is precisely the space in which a
conclusion can be overclaimed, and the contract is what closes it.

Without one, the write fails with `SURROGATE_CONTRACT_REQUIRED`. With a partial one, it
fails with `SURROGATE_CONTRACT_INCOMPLETE` naming the missing keys. Neither is a
formality to satisfy — a contract with empty fields is a claim that nothing was checked.

## The seven fields

```json
{
  "target_causal_claim": "discrete recovery release is too slow after trust recovers",
  "required_causal_features": [
    "real recovery state machine with its actual dwell and hysteresis",
    "trust signal recovering on the real timescale",
    "release condition evaluated on real state, not on a smoothed stand-in"
  ],
  "preserved_features": [
    "recovery state machine implementation, unmodified",
    "recorded trust trajectory, replayed at original rate",
    "case ordering from the recovery-12 suite"
  ],
  "missing_or_distorted_features": [
    "actuator dynamics",
    "closed-loop feedback from motion back into perception"
  ],
  "allowed_conclusions": [
    "the release condition, given this trust trajectory, holds longer than the mechanism under test requires",
    "the candidate mechanism changes release timing on this replay"
  ],
  "forbidden_conclusions": [
    "the closed-loop robot does not oscillate",
    "the mechanism is physically safe",
    "the mechanism generalizes beyond these recorded cases"
  ],
  "verdict": "VALID_SURROGATE"
}
```

The three lists that matter most are `required_causal_features`,
`missing_or_distorted_features`, and `forbidden_conclusions`. The first says what the
claim needs. The second says what is absent. The third says what a reader will be tempted
to infer anyway. If a required causal feature appears in the missing list, the verdict is
`EVIDENCE_INVALID` — not a weaker conclusion, an invalid one.

## The verdict

```
VALID_SURROGATE   the preserved features carry the claim; the boundary is stated
EVIDENCE_INVALID  a required causal feature is missing; the question is not answered
```

`EVIDENCE_INVALID` is a hard stop on assertion. A record with
`verdict: EVIDENCE_INVALID` and `research_outcome` of `confirmed` or `refuted` is
rejected (`INVALID_SURROGATE_ASSERTS_CONCLUSION`). Downgrade to `inconclusive` and record
the limitation instead. "We ran something and it did not answer the question" is a valid
and useful record. "We ran something and therefore the mechanism fails" is not.

Note what `EVIDENCE_INVALID` shares with `ENV_UNSUPPORTED`: neither is evidence against a
hypothesis. The difference is where the failure sits — `ENV_UNSUPPORTED` means the
environment cannot express the phenomenon at all, `EVIDENCE_INVALID` means a substitute
ran but dropped the feature that made the question meaningful.

## Two worked calls

**Valid.** Recorded trust trajectories replayed through the *unmodified* recovery state
machine. This can establish that the discrete release condition holds longer than
necessary after trust recovers, and can compare release policies against each other on
those trajectories. It cannot establish that a closed-loop robot has no physical
oscillation, because there is no dynamics in the loop. Same claim, different scope.

**Invalid.** A mock with no dynamics used to argue that the system is dynamically stable
under friction changes. Friction change *is* the causal feature; without it the surrogate
has removed the thing being tested. The correct record is `EVIDENCE_INVALID` with
`research_outcome: inconclusive` and a limitation naming the absent dynamics.

The test is one question: **if I removed this preserved feature, would the claim still be
testable?** If yes, it is a convenience, and it belongs in `preserved_features` honestly.
If no, it is a required causal feature, and its absence is `EVIDENCE_INVALID`.

## Predicate language

`invalidated_if` uses a deliberately tiny language. It has no expression engine, no `and`,
no `or`, no parentheses, and no negation of a compound.

```
predicate := PATH ( OP LITERAL | "changed" )
PATH      := ("env" | "inputs" | "code") "." KEY ("." KEY)*
OP        := == != < <= > >= in not_in
```

```json
"invalidated_if": [
  "env.sim_physics_hz != 30",
  "inputs.replay_suite changed",
  "evaluator.version != eval-v3",
  "env.inference_backend in [\"tensorrt\", \"onnxruntime\"]"
]
```

Rules:

- A list is a **conjunction**. If you need a disjunction, that is two evidence records —
  which is usually the more honest model anyway.
- A bare trailing `changed` is unary: it compares the value now against the value recorded
  when the evidence was written. It is the form to default to; hard-coding
  `!= recovery-12@sha256:...` is easier to get wrong and ages badly.
- A malformed predicate is a hard error at write time (`PREDICATE_SYNTAX`), not a silent
  no-op. That is the point: a predicate that parsed is a predicate that means something.
- Numeric comparison is numeric even when one side was written as a string, so a probe
  emitting `"30"` still matches an author writing `30`.
- Evaluation fails **open**. A path absent from the current fingerprint yields
  `UNRESOLVED`, which invalidates nothing and must be reported. Treating "could not check"
  as "still valid" hides staleness; treating it as "invalid" trains everyone to ignore
  the output.

## Writing it well

- Name the claim, not the topic. "discrete recovery release is too slow" is a claim.
  "recovery" is not.
- Put the tempting overclaim in `forbidden_conclusions` in the words a reader would
  actually use.
- Keep the boundaries short enough to be read. A contract nobody reads protects nothing.
- When the surrogate later gets upgraded — a replay becomes a slice, a slice becomes a
  full episode — do not retro-edit the old record. Write new evidence. Raw evidence is
  append-only, and the old record's bounded conclusion remains true for the level it
  reached.
