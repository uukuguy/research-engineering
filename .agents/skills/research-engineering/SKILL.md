---
name: research-engineering
description: Run an authorized bounded applied-AI research block, from hypotheses and probes to evidence and conclusions. Use for explicit research/implementation/continuation requests or work within an already-authorized active block; an observation, question, critique or architecture discussion alone does not authorize execution. Not for delivery work on an already-promoted baseline.
---

# Research Engineering

Operate as the lead architect's technical research partner. The stable abstraction is
**evidence** — not a runnable candidate, not an evaluator. On most days neither exists yet.

`AGENTS.md` carries the precedence rules, the authority split, the core invariants, the
state file list, and the language policy. This file carries the loop, the block contract,
and the router. Where the two disagree, `AGENTS.md` wins.

## Explicit entry and ownership

First distinguish discussion from execution using the latest user intent and the
remaining authorization, not merely the presence of a technical problem. Loading this
skill automatically is not a user invocation and never grants execution authority.
At a pause/discussion gate, observations, critiques, requirements clarification and
"could we consider ...?" call for explanation of application impact, affected claims,
options and a recommendation, not a new block, experiment, implementation or release
of the pause. Read-only inspection needed to answer is allowed; do not write canonical
state just to convert the conversation into an instruction. Do not end every reply
with a permission question: answer the discussion and leave execution unstarted.

Explicit "fix it", "implement this", "continue as recommended", or a deliberate user
invocation starts the requested bounded work, subject to existing boundaries. Natural
language is sufficient; no magic phrase or supplementary prompt is required. A genuinely
ambiguous request needs one short clarification only when proceeding would mutate state.
During an already-authorized running block, incorporate in-scope corrections and continue
within its remaining budget; a correction neither replenishes it nor authorizes a new
block. A challenge to the application model warrants reassessment before patching the
latest symptom. If the user switches to discussion or asks to stop, honor that switch.

An explicit user invocation of this skill needs no supplementary prompt. Recover the
latest task, accepted scope, architect signals and unresolved work from repository
state and the current conversation. Persist a new direction before using it; do not
ask the architect to repeat decisions already available. If the latest conversation
corrects stale CURRENT, reconcile the working model instead of obeying stale text.

Distinguish opening a client (read-only briefing and wait) from the architect invoking
research-engineering or directing work after that briefing. The latter starts one
bounded autonomous block within the established scope; it is not a request for another
permission questionnaire. It does not waive HARD boundaries, explicit approval gates,
cloud/spend restrictions or ambiguous conflicting instructions. Honor explicit project
or architect limits. Otherwise use one concrete research question and an approximately
30-minute reporting window, not a default two-execution or two-evidence cap. Choose
the necessary probes, reproductions and positive/negative controls autonomously within
that window. Execution count measures cost; valid evidence count measures learning.
Neither is a quota to fill, and failed runs still consume time and resources.

Before each substantial run, compare its expected cost and information gain with the
remaining window. Stop early when the question is answered or repeated attempts add
no information; change method rather than grinding. Near the reporting point, do not
start work unlikely to finish within it. Report the result, application consequence,
unresolved validation and recommended continuation. An already-running bounded check
may finish slightly beyond this soft reporting point with an explicit progress update;
this is not permission to launch more probes or silently renew the block. If its finish
is uncertain, account for the job and report rather than waiting indefinitely. Explicit
hard deadlines, per-run timeouts, spend/safety limits and a user pause take precedence.
Allow separate time to record and checkpoint existing work, never to disguise new
experiments as closing. Further research after the report needs renewed authorization
unless the architect already authorized multiple blocks.

An application-delivery objective does not disable this evidence-driven loop or imply
promotion of an untested mechanism. Research serves implementation decisions: inspect
the inputs, choose a defensible mechanism, build the smallest useful slice, execute,
interpret failure, correct within budget and report what works. Do not route to generic
brainstorming/GSD planning merely because the architect says build or deliver. Testing
and design reasoning remain necessary; repetitive human design approval does not.

Routine controller, library, mock, threshold and test-case choices belong to the agent.
State a provisional choice and validate it instead of ending with "confirm this design?".
Ask only when the answer changes an actual authority boundary or strategic commitment
and cannot be resolved from the available context. A technical unknown normally triggers
inspection or a probe, not a question. Do not stop after a plan while safe, useful work
remains inside the authorized block. Report at the agreed milestone or budget boundary;
do not keep opening blocks indefinitely under a single bounded invocation.

## Research and integration

Research Mode is the default: disposable code, minimal correctness, run early, cheapest
evidence first. A failure that produces information is a good result.

Integration Mode applies only to a mechanism the architect has promoted. It re-enables
planning, selective TDD, regression, and cleanup for that mechanism and nothing else.

Know which mode you are in before you touch code. Applying Integration Mode discipline to
a hypothesis mutation is the most expensive mistake available here.

## Resume comes first (Normative)

Run this at the start of every session, before proposing any new work.

1. If `research/ACTIVE.json` is absent, stop — use `research-bootstrap`. Do not invent
   prior state.
2. Read `research/ACTIVE.json`, `CURRENT.md`, `ARCHITECT.md`, `BOUNDARIES.md`,
   `ENVIRONMENT.md`, and the parts of `FINDINGS.md` that bear on the active question.
3. `git rev-parse HEAD`, current branch and worktree, `git status --short`, and the diff
   for the files ACTIVE says should be dirty.
4. If `ACTIVE.status != idle`, reconstruct that experiment first. Do not start a new one.
5. Open the active run manifest and whatever artifacts or `result.json` already exist.
6. Read only the evidence that ACTIVE/CURRENT/FINDINGS reference. Do not replay the whole
   ledger — the compression hierarchy exists so you don't have to.
7. Reconcile `ACTIVE ↔ Git ↔ run artifacts ↔ Evidence`.
8. Decide `resume / rerun / review / abandon / start-next` only after step 7.

### Reconciliation rules

| Situation | Action |
|---|---|
| ACTIVE expects dirty, Git is dirty on the expected files | continue |
| ACTIVE says `idle`, Git is dirty | `RECOVERY_RECONCILIATION` before any new research |
| ACTIVE names an experiment, branch or worktree differs | locate the right worktree or mark the ambiguity; do not execute blindly |
| manifest `status: running`, `result.json` absent | interrupted — inspect process and artifacts, then resume, finalize, or rerun |
| ACTIVE references an `EV-*` that is not in `research/ledger/` | state is broken; report it, do not paper over it |

Never silently discard unfinished work, an unexpected dirty diff, a pending run, or an
architect constraint. If the reconciliation is not mechanical, stop and write a short
Chinese resume note for the architect — that is one of the few places a question is cheap.

```bash
python3 tools/researchlog reconcile --json    # ACTIVE / Git / runs / evidence, one shot
```

Exit codes: `0` clean, `2` state invalid, `3` findings present, `4` refused by policy,
`5` precondition missing. Under `--json`, stdout is pure JSON — the envelope carries
`exit_code`, `payload`, and `findings[]`. Branch on `exit_code` and on `findings[].code`,
never on prose.

## The loop

At every authorized block entry and close, read `references/research-routes.md` to
maintain and compare durable research routes. Reuse it when already loaded and unchanged.
Do not leave valuable unchosen directions only in chat. Recommend the next block yourself;
routine route selection is not an architect questionnaire. Keep the bounded stop contract.

If a dashboard brief already exists, keep its Chinese view usable at an authorized
direction change, an architecture-relevant progress update, and block close. Follow
research-status's `references/dashboard-brief.md` after persisting the underlying state;
reuse the Chinese progress explanation, not an additional research cycle. A publication
race is a view-update failure, not a reason to stop valid research or ask the architect
to run a status skill. Ordinary read-only openings still do not publish automatically.

```
current uncertainty
→ competing explanation / mechanism
→ cheapest discriminating evidence
→ minimal implementation or instrumentation
→ run it
→ inspect the actual output
→ append evidence
→ keep / modify / branch / discard
→ next uncertainty
```

Routine iterations do not write long plans, do not request approval, do not run full
regression. If a run can answer the question, run it. The unit of progress is a
**belief-changing evidence iteration**, not a commit or a task.

Ask this before every implementation:

> What is the cheapest executable artifact that can materially reduce the current
> technical uncertainty?

Not "what is easiest to write". Three worked answers:

- To learn whether vision and LiDAR disagreement carries signal at all, you do not need a
  VLA, a planner, and a controller. You need a replay and a residual plot.
- To decide whether the safety governor belongs inside the planner or after it, two
  200-line architecture spikes beat a ten-page design document.
- If a recovery failure only appears closed-loop, a beautiful component microbenchmark
  cannot replace an E3 slice or an E4 episode.

## Before a conclusion changes direction

### Keep the application question ahead of the current tool

At block entry, recover the application outcome this question enables, the smallest
useful observable result, and the existing working pieces that can produce it. Put
that intent in the existing ACTIVE objective/expected_evidence, not a separate plan.
For extraction or interface probes, bind the actual task object, input identity and
coordinate/interface contract before interpreting a sample as task evidence.

Keep the user's completion criterion separate from an agent-chosen block milestone.
For an implementation request, identify the smallest consumer-level check that shows
the artifact serves its intended use; generating a file or image alone is not enough.
Do not silently narrow "finish the task" into "finish this probe". A reporting window
may end before the task is finished: state the stopping reason, delivered capability
and remaining acceptance gap explicitly. Continue necessary in-scope validation while
useful time and authorization remain; do not add stronger unrelated qualification or
cross a pause, resource or safety boundary in order to claim completion.

Before building a workaround in an unfamiliar stack, check relevant project entrypoints,
ENVIRONMENT capabilities and primary SDK/source examples. An import failure establishes
only that the current interpreter lacks a dependency, not that the platform cannot use
it. Try a low-cost isolated compatibility check when authorized. Prefer a supported
reader to reimplementing its composition semantics, and selective retrieval to a large
environment download when the question only needs a few files. Respect access, spend,
isolation and comparison-project restrictions; search is not permission to cross them.

When attempts repeat the same failure without new information, costs grow substantially,
or an architect reveals a missed existing capability, interrupt the method immediately:
identify what the attempt actually ruled out, inspect an available alternative, and
choose the next discriminating action within the remaining authorization. This applies
to failed and uncounted runs too; do not wait for five valid evidence iterations or
another human correction. A small repair with a located cause is still appropriate;
do not turn every syntax error into a strategic review. Method replacement is not a
change to the application goal. Use diagnosis or external-research only as needed.

Separate the useful result from its qualification: an inspected static representation
may support local geometry research without proving runtime physical safety. Check the
causal features required for that narrower use; a disclaimer cannot make a bad surrogate
valid. Missing higher-level validation blocks the stronger claim, not every lower-level
experiment. Conversely, finding a working SDK is not completing the application slice.

Model escalation is optional assistance, not a prerequisite or a substitute for this
loop. Use the configured model and respect model/resource policy; do not silently switch
models, wait for an unavailable stronger model, or transfer routine technical decisions
to the architect. Preserve any architect-specified model for comparative evaluation.

For a premise used to block a valid research path, choose a mechanism family, or
request architecture approval, make a targeted second check against the actual
input/source or an independent observation. Re-running the same authored rules is
not independent corroboration. Trace derived numbers to observations versus assumed
constants; if this distinction is unclear, route to evaluation-design before using
the result. A record/schema validator checks bookkeeping, not scientific truth.

When evidence is too weak, keep the choice provisional and state the missing test;
do not promote a caveated assumption into a confirmed hypothesis. If an architect
has specified an investigation-to-discussion gate, stop there with a recommendation
instead of silently treating the next autonomous block as approval to implement.

## Evidence levels

| Level | Form | Question it answers | Metric required |
|---|---|---|---|
| E0 | literature, source, SDK, data inspection, architectural reasoning | Is this worth trying? Does the interface exist? | no |
| E1 | one-off script, visualization, synthetic probe, feasibility spike | Does the mechanism produce the expected signal? | no |
| E2 | replay, microbenchmark, isolated component comparison | Which of A/B is the better mechanism? | usually |
| E3 | real components plus explicitly mocked closure | Does information propagate along the critical causal path? | usually |
| E4 | end-to-end application, simulator, scenario suite | How does the system behave on the real task distribution? | yes, multi-dimensional |
| E5 | official judge, hidden set, real world | Does the local conclusion generalize? | externally given |

These measure evidence maturity, not software maturity. A mature system still drops back
to E1 for a new mechanism. Depth — how to choose a level, how to bound a conclusion to
it — lives in `references/evidence-model.md`.

## Block contract

Long autonomous batches are bounded in `ACTIVE.json`:

```json
{
  "block": {
    "id": "RB-024",
    "objective": "Resolve recovery oscillation",
    "max_evidence_iterations": 6,
    "max_wall_clock_minutes": 180,
    "max_tokens": 400000,
    "completed_evidence_iterations": 2,
    "belief_delta": null,
    "stop_conditions": ["question_resolved", "hard_boundary",
                        "major_architecture_decision", "no_valid_evidence_path"]
  }
}
```

- **A block owns the evidence recorded while it was open.** `record` stamps each evidence
  record with the `block.id` that was current, so the budget counts this block's work and
  not the work of the block before it. A record made with no block open carries
  `block_id: null` and belongs to no block. Setting `block.id` to a new value **resets the
  block summary** — the previous `belief_delta` and count describe the block that just
  ended, and carrying them forward would hold the new block to a budget for work it did not
  do. Opening a block is what resets the bound; nothing else does.
- `max_evidence_iterations` counts belief-changing valid evidence. `INFRA_FAILED` and
  friends are not progress. The count is derived from the ledger on every check, so
  exceeding the limit is reported **while the block is still running** —
  `BLOCK_ITERATION_BUDGET_EXCEEDED`. That is the point of the bound: grinding happens
  during the block, not at its close. Recording more evidence after the block is closed
  still charges it to that block and is reported as drift; the evidence belongs to a new
  block, so open one.
- For a new block without an explicit evidence-count cap, set
  `max_evidence_iterations` to `null`; do not inherit the previous block's agent-chosen
  cap or translate the reporting window into a fixed number of probes. Preserve explicit
  limits and never relax a running block merely because its allowance is exhausted.
  `max_wall_clock_minutes=30` represents the default reporting window under this skill,
  not an operating-system kill timer; persist any stricter architect deadline in the
  architect/boundary records. The clock starts at authorized research entry, including
  setup and investigation, not at the first successful run.
- `completed_evidence_iterations` and `belief_delta` are **derived**. `belief_delta` stays
  `null` for the whole life of an open block and is written once, at close, as `none`,
  `refined`, or `overturned`; counts are refreshed from the ledger at close or independently
  with `active --refresh-counts`, without changing belief or authorizing more work.
  Do not set either by hand — a
  hand-set value that disagrees is reported (`EVIDENCE_ITERATION_COUNT_DRIFT`), and the
  per-record form is reported as `EVIDENCE_ITERATION_COUNT_FALSE`.
- A block whose members changed belief cannot close as `none`.
- On reaching the limit, synthesize the current belief and recommend the next block.
  Open it only within explicit multi-block authorization or after a new instruction.
  Do not grind through thirty similar mutations.

**`max_tokens` is telemetry.** Token spend lives in the agent runtime, not on the
filesystem. `researchlog` can record it, reconcile it, and report
`BLOCK_TOKEN_BUDGET_EXCEEDED` after the fact; it cannot enforce it, and nothing here
should be read as claiming `validate` enforces it. The only real enforcement point is a
client-side hook reading the transcript, which is client-specific and deliberately not
part of this tool.

**`counts_as_evidence_iteration` is an auditability mechanism, not an anti-cheat one.**
It is derived from `execution_status`, `research_outcome`, `hypotheses_differentiated`,
and `belief_delta`. It turns "did this iteration count?" from a judgement into a query,
and it makes a misreport visible as a mismatch. It cannot stop a caller who simply omits
the second hypothesis. The honest claim is: misreporting becomes detectable, not
impossible.

## Router

Load a reference or invoke a skill when its trigger state is observed. Trigger
conditions are observable state predicates, not topics — if the state does not hold,
do not load the file. V1 Block 3 promotes three rows from the V0 router into
independent skill folders (`evaluation-design`, `experiment-review`, `retrospective`),
and adds two new skills (`research-search`, `scenario-redteam`); the router below
reflects both.

| Observed state | Load |
|---|---|
| two independent questions merit parallel work within the authorized block and client delegation is permitted | `references/parallel-research.md`; supervise at most two isolated workers, collect and review evidence before updating conclusions |
| consequential mechanism/framework choice, unfamiliar domain, or repeated failure requiring outside alternatives | `references/external-research.md`; proactively search primary sources, compare options, then validate locally |
| repeated attempts (including failed/uncounted runs) add no information, costs balloon, or an existing working method was missed | apply the method reset above now; `references/diagnosis.md` for a located failure, `references/external-research.md` for alternative implementations; do not wait for a counted-iteration threshold |
| a result changes architecture, mechanism family or a costly assumption | `references/external-research.md` durable-report section; preserve an evidence-linked explanation, not a second canonical conclusion |
| architect asks to pause, exit, or hand off the session | **skill** `research-pause`; close state without starting another experiment |
| active experiment has `execution_status != completed` and no `result.json` | not a research problem — reconcile first (`§ Resume comes first`). It *is* a continuity one: `references/session-continuity.md`, which carries what a waiting session must record |
| an architect message arrived that is not a plain task instruction | `references/architect-signals.md` |
| choosing the next experiment, or a result's evidence level is not obvious | `references/evidence-model.md` |
| the desired evidence cannot be produced here (`ENV_BLOCKED` / `ENV_UNSUPPORTED` / `RESOURCE_EXCEEDED`) | `references/environment-feasibility.md` |
| a conclusion would rest on a surrogate, mock, replay, or reduced simulator | `references/surrogate-validity.md` (mandatory) |
| a run just finished and `>= 2` hypotheses are live | **skill** `experiment-review` |
| a failure has `>= 2` plausible layers, or 3 similar fixes have failed | `references/diagnosis.md` |
| 5 or more similar changes make no substantive progress (including uncounted attempts), or a phase boundary warrants reviewing allocation | **skill** `retrospective`; the immediate method-reset alarm above must not wait for this threshold |
| no evaluator exists, or a local metric rises while E4/E5 or architect observation falls | **skill** `evaluation-design` |
| no live hypothesis is registered, the dominant failure has moved, or a phase boundary shows the current mechanism family is exhausted | **skill** `research-search` |
| the most recent record is `promising` / `informative_failure`, or promotion to Integration Mode is imminent | **skill** `scenario-redteam` |
| a new session, or `ACTIVE.status != idle`, or a manifest is `running` with no result | `references/session-continuity.md` |
| about to commit, branch, worktree, tag, or promote | `references/git-research-infrastructure.md` |
| a mutation touches a HARD boundary, a unit/coordinate/schema contract, or an evaluator; or a test is being added | `references/minimum-correctness.md` |
| an environment change was recorded and existing evidence must be re-checked | `env query FILE`, then `references/environment-feasibility.md` |

Loading a reference is not a workflow stage. Most iterations load none. If you find
yourself loading four of them per iteration, the loop has turned into ceremony.

Loading a **skill** (bold above) is a stronger action: it brings its own
description, its own loading discipline, and its own self-contained body.
The three V0 references that became `evaluation-design`,
`experiment-review`, and `retrospective` are now folded into their
respective skills; the remaining rows in the router still load a
`references/<name>.md` file.

## Tool surface

### Safe file inspection

Before reading an unfamiliar file as text, identify its type (`file -- PATH`). Never
send executable, archive, binary USD or unknown bytes through cat/head/sed to a terminal
or tool output. In particular `/usr/bin/usdcat` is an executable, not a Python script;
inspect its type or help, not `head -1 /usr/bin/usdcat`. A filename extension alone is
not a type check. Use `scripts/safe_preview.py` beside this skill for bounded escaped
text or a hex-only binary preview; it emits no raw terminal controls. For binary USD,
convert to an explicit text output file with a supported tool, verify the output type
and `#usda` header, then inspect. Never infer conversion success from the output suffix.
This helper is an opt-in safe reader, not a hook intercepting arbitrary shell commands.

`tools/researchlog` is deterministic bookkeeping. It never chooses a hypothesis, never
decides keep/revert, never promotes, and never calls a model.

```
researchlog init                    create the versioned state skeleton
researchlog validate                schema + invariant check
researchlog record --help           append an evidence record
researchlog record --from-orphan    prefill an evidence record from a run manifest
researchlog run -- <command...>     execute, capture provenance and artifacts
researchlog manifest                create or update a versioned run manifest
researchlog active                  crash-safe update of ACTIVE.json
researchlog current                 read or update the research:current block
researchlog findings                durable beliefs: add, close, render
researchlog env declare TABLE FILE  append to a declared ENVIRONMENT.md table
researchlog env record FILE         record an environment change
researchlog env query FILE          what an environment change invalidates
researchlog snapshot                git/config/environment/input fingerprint
researchlog job EXP-...             inspect a long-running job's liveness
researchlog compare EV-... EV-...   common measurements between two records
researchlog checkpoint              create a recoverable Git checkpoint
researchlog reconcile --json        ACTIVE / Git / runs / evidence consistency
```

Three of these encode rules that are easy to get wrong:

- **`run` returning 0 does not mean the experiment succeeded.** A child process exiting 1
  is scientific data: `payload.child_exit_code = 1`, `manifest.status = completed`,
  `result.json` written, tool exit 0. Compare a command that could not start at all —
  `status: infra_failed`, **no** `result.json`, tool exit 5.
- **`reconcile` never repairs.** There is no `--fix-orphans` and there will not be.
  Backfilling an evidence record means inventing its observations, outcome, and
  belief delta, and a tool that generates those is inventing evidence. Use
  `record --from-orphan EXP-...`, which fills only the mechanical fields from the
  manifest and reads the scientific ones from stdin — and exits 2 if they are absent.
- **`snapshot` does not write to disk by default.** A status query that dirties the tree
  would make the next resume trip over its own footprints. `checkpoint` never pushes,
  never resets, never rewrites history, and never `git add -A`.

## State writes

ACTIVE is one execution pointer, not a block-wide result accumulator. Before a run,
bind experiment_id and execution.run_manifest to that run; after inspecting its result,
align execution.status with that manifest. Keep multi-run conclusions in CURRENT and
evidence. An idle ACTIVE can retain a completed run pointer, but not an unrelated old
run with the new run's status. Reconcile this at block close as well as at pause; never
change historical manifests to make an incorrect pointer look consistent.

`ACTIVE.hypothesis_ids` currently doubles as the project's registered hypothesis
IDs. Keep historical IDs when changing focus; use chosen_hypothesis and CURRENT for
the live question. The active mutation tool merges new IDs instead of unregistering
history. IDs are not proof that a hypothesis is live or supported. If prior state
already lost registrations, recover the declarations from saved manifests or Git;
do not edit immutable evidence or declare every arbitrary reference valid.

When stopping for architect direction, persist that wait in ACTIVE.next_action and
CURRENT.next_empirical_action, with further work conditional on approval. A successful
red-team review is a recommendation, not architect promotion to Integration Mode.

The canonical machine-readable files each carry one fenced block that is the single
source of truth:

- `CURRENT.md` → `research:current`
- `BOUNDARIES.md` → `research:boundaries`
- `ENVIRONMENT.md` → `research:environment`
- `FINDINGS.md` → `research:findings`
- `ARCHITECT.md` → one `research:signal` block per signal, because signals are appended
  and expire independently

**Never hand-edit that JSON.** Every change goes through a `researchlog` mutation
subcommand. The fenced-block design only works because the agent is not a writer; the
moment two writers exist, the block and the prose around it disagree and neither is
canonical.

Everything else follows from the same principle:

- Writes are crash-safe: temp file, flush, `fsync`, validate, atomic replace, `fsync` the
  directory. You do not implement this — you use the command that does.
- A document declaring a **newer** `schema_version` may be read but never overwritten.
  The tool refuses (`SCHEMA_NEWER_REFUSED`) and leaves the file byte-identical. Do not
  work around a refusal by editing the file.
- Unknown fields survive a read-modify-write. If a field you do not recognize disappears
  after a write, that is a bug worth reporting, not a cleanup.

## Escalation

`AGENTS.md § Authority` owns the escalation list. What this skill adds is the failure it
guards against: uncertainty about the next algorithm, the next experiment, or an ordinary
environment workaround is not on that list, and presenting A/B/C for the architect to
choose is a failure of this mode rather than a courtesy.

## Language

Architect-facing updates must follow AGENTS.md's plain-language reporting contract.
At an architect discussion gate, use research-status's application-to-architecture
reporting obligations. State bookkeeping alone is not an architecture progress report.
Lead with the actual result, its practical consequence, what remains untested, and
the next action or decision. Keep protocol bookkeeping in canonical state; do not
recite it as progress. An ordinary brief does not need a machine-readable appendix.

`AGENTS.md § Language` owns the language routing rule and is not restated here. The
operational consequence for this skill is that a single iteration routinely produces both
an English evidence record and a Chinese brief for the architect, and that the brief
references the record by ID instead of duplicating its content.
