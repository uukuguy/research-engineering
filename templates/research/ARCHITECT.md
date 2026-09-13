# Architect State

Currently-valid steering from the lead architect. Not a chat history: signals that have
expired or been superseded do not belong here.

Each signal is its own `research:signal` block, because signals are independent
entities that are added and expire on their own schedule. There is no `researchlog`
command for them: append the block by hand, and let `validate` and `reconcile` check it.
A malformed block is an error, not a silent skip.

## Signal types

| Type | Meaning | Default response | Challengeable |
|---|---|---|---|
| `OBSERVE` | A physical, simulation, or code phenomenon | Treat as evidence; quantify and localise it | No need — but verify the mechanism it implies |
| `SUSPECT` | Senior technical intuition | Raise the prior on related hypotheses; test cheaply | Yes |
| `DIRECTION` | Research direction or priority | Choose algorithms and experiments yourself | Yes, with evidence |
| `CHALLENGE` | The current research path may be wrong | Stop narrow exploitation; re-diagnose | Should not be ignored |
| `CONSTRAINT` | A current boundary | Obey within scope and expiry | Only by asking to amend |
| `DECISION` | An architecture decision already taken | Record and execute; state one material risk | No, until superseded |
| `IMPLEMENT` | Request for a specific implementation | Implement, but still validate the effect | One warning about obvious risk |
| `VETO` | A direction is forbidden | Stop it and record why | No |

`DECISION FINAL:` is not a ninth type. It is what the architect types in chat when the
decision is not open to challenge, and it is recorded as `DECISION` with `final: true`.

Normal research lives in the top half of that table. The architect's experience is most
valuable for anomaly sensing, search-space pruning, and architectural invariants —
algorithmic detail is better left to the agent.

## The signal contract

```json research:signal
{
  "id": "C-009",
  "type": "CONSTRAINT",
  "statement": "Do not modify the navigation planner.",
  "scope": "recovery research",
  "expiry": "recovery checkpoint",
  "source_text": "导航 planner 先别改，等复盘完再评估。",
  "created_at": "2026-09-10T19:28:41+08:00",
  "active": true
}
```

`type` is required and names the signal. A `CONSTRAINT` also requires `scope` and `expiry`:
a temporary remark that is never given an expiry becomes unchallengeable architecture by
accident, and those two fields are what stop that. `expiry` carries either an ISO 8601
timestamp, which `reconcile` enforces at resume, or free text such as
`recovery checkpoint`, which is a promise a human keeps and the tool deliberately does not
evaluate.

For `CONSTRAINT`, `DECISION`, and `VETO`, `source_text` is **required** — keep the
architect's original wording. Normalising "do not touch the planner's recovery branch"
into "do not modify the navigation planner" quietly changes the scope, and the
translation is exactly what a later dispute would turn on. `final: true` on a `DECISION`
marks it as not open to challenge.

`validate` and `reconcile` check this contract on every run.

## After a correction

An intervention is an impulse, not a takeover. Ingest it, execute the immediate
correction, update the research policy, and return to autonomous research. Do not wait
for the next ten instructions.
