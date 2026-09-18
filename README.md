# Research Engineering

A protocol and a small set of tools for **AI coding agents** to do **applied-AI research**
— not just write code. Built around one claim: when you don't yet know whether the thing
works, the only thing worth keeping is the **evidence** of what you tried.

> Chinese version: [README.zh-CN.md](README.zh-CN.md)

## The problem this solves

Most AI coding agents — Claude Code, Codex, `pi`, and others — are built for **software
delivery**. Their workflow assumes:

- The system is already runnable.
- Tests catch regressions.
- "Done" means tests pass.

Applied-AI research is the opposite:

- The system may not exist yet, or the data isn't there, or the evaluator isn't trustworthy.
- "Cheap evidence first" beats "comprehensive test suite".
- "Done" is a **belief update** — a finding that survives evidence — not a green CI.

If you point a delivery-shaped agent at a research problem, it tends to either:
build scaffolding for hours without finding out if the mechanism holds, or quietly
optimize a wrong metric because the evaluator looks like it works. **Research
Engineering** is the thin layer that keeps an agent in *research* instead.

## What it actually is

Three things, kept small:

| Component | What it does | Where |
|---|---|---|
| **Skills** | In-context instructions for the agent: bootstrap a research repo, run the main loop, write a status report for the architect. | `skills/` (canonical) — copied to `.claude/skills/` and `.agents/skills/` by the installer |
| **Bookkeeping tool** | `researchlog` — a zero-dependency CLI that keeps `research/ACTIVE.json` (the execution pointer), the ledger of evidence, and the durable state in sync. | `tools/researchlog/` |
| **Canonical state files** | `research/ACTIVE.json`, `CURRENT.md`, `ARCHITECT.md`, `BOUNDARIES.md`, `ENVIRONMENT.md`, `FINDINGS.md`. The agent reads these at the start of every session; they are the durable memory of a project. | `research/` |

The agent itself picks hypotheses, runs experiments, interprets results. The tool
**never** picks a hypothesis, never decides keep-or-revert, never calls a model, never
repairs state on its own — those require scientific content, and a tool that invents
that content is inventing evidence.

## Two modes, one boundary

The whole design turns on a single distinction:

| | Research Mode (default) | Integration Mode (after promotion) |
|---|---|---|
| Goal | validated behaviour, information gain | stable, reproducible baseline |
| Code | disposable, minimal correctness | maintained, stable interfaces |
| Tests | only what protects experimental validity | selective regression |
| Full regression suite | not run | required at promotion |

A mode is a regime, not a project attribute. The same repo can flip modes at a
promotion boundary; the agent stays in Research Mode until the architect promotes it
to Integration Mode. Knowing which mode you're in is the whole game.

## The protocol in one diagram

```
Research Question / Technical Uncertainty
        ↓
Research Subject   idea / mechanism / component / slice / system
        ↓
Evidence Acquisition   reasoning / probe / replay / spike / simulator / judge
        ↓
Observation → Belief Update → next intervention
```

The core claim: **evidence is the stable abstraction**, not candidate-or-evaluator.
A project may start with nothing but a problem statement, an SDK, and some data.
The system has to work from there.

## Layout

```
README.md / README.zh-CN.md   this file (English / Chinese mirror)
AGENTS.md                     always-loaded contract for AI agents
CLAUDE.md                    (one-line import of AGENTS.md, Claude Code)
skills/                       canonical skill source (8 skills)
  research-bootstrap/         zero-state initialization
  research-engineering/       the main loop; holds the router table for references/
  research-status/            read-mostly Project Working Model for the architect
  evaluation-design/          V1 expert skill: when the evaluator is untrustworthy
  experiment-review/           V1 expert skill: review a run against live hypotheses
  research-search/            V1 expert skill: reopen the search space
  retrospective/              V1 expert skill: the slow loop
  scenario-redteam/           V1 expert skill: red-team a candidate claim
tools/
  install_research_skills.py   copy skills/ into .claude/skills and .agents/skills
  check_workflow_block.py      exit 1 if any delivery-workflow skill is uncovered
  researchlog/                 zero-dependency state bookkeeping (20 subcommands)
research/                     this repo's own live research state
templates/research/            skeleton that `researchlog init` copies into a new project
docs/
  WORK_LOG.md                 dated, append-only record of developing this tool (start here)
  GOTCHAS.md                  traps that are currently live, kept as state not a log
  V0_ACCEPTANCE_GUIDE.md      V0 acceptance criteria and measured results
  V1_ACCEPTANCE_GUIDE.md      V1 acceptance criteria and measured results
  V1_CASES.md                 V1 drill suite, executable commands + PASS signals
  RESEARCH_ENGINEERING_V1.5_REVIEW.html   design review and revision log
```

## Using it in another repository

```bash
git clone https://github.com/uukuguy/research-engineering
python3 tools/install_research_skills.py --target /path/to/project
cd /path/to/project && python3 tools/researchlog init
```

`install_research_skills.py --check` diffs the canonical skills against the installed
copies and exits non-zero on drift. Run it after `git pull` to catch skill-block drift.

## What `researchlog` does

```bash
python3 tools/researchlog init          # create the research state skeleton
python3 tools/researchlog validate      # schema + invariant check
python3 tools/researchlog reconcile     # ACTIVE ↔ Git ↔ runs ↔ evidence
python3 tools/researchlog record        # append an evidence record
python3 tools/researchlog run           # execute an experiment, capture provenance
python3 tools/researchlog compare       # common measurements + attribution between two EVs
python3 tools/researchlog env           # record/query environment changes
python3 tools/researchlog findings      # durable beliefs (Established / Provisional / ...)
python3 tools/researchlog synthesize     # block-close 1-2 page synthesis for the architect
python3 tools/researchlog telemetry      # §21 productivity KPI table
python3 tools/researchlog checkpoint     # recoverable Git checkpoint
python3 tools/researchlog current        # read/update research:current block
python3 tools/researchlog boundaries     # read/update research:boundaries block
python3 tools/researchlog active         # rotate session, open/close block, set status
```

Every subcommand returns a JSON envelope (`exit_code`, `findings`, `payload`) so the
agent branches on a number and never parses prose. Outputs are deterministic —
same inputs, same outputs, no wall-clock drift in the answers.

## Core invariants (what it does *not* do)

1. **Evidence is the stable abstraction**, not candidate-or-evaluator. Don't assume
   the system is runnable or the evaluator is trustworthy.
2. **Environment infeasibility is never evidence against a hypothesis.** `INFRA_FAILED`,
   `ENV_BLOCKED`, `ENV_UNSUPPORTED`, `RESOURCE_EXCEEDED` stay separate from
   `research_outcome`. Only `SCIENTIFIC_NEGATIVE` weakens a hypothesis.
3. **Validate a surrogate before drawing on it.** A missing causal feature means
   `EVIDENCE_INVALID`, not a weaker conclusion.
4. **Raw evidence is append-only.** Beliefs and current state are rebuildable; chat
   context is not a source of truth.
5. **Session context is disposable.** Everything decision-relevant lives in the repo.

## Status

**V1 tool layer is closed** as of 2026-09-19. Drill suite 8/9 complete; the remaining
1/9 (V1-D9, M6/M7 claude-pending) is `ENV_BLOCKED` under the minimax-compat endpoint
that this sandbox uses — they will resolve when a native Anthropic subscription is
available. Aggregate: **45 PASS + 0 deferred + 4 ENV_BLOCKED** across 49 criteria.
304 tests passing across `tools/researchlog/tests/`.

Three files carry the state of the work:

- **`docs/WORK_LOG.md`** — start here. Dated, append-only record of developing this tool:
  what was done, what is outstanding, what to do next.
- `docs/V1_ACCEPTANCE_GUIDE.md` — V1 acceptance criteria, drill protocols, measured
  results.
- `docs/V1_CASES.md` — V1 drill suite: executable commands + PASS signals.
- `docs/GOTCHAS.md` — the traps that are currently live, kept as **state rather than a
  log**: a fixed trap is deleted, not annotated.

The repo's own `research/ACTIVE.json` is **idle** — V1 tool-layer closure is a
delivered, not running, artifact. New research activity is gated on Architect decisions
to extend telemetry, switch to a native Anthropic endpoint, or pick a hypothesis.

## Compatibility

- **Python 3.12+** (see `.python-version`).
- **Claude Code** (default), **Codex**, **`pi`** — protocol is agent-agnostic. The
  installer copies skills into `.claude/skills/` and `.agents/skills/`; `pi` reads
  this file natively.
- **Single-process, single-machine.** No scheduler, no server, no multi-tenant
  state. One research repo, one agent loop, one durable state on disk.

## Tests

```bash
PYTHONPATH=tools python3 -m unittest discover -t tools -s tools/researchlog/tests -v
```

304 tests, no network, no model calls. Run time ~30 seconds.

## License

Internal research project. See `docs/` for design lineage.