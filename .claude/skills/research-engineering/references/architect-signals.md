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

## The signal contract

```
type: CONSTRAINT
scope: current_recovery_research
expiry: recovery_checkpoint
statement: Do not modify navigation planner.
source_text: 导航 planner 先别改，等复盘完再评估。
```

```json
{
  "id": "C-009",
  "type": "CONSTRAINT",
  "statement": "Do not modify navigation planner.",
  "scope": "recovery research",
  "expiry": "recovery checkpoint",
  "source_text": "导航 planner 先别改，等复盘完再评估。",
  "created_at": "2026-09-10T19:28:41+08:00",
  "active": true
}
```

- **`type`** — required, one of the eight above. `DECISION FINAL:` is how the architect
  writes a non-challengeable decision in chat; what you record is `DECISION` with
  `final: true`. It is not a ninth type, and writing it as one is reported as
  `SIGNAL_TYPE_UNKNOWN`.
- **`scope` and `expiry`** — required on a `CONSTRAINT`. Without them a temporary remark
  hardens into unchallengeable dogma: the constraint above is legitimate, and
  `NEVER MODIFY NAVIGATION` is not the same statement. `expiry` takes either an ISO 8601
  timestamp, which `reconcile` enforces at resume, or free text such as
  `recovery checkpoint`, which is a promise you keep and the tool deliberately does not
  evaluate.
- **`source_text`** — required for `CONSTRAINT`, `DECISION`, and `VETO`; see below.
- **`active`** — set `false` when the signal lapses or is superseded. An expired signal is
  no longer steering and does not belong in `ARCHITECT.md` as live state.

Each signal is its own `research:signal` fenced block in `research/ARCHITECT.md` — signals
append and expire independently, so the file has many blocks rather than one. There is **no
`researchlog` command for signals**: append the block by hand, and let `validate` and
`reconcile` check it. Both report a malformed block rather than skipping it, so the
hand-edit is audited rather than merely trusted.

The design document's §5.2 sketches the type field as `strength`. The field is `type`
everywhere in the tool and in the templates; `strength` was an earlier name for it.

Two rules the tool enforces or reports:

- **Expiry is recomputed at resume.** A constraint whose expiry has passed is no longer
  binding, and leaving it in force is as wrong as forgetting it. `reconcile` reports
  `EXPIRED_ARCHITECT_SIGNAL`; the resume protocol is where that report gets acted on.
- **`source_text` is mandatory for `CONSTRAINT`, `DECISION`, and `VETO`** — a `DECISION`
  with `final: true` included, since finality is a reason to keep the wording, not a reason
  to drop it. The wording of a boundary *is* its scope. Architect input may be Chinese, so
  the English rendering goes in `statement` and the original sentence is kept verbatim in
  `source_text` — both, always, for these three types. Paraphrasing a boundary into English
  and discarding the original is not translation: "先别改，等复盘完再评估" recorded as
  "do not modify the navigation planner" has silently lost its time box and become
  permanent doctrine. That is the one dispute a later session cannot reconstruct. If what
  you were given is a paraphrase rather than a sentence you may quote, keep the paraphrase
  as `source_text`; never manufacture a quotation. `validate` and `reconcile` both report
  `SIGNAL_SOURCE_TEXT_REQUIRED`.

## Echo back before you record a boundary

`CONSTRAINT`, `DECISION` (including `final: true`), and `VETO` are recorded and executed,
not argued. That is exactly what makes the recording itself the risk: you choose the type,
the scope, the expiry, and the English rendering, and every one of those choices can widen
what was actually said. A `VETO` softened into a `CONSTRAINT` is a silent change, and so is
a constraint whose expiry quietly disappears.

So for these four types, state back what you are about to record **before** acting on it:

> Recording as `CONSTRAINT`, scope `current_recovery_research`, expiry
> `recovery_checkpoint`:
> *"导航 planner 先别改，等复盘完再评估。"* → `statement`: "Do not modify the navigation
> planner." One risk: the original ties this to the retrospective, the rendering reads as
> unconditional.

Read the type, the `statement`, the `scope`, the `expiry`, and the retained `source_text`
back together, in one message. Then execute. Silence is assent — this is not a request for
permission and not a second guess about whether to comply.

If you cannot tell a `VETO` from a `CONSTRAINT`, that is a question about the type and it
is worth asking, because the two differ in whether you may ever ask to amend: guessing
changes the answer. Echoing is for the four boundary types only — the challengeable
signals have the protocol below, and routine research decisions stay autonomous.

### When the architect answered a question you wrote

Asking is often right — a `DECISION` that changes direction or commits resource is the
architect's to make, and a multiple-choice question is a cheap way to put it to them. But
the **wording** of a chosen option is yours, not theirs. Recording it as `source_text`
satisfies the letter of the requirement and defeats the point: the field exists to preserve
*the architect's* phrasing against your normalisation, and an option you authored has
already been through it.

So after a selection, `source_text` holds the architect's own words — ask for them in a
sentence if the selection did not include any ("say it in your own words and I will record
that verbatim"), and if there really are none, leave `source_text` out and let
`SIGNAL_SOURCE_TEXT_REQUIRED` report it rather than filling the field with your own text.
The `statement` can still be your rendering; the difference between the two fields is the
whole reason both exist.

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
| a `VETO` that quietly became a `CONSTRAINT`, or a bounded constraint that lost its expiry | no echo-back before recording a boundary |
| a correction followed by ten confirmation requests | no autonomy return |
| an architect observation cited as established fact | `OBSERVE` treated as a causal conclusion instead of evidence |
