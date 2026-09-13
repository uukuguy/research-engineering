# Retrospective

Load when the last 5 counted iterations all carry `belief_delta: none`, or at a phase
boundary.

This is the slow loop. The fast loop asks "what is the next experiment". The
retrospective asks whether the experiments being run are the right ones at all.

## Triggers

- roughly 8–15 counted evidence iterations since the last one;
- 5 or more similar changes with no substantive progress;
- the local metric and the physical or simulation observation start to disagree;
- a new piece of evidence shakes a current architectural assumption;
- the agent has been doing exploitation inside one parameter or mechanism family;
- the dominant failure has moved and the research has not followed it.

The first of those is a scheduled check. The rest are alarms.

## The questions

```
What do we actually know?
Which of our beliefs are not well supported?
Which provisional architectural assumption has hardened into dogma?
Is the research budget concentrated in the wrong module?
Which failure carries the most information?
Should we exploit further, explore a new mechanism, or understand a failure first?
```

Answer them from the ledger, not from memory. `FINDINGS.md` is the compressed answer; the
question here is whether it is still true.

## What a plateau looks like

The signature is a long run of experiments that are variations on one mechanism, each
producing a small number and no change in belief.

```
decay → smoothing → threshold → another smoothing → tuning the smoothing
```

Twelve consecutive trust-score tuning experiments that all assume the current trust
architecture is correct is the canonical case. The architecture assumption was never
proven, and no amount of tuning inside it can reveal that.

When you see this pattern, the correct response is not a better sweep. It is to reopen the
assumption and re-derive why the failure happens — possibly via `diagnosis.md`, possibly
via a new architecture spike.

A plateau is also a signal the search space has narrowed below the width of the problem.
Check specifically:

- is there only one live mechanism family? Then the frontier is gone and one of the
  alternatives needs rebuilding;
- has a proxy replaced the real objective? An E1 metric improving while the simulation
  worsens is the classic form, and the response is `evaluation-design.md`, not more tuning;
- has a provisional decision become an axiom? Provisional decisions may be overturned by
  evidence, and a retrospective is where you check whether anyone still remembers they are
  provisional.

## Reopening the search space

The retrospective is where external knowledge is worth its cost — when the mechanism
family itself is unclear, not when a parameter needs a value.

1. State the technical unknown precisely. Not "how do we do safety", but "what
   representation carries trust across sensors with different failure modes".
2. Search papers, source, benchmarks, and issue trackers for that unknown. Not "top ten
   approaches to X".
3. Prefer something runnable. A reference implementation you can execute beats a paper you
   can only cite.
4. Extract a testable mechanism. Do not adopt a framework.
5. End with 2–4 directions worth an executable confrontation, and pick one.
6. Return to running. Literature research that does not end in an experiment has not
   finished.

## Branch diversity

When several genuinely distinct families are live, preserve them explicitly in
`CURRENT.md § Current frontier`. Diversity is cheap to maintain and expensive to
reconstruct — a family that was deleted three weeks ago has to be rebuilt from scratch.

Stagnation detection and cross-branch recombination are worth borrowing as habits: when
one branch stalls, the useful move is often to combine a mechanism from another branch
with the stalled one rather than to push harder on either. Do not import a full
ML-evolution runtime to get this; a paragraph in `CURRENT.md` and one honest comparison
run is the V0 form.

## What the retrospective writes

`FINDINGS.md` and `CURRENT.md`. Never raw evidence.

- Beliefs that survive re-examination stay, with their evidence IDs.
- Beliefs that turn out to rest on a single weak record are downgraded to `Provisional`.
- Beliefs whose evidence has been invalidated by an environment change are re-checked
  against `env query` output before anything else happens.
- A superseded belief is marked `Superseded` with `superseded_by` and a reason
  (`FINDING_SUPERSEDED_WITHOUT_REPLACEMENT` and `..._WITHOUT_REASON` are errors, not
  warnings). Do not delete it — a belief that was once held and replaced is information
  about how the system was reasoned about.
- `CURRENT.md` gets a rewritten working model, revised uncertainties, and the frontier.

A retrospective that produces no change to `FINDINGS.md` is a legitimate outcome. It is
also worth being suspicious of: run it twice in a row with no change and the retrospective
has probably become ceremony.

## Research budget

The retrospective is where the allocation gets questioned:

- is the current uncertainty still the highest-value one?
- is the effort proportional to the score or risk it addresses?
- which failure, if understood, would unblock the most downstream work?
- is a harness or instrumentation investment now worth more than another experiment?

Sometimes the right output is "stop experimenting and build the instrument". A replay
converter that unblocks twenty future experiments is a better use of the next two hours
than experiment number thirteen in a stalled family.

## Escalation

The retrospective is also where a real escalation becomes visible: a HARD boundary that
is blocking research, a strategic tradeoff that cannot be resolved technically, an
environment investment requiring major commitment. Those go to the architect, with the
retrospective's evidence behind them.

A plateau by itself is not an escalation. It is a research problem, and the retrospective
is the instrument for it.

## Recording

The retrospective is not itself an evidence record — it produces no new empirical
observation. Its outputs are the updated findings and working model. If it triggers a new
architecture spike or a discriminating experiment, that experiment gets its own `EXP-*`
and its own record as usual.

If a retrospective concludes that a belief was wrong, the record of that belief's
original evidence does not change. Raw evidence is append-only; what changed is the belief
drawn from it, and that lives in `FINDINGS.md`.
