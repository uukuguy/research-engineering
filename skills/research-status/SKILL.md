---
name: research-status
description: Use when the lead architect asks for current project progress, global research state, key bottlenecks, current architecture, active research, or a compact project context snapshot. Compiles canonical repository state into a Chinese Project Working Model with traceable evidence. Read-mostly synthesis — it does not plan research, start experiments, or modify state.
---

# Research Status

Explain the project's current state to the architect in plain Chinese. The default
reader is a human deciding what to do, not an agent parsing a compressed state dump.
An explicitly requested handoff can additionally serve a future agent.

It is a **derived snapshot**. Canonical truth stays in `research/ACTIVE.json`,
`CURRENT.md`, `ARCHITECT.md`, `BOUNDARIES.md`, `ENVIRONMENT.md`, `FINDINGS.md`, the
evidence ledger, run manifests, and Git. The report never becomes a second source of truth.

`AGENTS.md` carries the language policy, the authority split, and the invariants. This
skill does not restate them.

## Language

The visible report is **plain Chinese**. Preserve exact model/library names and
necessary metrics; explain unfamiliar terms at first use. Prefer "只检查了输入文件，
还没运行机器人任务" to "E1 闭环完成，E4 尚未闭合". Prefer "它漏查了数据链接，
所以错误地认为没有数据" to "环境可行性表面出现偏移". These are examples of clarity,
not phrases to repeat regardless of evidence.

Do not lead with protocol names, IDs, Git hashes, or state fields. Put evidence links
next to material claims; reserve machine-readable detail for a requested handoff or
audit. Canonical state remains English; do not create a second bilingual truth source.

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

### Lightweight session opening

If the canonical state directory contains `delegations/`, query `delegate list` with
the local CLI. Include unanswered worker questions, returned-but-unreviewed results,
and their application relevance. Recorded dispatch is not liveness; do not relaunch,
collect, cancel or review work during a read-only opening.

For an established project, this skill contains the read-only opening protocol;
do not load the full research-engineering loop merely because a new client opened.
Read TASK, active architect directions and canonical state first, batching independent
reads. Inspect only the few evidence/artifact references needed for material claims.
`reconcile`, `validate`, `active --get-json` and snapshot queries are read-only and
need no authorization to begin research. They must not be confused with repair.

Do not re-extract an original DOCX/PDF, reload domain documentation skills, enumerate
the whole repository/data tree or repeat the prior investigation simply because TASK
links an original source. Descend to source when the required fact is missing, conflicts
with current instructions, or source identity has changed/has not been established for
a claim requiring verification. Otherwise report the recorded conclusion with its basis
and limitations; do not describe it as newly verified. An unverified source freshness
check is unknown, not an excuse to silently certify old conclusions as current.

Run mechanical checks once on an unchanged snapshot. If they fail, report the impact
and stop at the briefing; do not expand into a repair or research cycle. If opening
takes over a minute, explain the specific remaining check rather than going silent.

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
re-deriving it. On material inconsistency, put a plain Chinese warning near the top
explaining which records disagree, what that prevents us from trusting, and the next
safe step. Link affected evidence; do not make a code the explanation.
Do not silently repair a destructive
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

## Default brief

Before compressing state, recover the application objective and success criteria
from the project's TASK or original brief and active architect signals. CURRENT is
working memory, not permission to silently narrow the task to the current probe.
If these disagree, disclose the narrowing; do not rewrite state during this query.

Report from the outside in: application capability, system responsibilities and
candidate choices, implementation and validation, then the next decision. Explain:

- What the user needs the system to do and how success will be judged. A ranking
  aspiration is a goal, not a measured capability or a promised result.
- Which components are supplied externally versus built here, how inputs/actions
  cross that boundary, and which parts are known versus still uninvestigated.
- Which materially different approaches remain plausible, their practical benefits
  and costs, and what evidence would distinguish them. Do not turn routine algorithm
  selection into an architect vote. If no defensible comparison exists, say so.
- What code actually does today: documentation inspection, authored-rule calculation,
  component execution, or task execution. Name the missing link to useful capability.
- Why the next investigation changes an application or architecture decision, and
  whether the agreed investigation-to-discussion milestone has actually been reached.

These are reasoning obligations, not five mandatory extra sections. Include a small
system sketch or comparison only if grounded and useful; label a proposed structure
as proposed. Missing architecture research cannot be filled with an invented diagram.
If state alone cannot answer a material question, inspect the relevant task/interface
or implementation artifact read-only; otherwise report the gap explicitly.

Answer the architect's actual question, usually in a few short paragraphs or up to
five bullets. These are questions to answer where relevant, not mandatory headings:

- Where are we, in one sentence?
- What did we actually learn or change, and why does it matter?
- What is wrong, uncertain, or still untested?
- What is the next concrete action?
- Does the architect need to decide anything? If yes, give the recommendation,
  practical alternatives, cost/risk, and consequence of waiting.

Do not use completion percentages without a meaningful denominator, or counts of
files/tests/evidence as substitutes for research value. Do not soften a mistake into
"drift" or hide a failed assumption behind a successful tool run. "I checked X"
does not mean "X works"; "I recommend X" does not mean "X has been demonstrated".

Keep the three maturity distinctions in the reasoning, but express them as what
exists, what has actually been tested, and what this environment cannot yet test.
Longer architecture comparisons and deep reviews are welcome when requested;
brevity must not omit a fact that would change the architect's decision.

## Make important conclusions inspectable

For each direction-changing conclusion in a brief, state its basis and limitation
in ordinary language: was it observed in real inputs, inferred from documentation,
or calculated from manually chosen rules? Give enough evidence to judge the claim
without inspecting code. A report should say "I calculated coverage under these
assumptions; detection has not been tested", not merely "two probes confirmed it".
Do not require the architect to uncover hidden premises by auditing command logs.
When a premise was corrected, name the affected conclusions and what remains valid.
If progress required the architect to identify the technical method or supply a working
implementation, distinguish that assistance from independent discovery. Repeated failure
without a method change, or repeated rediscovery of an available capability, is a research
process problem even if every record validates. Report its practical cost and the recorded
method change; do not imply that changing the model alone resolves it. During recovery,
include relevant reusable capability pointers when available, not just unresolved limits.

## Items needing the architect

When CURRENT.research_routes exists, include a compact portfolio view: current focus,
valuable queued alternatives, parked/blocked lines and their wake conditions, and why
the recorded recommendation should come next. Distinguish AI priorities from architect
constraints. Flag an apparently satisfied wake condition as a recommendation, not a
state mutation. No route registry in an older project means "not registered", not that
all unchosen work is gone or rejected. Do not silently migrate during this read-only query.

Routine state maintenance belongs to the agent on resumption, not in the architect's
decision list. Disclose integrity problems and their consequences separately; a
request to resume is not a request for the human to repair an environment ID.

Default to a line stating, in Chinese like the rest of the report, that no architect
decision is required. A status report that escalates nothing is the normal case.

List something only for a HARD boundary change, a strategic architecture decision, a
meaningful environment investment, external spend or access, an official submission, a
physical safety decision, or an unresolved conflict between architect directives.

Routine algorithm, model, threshold, and library choices are never listed. If the report
is surfacing those, the research loop is escalating when it should be researching — say so
plainly rather than presenting them as decisions.

## Continue-research context capsule

Only for an explicitly requested handoff or reusable context snapshot, append a
compact Chinese capsule. Do not repeat the ordinary brief in every status answer:

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

For a requested handoff, audit, or machine-readable snapshot, append this
**English-keyed YAML block** so a new session can parse the state. Ordinary human
briefs omit it; they still perform the same integrity check and disclose material
inconsistencies in plain language:

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

Emit it whenever a machine-readable snapshot is requested, even when state is inconsistent. Then
`integrity.state` is `inconsistent` and `integrity.findings` lists the codes. The block
is required for a handoff capsule: omitted integrity must never be mistaken for clean.

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

For a requested dashboard refresh, or an authorized milestone refreshing an existing
dashboard, follow [dashboard briefing](references/dashboard-brief.md). It writes only
ignored derived display data, never canonical state. Ordinary status queries still do
not write by default; an absent or stale web summary is disclosed rather than repaired
silently. The browser itself is always read-only.

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
