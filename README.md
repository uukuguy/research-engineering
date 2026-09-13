# Research Engineering

A thin **Research Operating Layer** for coding agents. It does not add a scheduler, a
server, or a workflow engine. It adds a small set of skills, a Git-backed state
protocol, and a zero-dependency bookkeeping tool — enough to keep an agent's default
behaviour in *research* rather than *software delivery*.

The core claim: **Evidence is the stable abstraction, not candidate-or-evaluator.** A
project may start with nothing but a problem statement, an SDK, and some data. The
system has to work from there.

```
Research Question / Technical Uncertainty
        ↓
Research Subject   idea / mechanism / component / slice / system
        ↓
Evidence Acquisition   reasoning / probe / replay / spike / simulator / judge
        ↓
Observation → Belief Update → next intervention
```

Two modes, and the boundary between them is the whole design:

| | Research Mode | Integration Mode |
|---|---|---|
| Goal | information gain, validated behaviour | stable, reproducible baseline |
| Code | disposable | maintained |
| Tests | only what protects experimental validity | selective regression |
| Full regression | not run | required at promotion |

## Layout

```
AGENTS.md              always-loaded contract (Codex reads it natively;
                       CLAUDE.md imports it for Claude Code)
skills/                canonical skill source — 3 entry skills + references/
  research-bootstrap/  zero-state initialization
  research-engineering/  the main loop; references/ holds conditional expert guidance
  research-status/     read-mostly Chinese Project Working Model
tools/
  install_research_skills.py   copy skills/ into .claude/skills and .agents/skills
  researchlog/                 zero-dependency state bookkeeping
research/              this repo's own live research state
templates/research/    skeleton that `researchlog init` copies into a new project
```

## Using it in another repository

```bash
python3 tools/install_research_skills.py --target /path/to/project
cd /path/to/project && python3 tools/researchlog init
```

`--check` diffs the canonical skills against the installed copies and exits non-zero on
drift.

## Tools

```bash
python3 tools/researchlog init          # create the research state skeleton
python3 tools/researchlog validate      # schema + invariant check
python3 tools/researchlog reconcile     # ACTIVE ↔ Git ↔ runs ↔ evidence
python3 tools/researchlog record        # append an evidence record
python3 tools/researchlog run           # execute an experiment, capture provenance
python3 tools/researchlog env           # record/query environment changes
python3 tools/researchlog findings      # durable beliefs
```

`researchlog` performs deterministic bookkeeping only. It never selects a hypothesis,
never decides keep-or-revert, never calls a model, and never repairs state on its own —
correcting an orphaned run requires scientific content, and a tool that invents that
content is inventing evidence.

## Tests

Requires Python 3.12 (see `.python-version`). On a machine whose `python3` is newer:

```bash
uv run python -m unittest discover -t tools -s tools/researchlog/tests -v
```

## Status

V0. Design baseline: `docs/research-engineering-complete-design-v1.5.docx`.
Review and revision log: `docs/RESEARCH_ENGINEERING_V1.5_REVIEW.html`.
