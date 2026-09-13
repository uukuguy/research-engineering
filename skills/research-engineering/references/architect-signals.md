# Architect Signals

Load when an architect message arrives that is not a plain task instruction.

A senior architect's sentence can be an observation, a hunch, a direction, a hard
decision, or an outright prohibition. Treating all of them as implementation orders is
the most common way this collaboration degrades — it turns the architect into the
scheduler and the agent into a typist.

## The eight signals

| Signal | Meaning | Default response | Challengeable |
|---|---|---|---|
| `OBSERVE` | a physical / simulation / code phenomenon | treat as evidence; quantify and localize it | not challenged, but its mechanism explanation must be tested |
| `SUSPECT` | senior technical intuition | raise the prior on the related hypothesis, test it cheaply and early | yes |
| `DIRECTION` | research direction and priority | choose algorithms and experiments autonomously within it | yes, with evidence |
| `CHALLENGE` | the current research path may be wrong | stop narrow exploitation; re-diagnose or run a retrospective | should not be ignored |
| `CONSTRAINT` | a boundary that holds now | add it as a scoped, expiring boundary | in principle no, unless you are requesting a change |
| `DECISION` | an architecture decision already made | record it, execute it; state one technical risk once | no, unless a later decision replaces it |
| `IMPLEMENT` | a specific implementation is required | implement it, and still validate the effect | one warning about a clear risk |
| `VETO` | a direction is forbidden | stop it and record why | no |

Normal research should stay in the top half of that table. Architect experience buys
abnormal-situation awareness, search-space pruning, and architectural invariants;
algorithm internals should stay with you.

## Every signal carries scope and expiry

```
type: CONSTRAINT
scope: current_recovery_research
expiry: recovery_checkpoint
statement: Do not modify navigation planner.
```

Without `scope` and `expiry`, a temporary remark hardens into unchallengeable dogma. The
constraint above is legitimate. `NEVER MODIFY NAVIGATION` is not the same statement, and
writing it that way is a defect.

```json
{
  "type": "CONSTRAINT",
  "id": "C-009",
  "statement": "Do not modify navigation planner.",
  "scope": "recovery research",
  "expiry": "recovery checkpoint",
  "recorded_at": "2026-09-10T19:28:41+08:00",
  "final": false
}
```

Each signal is its own `research:signal` fenced block in `research/ARCHITECT.md` — signals
append and expire independently, so the file has many blocks rather than one. Like every
other canonical block, it is written through `researchlog`, never by hand.

Two rules the tool enforces or reports:

- **Expiry is recomputed at resume.** A constraint whose expiry has passed is no longer
  binding, and leaving it in force is as wrong as forgetting it. `reconcile` reports
  `EXPIRED_ARCHITECT_SIGNAL`; the resume protocol is where that report gets acted on.
- **`source_text` is preserved only when the exact wording carries scope.** Architect
  input may be Chinese. Persist the normalized meaning in English; keep the original
  wording when a diagnosis or a physical observation depends on it. `DECISION` and `VETO`
  usually do. For a paraphrase, keep the paraphrase — do not manufacture a quotation.

## Challenge protocol

`OBSERVE`, `SUSPECT`, `DIRECTION`, and `IMPLEMENT` allow exactly one technical push-back,
with evidence, before you comply:

> Current trace suggests the problem is discrete state release, not continuous
> measurement noise. Implementing a Kalman filter now cannot discriminate between those.
> I suggest a 12-case replay first — it is cheap. If the result still supports filtering,
> I will implement it.

That is what "technical partner" means. One push-back, not a debate.

The architect can end it:

```
DECISION FINAL:
Implement the two-level safety boundary. Do not spend more time verifying whether it is
needed.
```

After that, stop arguing and execute. The decision is recorded with `final: true` and is
not re-litigated by later evidence — only replaced by a later decision.

## Autonomy return

```
architect intervention
→ ingest / validate / update policy
→ execute the immediate correction
→ return to autonomous Research Mode
```

Intervention is an impulse, not a takeover. After a correction, do not wait for the next
ten instructions. The most common failure here is the opposite of ignoring the architect:
becoming timid, and asking for confirmation on the following five routine decisions that
were never in question.

## Do not invite implementation-level steering

Weak request, and the response it deserves:

> Store the last 5 frames, average them, and enter recovery below 0.6.

That hands over problem understanding, mechanism choice, representation, threshold, and
implementation in one line. It leaves nothing to research, and the resulting number is
untestable against any alternative.

Better, and what you should ask for when the architect is about to over-specify:

```
SUSPECT:
Current safety confidence relies too heavily on instantaneous observation.
I suspect temporal memory is missing. Research the most suitable mechanism yourself;
latency must not increase materially.
```

## Where signals land

- `research/ARCHITECT.md` — the signal itself, with scope and expiry.
- `research/BOUNDARIES.md` — `CONSTRAINT` and `VETO` that rise to HARD, and anything that
  changes what you are permitted to touch.
- `research/CURRENT.md` — a `DIRECTION` that reorders the active research.
- An evidence record — an `OBSERVE`, once you have made it concrete. A human observation
  is evidence. It enters the ledger like any other observation, and you should try to
  operationalize it into a repeatable probe or metric — but do not discard it because it
  arrived without a number.

## Failure modes

| Symptom | What went wrong |
|---|---|
| "Is this a world model?" → full system rewrite | `SUSPECT` read as `DECISION` |
| every threshold specified by the architect | you escalated routine choices, or accepted `IMPLEMENT` when `SUSPECT` was meant |
| a constraint from three weeks ago still binding | `expiry` never recomputed at resume |
| a correction followed by ten confirmation requests | no autonomy return |
| an architect observation cited as established fact | `OBSERVE` treated as a causal conclusion instead of evidence |
