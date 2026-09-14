---
name: research-engineering
description: Use for exploratory applied-AI research where the system, algorithm, architecture, evaluation surface, or research environment is still evolving. Operates the research loop end to end — resume state, pick the cheapest valid evidence, run it, record it, decide what is next. Not for delivery work on an already-promoted baseline.
---

# Research Engineering

Operate as the lead architect's technical research partner. The stable abstraction is
**evidence** — not a runnable candidate, not an evaluator. On most days neither exists yet.

`AGENTS.md` carries the precedence rules, the authority split, the core invariants, the
state file list, and the language policy. This file carries the loop, the block contract,
and the router. Where the two disagree, `AGENTS.md` wins.

## Mode

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
- `completed_evidence_iterations` and `belief_delta` are **derived**. `belief_delta` stays
  `null` for the whole life of an open block and is written once, at close, as `none`,
  `refined`, or `overturned`; `completed_evidence_iterations` is written at the same
  moment, by the same command, from the ledger. Nothing maintains a live counter, because
  a counter nobody maintains is a counter that lies. Do not set either by hand — a
  hand-set value that disagrees is reported (`EVIDENCE_ITERATION_COUNT_DRIFT`), and the
  per-record form is reported as `EVIDENCE_ITERATION_COUNT_FALSE`.
- A block whose members changed belief cannot close as `none`.
- On reaching the limit, synthesize the current belief and open a new block. Do not grind
  through thirty similar mutations.

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

Load a reference when its trigger state is observed. Trigger conditions are observable
state predicates, not topics — if the state does not hold, do not load the file.

| Observed state | Load |
|---|---|
| active experiment has `execution_status != completed` and no `result.json` | not a research problem — reconcile first (`§ Resume comes first`) |
| an architect message arrived that is not a plain task instruction | `references/architect-signals.md` |
| choosing the next experiment, or a result's evidence level is not obvious | `references/evidence-model.md` |
| the desired evidence cannot be produced here (`ENV_BLOCKED` / `ENV_UNSUPPORTED` / `RESOURCE_EXCEEDED`) | `references/environment-feasibility.md` |
| a conclusion would rest on a surrogate, mock, replay, or reduced simulator | `references/surrogate-validity.md` (mandatory) |
| a run just finished and `>= 2` hypotheses are live | `references/experiment-review.md` |
| a failure has `>= 2` plausible layers, or 3 similar fixes have failed | `references/diagnosis.md` |
| the last 5 counted iterations all carry `belief_delta: none` | `references/retrospective.md` |
| no evaluator exists, or a local metric rises while E4/E5 or architect observation falls | `references/evaluation-design.md` |
| a new session, or `ACTIVE.status != idle`, or a manifest is `running` with no result | `references/session-continuity.md` |
| about to commit, branch, worktree, tag, or promote | `references/git-research-infrastructure.md` |
| a mutation touches a HARD boundary, a unit/coordinate/schema contract, or an evaluator; or a test is being added | `references/minimum-correctness.md` |
| an environment change was recorded and existing evidence must be re-checked | `env query FILE`, then `references/environment-feasibility.md` |

Loading a reference is not a workflow stage. Most iterations load none. If you find
yourself loading four of them per iteration, the loop has turned into ceremony.

## Tool surface

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

`AGENTS.md § Language` owns the language routing rule and is not restated here. The
operational consequence for this skill is that a single iteration routinely produces both
an English evidence record and a Chinese brief for the architect, and that the brief
references the record by ID instead of duplicating its content.
