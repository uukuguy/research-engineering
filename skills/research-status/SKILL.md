---
name: research-status
description: Use when the lead architect asks for current project progress, global research state, key bottlenecks, current architecture, active research, or a compact project context snapshot. Compiles canonical repository state into a Chinese Project Working Model with traceable evidence. Read-mostly synthesis — it does not plan research, start experiments, or modify state.
---

# Research Status

Compile the repository's current research state into a compact Project Working Model.

Two audiences read the same report:

1. the lead architect, who needs the global picture without reconstructing it;
2. an AI agent, which can paste it back in as high-quality context compression.

It is a **derived snapshot**. Canonical truth stays in `research/ACTIVE.json`,
`CURRENT.md`, `ARCHITECT.md`, `BOUNDARIES.md`, `ENVIRONMENT.md`, `FINDINGS.md`, the
evidence ledger, run manifests, and Git. The report never becomes a second source of truth.

`AGENTS.md` carries the language policy, the authority split, and the invariants. This
skill does not restate them.

## Language

The visible report is **Chinese**, with technical terms, algorithm and library names,
metrics, protocol names, Git refs and tags, and canonical IDs (`EV-*`, `EXP-*`, `H-*`,
`FND-*`, `RB-*`, `ENV-*`) kept in their original English form.

Keep the structure stable enough that the same report can be pasted into a new Codex or
Claude Code session as usable context. Do not maintain a bilingual duplicate — one
canonical English state, one Chinese report that references it by ID.

## Read-mostly

By default this skill does **not**:

- modify application code;
- start experiments;
- choose a new research direction;
- change hypotheses or `FINDINGS.md`;
- promote a candidate;
- alter architect decisions;
- reset, clean, or check out over Git state.

If the state is inconsistent, report it, and then **name the next step** — see *When the
state is inconsistent*. This skill never reconciles, but it is the entry point the
architect reads most often, so a report that only reports is how an inconsistency stays in
place indefinitely. Producing a status report must never be the thing that dirties the
working tree — a query that manufactures a dirty diff makes the next resume trip over its
own footprints.

## Sources, in order

```bash
python3 tools/researchlog reconcile --json    # ACTIVE / Git / runs / evidence, one shot
python3 tools/researchlog active --get-json
python3 tools/researchlog job EXP-0142        # only when a run is in flight
```

1. `research/ACTIVE.json`
2. `research/CURRENT.md`
3. `research/ARCHITECT.md`
4. `research/BOUNDARIES.md`
5. `research/ENVIRONMENT.md`
6. `research/FINDINGS.md`
7. the evidence records those files reference
8. the active run manifest, results, and artifacts where relevant
9. Git HEAD, branch and worktree, `git status --short`, relevant research commits and tags

Do **not** load the whole evidence ledger. The compression hierarchy exists so that a
status report costs a few files, not a replay of the entire history. Descend only when a
specific claim needs checking.

## Integrity check before reporting

Read-only, and it runs every time:

```
ACTIVE  ↔  Git HEAD / branch / status / diff
        ↔  active run manifest / artifacts
        ↔  referenced Evidence
```

Also check:

- architect constraint scope and expiry — is anything still marked active past its expiry?
- environment ID and rebaseline status;
- whether `CURRENT.md` is stale relative to `ACTIVE`, the evidence, or Git;
- whether the baseline or tag the report names actually exists;
- whether `FINDINGS.md` cites evidence that is present in the ledger.

`reconcile` reports most of this mechanically; read `findings[].code` rather than
re-deriving it. On material inconsistency, put a `STATUS INTEGRITY WARNING` near the top
naming the conflicting facts and the IDs involved. Do not silently repair a destructive
ambiguity — that is `research-engineering`'s job, under the resume protocol.

## Reporting principles

No software-style completion percentage. There are three independent maturity axes and
they do not collapse into one number:

- **System Maturity** — what exists and runs;
- **Evidence Maturity** — how reliably we know it works;
- **Research Environment Maturity** — what this lab can currently verify.

A system can be E4-runnable while a new mechanism inside it has only E1 evidence. A
complete implementation can sit in an environment that can only verify a whole class of
attacks to E2. Both are normal, and a single percentage misrepresents both.

Keep these separate in the report: what exists; what has been demonstrated; what is
currently believed; what remains provisional; what has been refuted; what is being tested
right now.

Report only belief-changing, architecture-relevant, capability-relevant, or
environment-relevant progress. Do not enumerate commits, files, tests, or routine
experiments — a status report that reads as a project-management ledger has failed at
context compression.

## Default report structure

1. One-line project status
2. Current working contract (active block, objective, limits)
3. Three-axis maturity: System / Evidence / Research Environment
4. Current system and architecture shape, marked provisional unless it is not
5. Recent substantive progress — belief-changing or architecture-changing only
6. Findings: Established / Provisional / Refuted / Open
7. Current research frontier, when more than one meaningful family is live
8. Key unknowns, failures, and bottlenecks
9. Research environment: only capabilities and limits that bear on current research
10. Active research: hypothesis IDs, experiment ID, current observation, next action
11. Next-stage research priorities
12. Items needing the architect
13. Risks and drift signals
14. Continue-research context capsule
15. Snapshot basis / provenance

Default length is about 1–3 screens. Expand the evidence history only when the architect
explicitly asks for it.

## Items needing the architect

Default to a line stating, in Chinese like the rest of the report, that no architect
decision is required. A status report that escalates nothing is the normal case.

List something only for a HARD boundary change, a strategic architecture decision, a
meaningful environment investment, external spend or access, an official submission, a
physical safety decision, or an unresolved conflict between architect directives.

Routine algorithm, model, threshold, and library choices are never listed. If the report
is surfacing those, the research loop is escalating when it should be researching — say so
in section 13 rather than presenting them as decisions.

## Continue-research context capsule

Close the report with a compact Chinese capsule:

```
Objective
Current Direction
Established Facts               (with EV-* IDs)
Current Provisional Beliefs     (with EV-* IDs)
Active Architect Decisions / Constraints  (with scope + expiry)
Current Bottleneck
Active Research / Experiment
Environment limits relevant to the active problem
Next Empirical Action
Escalation Conditions
```

Keep original English technical terms and canonical IDs. No conversational history, no
reasoning narrative — this is a rehydration capsule, not a summary of the discussion.

**It accelerates cognitive rehydration. It does not replace the Session Resume Protocol.**
A new agent must still reconcile `ACTIVE ↔ Git ↔ run artifacts ↔ Evidence` before touching
code. Say so explicitly at the end of the capsule, because the failure mode is an agent
that reads the status report and starts editing.

## Snapshot basis

Sections 1–14 are Chinese prose for the architect. End the report with an **English-keyed
YAML block** instead of prose, so that a new session parses the state rather than
re-deriving it from Chinese narration:

```yaml
generated_at: 2026-09-14T10:22:31+08:00
git:
  head: 8c1a2f0
  branch: main
  worktree: /absolute/path/to/worktree
  baseline: null                 # tag or frozen baseline this report is relative to
environment_id: null             # ENVIRONMENT.md's current environment, or null if unset
maturity:
  system: <what exists and runs>
  evidence: <highest stable level, e.g. E2>
  research_environment: <what this lab can currently verify>
active:
  status: idle                   # ACTIVE.status verbatim
  experiment_id: null
  block_id: null
evidence_cutoff:
  key_ids: []                    # the EV-* records this report actually rests on
  highest_level: null
  records: 0
integrity:
  reconcile_exit: 0
  state: clean                   # clean | inconsistent
  findings: []                   # findings[].code verbatim, empty when clean
```

Emit it on every report, including — especially — when the state is inconsistent. Then
`integrity.state` is `inconsistent` and `integrity.findings` lists the codes. The block
is not optional: a capsule with no integrity block reads as clean, which is the one thing
it must never say by accident.

## When the state is inconsistent

This skill reports; it does not repair. But it is the highest-frequency entry point — the
architect may read nothing else that day — so the report has to close with the concrete
next step rather than a description of who owns the problem:

```
→ 建议下一步: /research-engineering 执行 RECOVERY_RECONCILIATION
```

Use that line whenever `integrity.state` is `inconsistent`. When the state is clean, close
with the next empirical action instead. Either way the resume protocol still runs before
any code is touched.

## Persisting the report

By default, print the report and stop. Write `research/STATUS.md` only when the architect
explicitly asks to save the current state, or at a declared milestone or checkpoint. When
written, the file header carries:

```
DERIVED SNAPSHOT — NOT SOURCE OF TRUTH
```

A stale `STATUS.md` never overrides `CURRENT`, `FINDINGS`, `ACTIVE`, or Git. A new agent
may use it to build a fast global picture, and must still run the resume protocol before
executing.

## Optional remote state

GitHub is optional and never canonical. If a remote and `gh` are available, supplementary
state may include whether the active branch is pushed, an open promotion PR, an explicitly
requested verifier run, or release and submission tags. Local repository state wins on any
disagreement, and the disagreement is reported as an integrity finding.
