# Durable research routes and next-block selection

Read at an authorized block's entry/close, when a valuable alternative appears, or when
parking, switching or waking a line. A route is an application-relevant uncertainty or
mechanism family, not each experiment, TODO, Git branch, chat, or agent.

## One portfolio, existing evidence

CURRENT.research_routes is the canonical portfolio; absence in older projects means
unregistered, not no unresolved work. During an authorized block, register valuable
existing alternatives from CURRENT/architect signals/evidence, without inventing prior
work or marking an untested option rejected. No automatic migration on resume/status.
FINDINGS remains the conclusion store; route evidence references its existing EV records.
Use `routes` verbs, never hand-edit the JSON or overwrite the array with `current --set`.

Each route has a stable R-* ID, question, application value, priority with reason,
next cheap discriminating probe, resume point (code/artifact/branch when needed), evidence,
dependencies and alternatives, lifecycle state, wake condition, and transition history.
Dependencies mean genuinely necessary completed work; alternatives are competing choices,
not dependencies. Unrelated required components must not be framed as a winner-takes-all vote.

The stdlib CLI persists choices; it does not reason, prove a trigger true, schedule a model,
check scientific validity, or grant authority. The lead agent owns prioritization and is
the single CURRENT writer. Global ACTIVE still describes actual execution, not a second
portfolio. A route can stay active while a session/block is idle; active means focus.

## Small tool surface

Use the installed project's CLI prefix (`uv run python tools/re`), or this repository's
`python3 tools/researchlog`. Examples below omit that prefix; inspect `routes ACTION --help`
for flags rather than guessing syntax.

```
routes list
routes list --id R-collision
routes add --id R-collision --title "..." --question "..." --value "..." --next-probe "..." --resume-point "..." --priority 1 --reason "..."
routes update --id R-collision --evidence EV-... --next-probe "..." --resume-point "..." --reason "..."
routes park --id R-collision --reason "..." --wake-when "..."
routes block --id R-collision --reason "..." --wake-when "..."
routes wake --id R-collision --trigger "observed change" --evidence EV-... --reason "..."
routes activate --id R-collision --reason "..." --park-reason "..." --park-wake-when "..."
routes close --id R-collision --outcome completed --evidence EV-... --reason "..."
dashboard --route R-collision
```

States: queued (available to consider), active (current focus), parked (deliberately
deferred), blocked (no currently authorized feasible path), completed, rejected.
`wake` moves a dormant route to queued, not directly to execution; reopening closed work
requires evidence. `activate` parks the previous focus in the same CURRENT replacement,
requiring its reason and wake condition. It never erases the old probe/resume location.
Unknown references, missing EVs, dependency cycles and multiple active focuses are errors.

Before a lifecycle change, finish/record/reconcile the current execution and reach idle;
do not set idle just to bypass a refusal. Resolve running/pending jobs and the current
interrupted execution first. Historical terminal interruptions are preserved, not rerun
or supplied fabricated result files merely to unlock unrelated route changes.
Save the previous route's concrete resume point before switching. Check the target
worktree and source identity before running; the command does not perform Git checkout.
Concurrent write-heavy work needs isolated worktrees and evidence return to the lead,
not multiple agents mutating CURRENT. Portfolio management does not itself enable parallelism.
When client-native delegation is available and two independent questions merit it,
load `parallel-research.md` for the bounded worker contract and evidence-return rules.

## Autonomous selection with architect control

At block entry and after meaningful evidence, evaluate the portfolio against application
impact, dependencies, uncertainty reduction, cost and current access. Priority is an
explainable agent recommendation, not an invented numerical confidence score. Update
affected routes and keep valuable unchosen lines parked with explicit wake conditions.
When an authorized block changes application direction, activate the corresponding
route before starting its execution; registration as queued is not a focus change.
If the tool refuses, report the mismatch between the actual block and saved focus,
with the concrete refusal. Never silently present the old route as the current work.
Track newly discovered valuable directions before the session loses them. Avoid an
unbounded idea backlog: each registered route needs a useful question and next probe.

At block close, compare the current line with plausible alternatives and inspect whether
new evidence/environment/architect signals satisfy dormant routes' conditions. Persist
observed wakes explicitly. Recommend one next action with why it outranks the others;
no automatic priority decay, timers, or fabricated "trigger satisfied" events.
Environment failure does not reject a mechanism. Rejection requires scientific evidence;
an architect veto parks/blocks it with that authority recorded, not a fake negative result.

Report application progress first, then changed route priorities, what is retained and
when it returns, the proposed next block, and any genuine architect decision. Routine
technical selection belongs to the agent. A half-hour stop is a briefing/intervention
window, not an obligation to ask the architect which algorithm or research topic to pick.
"Continue as recommended" can start the next bounded block within existing authority.
Do not open unlimited blocks under one bounded invocation. Persist any wider multi-block
authorization with scope, budget and reporting cadence before relying on it.

## Recovery acceptance

Mechanical test: register A/B, advance A, switch to B while retaining A's restart basis,
read in a fresh CLI process, append new evidence, wake A, switch back, and inspect both
histories. Queries must leave Git/state unchanged and a running job must prevent switching.
Behavioral acceptance is separate: a fresh model must recover and recommend appropriately
without the architect retelling A; passing the CLI test is not that proof.
