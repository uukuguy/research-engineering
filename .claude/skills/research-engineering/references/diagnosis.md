# Diagnosis

Load when a failure has two or more plausible layers, or three similar fixes have failed.

Applies mainly from E3 onward, where real components interact and a failure can originate
anywhere along the path.

Triggers:

- several layers could each explain the failure;
- multiple fixes have been attempted and it still fails;
- timing, recovery, or state propagation is involved;
- similar cases sometimes succeed and sometimes fail;
- a safety top event has several AND/OR conditions.

The output is **not a fix**. It is a located divergence plus the evidence that located it.

## Method routing

| Situation | Method |
|---|---|
| a control/data path with several stages | boundary instrumentation, backward trace from the symptom |
| a top event with several contributing conditions | fault tree — enumerate the AND/OR structure before testing branches |
| a comparison with a working reference | compare working vs broken, diff the whole path not just the suspect stage |
| a decision between explanations that predict different observations | discriminating experiment (`experiment-review.md`) |
| a nondeterministic failure | replay with a fixed seed, then vary one factor at a time |

Three habits carry most of the value, and all three are inherited from ordinary
systematic debugging: **reproduce before guessing**, **instrument at component
boundaries**, and **trace backward from the symptom to the first divergence**.

## Locate the first divergence

Walk the data and control path from the input forward, and at every stage record the
actual values — not lengths, counts, schema summaries, or exit codes. The first stage
where the expected value fails to appear is the divergence.

```
perception confidence  →  fusion  →  safety state  →  controller command
   recovers at t+1.2s      ok         still held        stop
                                     at t+4.8s
```

That trace says the divergence is in the safety-state release, not in perception. The
competing story — "perception did not recover" — is refuted by the first column, and it
would have been the intuitive guess.

If the trace only stores summaries, **fix the trace to store values first**, then re-run.
Diagnosing from a summary is guessing with extra steps.

### Earliest preventable divergence

The first divergence is where behavior went wrong. The earliest **preventable**
divergence is the last point at which a reasonable check could have caught it. They are
usually different, and the second one is what tells you where to add a guard.

An agent failure may originate in the planner, or a guardrail may have detected the
problem while the action layer executed anyway. The first divergence is upstream; the
earliest preventable one is the action layer that ignored a working signal.

## Competing hypotheses

Every diagnosis maintains more than one until the evidence separates them.

```
first divergence
+ earliest preventable divergence
+ competing hypotheses
+ supporting / contradicting evidence for each
+ the cheapest discriminating test
```

Record what each hypothesis predicts *differently*. Two hypotheses that predict the same
observation are one hypothesis until you find an observation that splits them.

`INCONCLUSIVE + high confidence` is an allowed and sometimes correct outcome. "We
established that these three layers are not the cause, and the remaining candidates cannot
be separated with the instruments we have" is a real result. The alternative — picking the
most plausible story and proceeding as if it were established — is how a wrong root cause
gets baked into the next three weeks of work.

## Anti-patterns

| Symptom | What is happening |
|---|---|
| "tried several times, no improvement" | diagnosing the wrong link; the failure is upstream or downstream of the area being edited |
| "fixed A and B regressed" | a shared upstream cause; two symptoms of one divergence |
| results vary across runs | a nondeterministic factor is unmodeled — seed, ordering, timing, a cache |
| a plausible root cause found in one pass | the story arrived before the trace; go back and instrument |
| the trace stores counts and exit codes | the trace cannot answer the question it exists to answer |

**Do not** change prompts, thresholds, rules, data, or retry logic before the broken link
is located. A change made before the divergence is known converts a diagnosable failure
into an undiagnosable one, because now two things have changed.

## The three-strike rule

```
strike 1  diagnose the root cause, apply a targeted fix
strike 2  change the approach — different instrument, different method
strike 3  question the assumption the search is built on
after 3   stop and escalate to the architect with what has been ruled out
```

Never repeat the identical failing action. Each attempt's result is data; keep it.

## Worked shape

The competition run shows no collision but the robot stays stopped for 10–15 seconds after
the attack ends. The architect supplies the observation and a suspicion about recovery
state ownership.

```
reproduce      replay cases 31/37/42, confirm the stop-go pattern is stable
instrument     trace perception confidence, fusion output, safety state, controller
               command, with values at each stage
first div.     perception confidence recovers at t+1.2s; safety state holds until t+4.8s
earliest prev. the release condition, which had a signal available and did not act on it
hypotheses     H-037 release condition too slow
               H-039 recovery state ownership split between fusion and governor
discriminate   hold the release condition fixed, change only ownership
```

Note what the trace rules out: perception recovery, which was the first guess. And note
that the human observation — "it looks like stop-go oscillation, and the metrics do not
capture it" — enters the ledger as evidence in its own right. It is not a lesser input for
having arrived without a number; the right response is to operationalize it into a
repeatable metric (state transition frequency, dwell time) so the next occurrence is
measurable.

## Recording

A diagnosis produces evidence like any other experiment: `research_outcome: inconclusive`
when the cause is not separated, with `confidence` reflecting how much was ruled out, and
`limitations` naming what the instruments could not reach. Hypotheses that were eliminated
go in `contradicts`; the surviving ones in `supports` if the evidence genuinely favors
them.

The subsequent fix is a new experiment with its own `EXP-*` and its own evidence record.
Do not fold the fix into the diagnosis record — the diagnosis describes what was true
before the fix existed.
