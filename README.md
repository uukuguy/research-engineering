# research-engineering

> An open protocol and tooling kit for AI agents doing **applied-AI research** —
> where the system doesn't yet exist, the evaluator might be wrong, and "done"
> is a belief update, not a green CI.

[![status](https://img.shields.io/badge/V1%20tool%20layer-closed-green)](#status)
[![tests](https://img.shields.io/badge/tests-304%20passing-brightgreen)](#status)
[![drill](https://img.shields.io/badge/drill%20suite-8%2F9-blue)](#status)
[![python](https://img.shields.io/badge/python-3.12%2B-blue)](#status)
[![license](https://img.shields.io/badge/license-MIT-blue)](#license)

[English](README.md) · [中文](README.zh-CN.md)

---

## What is research-engineering

Most AI coding agents (Claude Code, Codex, pi, and others) are built to **ship
software**. They assume the system runs, tests catch regressions, and "done"
means the build is green.

Applied-AI research breaks every one of those assumptions. The system may not
exist yet. The evaluator may be wrong. The data may not be there. "Cheap
evidence first" beats "comprehensive test suite". And "done" is a **finding
that survives evidence** — not a green CI.

`research-engineering` is the thin layer that keeps an AI agent in *research*
instead of *delivery*. It gives the agent a durable state protocol, a
deterministic bookkeeping tool, and a small set of skills — enough to record
what was tried, what was learned, and what to do next, across session
boundaries.

It does **not** pick hypotheses, decide keep-or-revert, call a model, or
repair its own state. Those need scientific content, and a tool that invents
that content is inventing evidence.

---

## Why it exists

Three failure modes show up repeatedly when delivery-shaped agents are pointed
at research problems:

1. **Scaffolding trap.** The agent builds a clean repo skeleton, types
   everything, gets a green build — and never finds out if the mechanism
   actually holds, because no evaluator was trusted and no evidence was
   recorded.
2. **Metric gaming.** The evaluator looks like it works, so the agent
   optimizes it. The number goes up. Nobody checks whether the underlying
   causal claim is still true.
3. **Belief amnesia.** Each new session starts from a blank chat. The agent
   re-derives what was learned last week, contradicts the previous
   hypothesis, and re-does the work that was already done.

`research-engineering` exists because all three are state problems. The fix
is **durable, append-only evidence** that survives the session boundary,
plus a **research / integration mode distinction** so the agent doesn't
treat an unverified hypothesis like a delivered feature.

---

## Quick start

```bash
# 1. Clone (or copy the tools/ and skills/ directories into your own repo)
git clone https://github.com/uukuguy/research-engineering
cd research-engineering

# 2. Install the skills into your agent's discovery directory
python3 tools/install_research_skills.py --target /path/to/your-project

# 3. Initialise a research repo (creates research/ACTIVE.json + skeleton)
cd /path/to/your-project
python3 /path/to/research-engineering/tools/researchlog init

# 4. Run a sanity check (verifies schema, state, git consistency)
python3 tools/researchlog reconcile

# 5. Record your first evidence
python3 tools/researchlog record \
    --question "does the mechanism hold?" \
    --subject-type mechanism --subject-id M-001 \
    --level E1 --execution-status completed \
    --research-outcome inconclusive --belief-delta none \
    --confidence low \
    --observation "first observation" --no-experiment
```

That's it. The repo now has its first evidence record, ACTIVE.json has been
updated, and the next session can resume from the durable state — no chat
context required.

---

## How it works

### Research vs. Integration Mode

The whole design turns on a single distinction:

|                    | **Research Mode** (default)              | **Integration Mode** (after promotion)       |
| ------------------ | ----------------------------------------- | --------------------------------------------- |
| Goal               | information gain, validated behaviour     | stable, reproducible baseline                  |
| Code               | disposable, minimal correctness            | maintained, stable interfaces                  |
| Tests              | only what protects experimental validity  | selective regression                            |
| Full test suite    | not run                                    | required at promotion                           |
| Promotion criterion | a finding survives evidence                | promotion review by the architect                |

A mode is a regime, not a project attribute. The same repo flips modes at
a promotion boundary; the agent stays in Research Mode until the architect
promotes it. **Knowing which mode you are in is the whole game.**

### The protocol

```
   Research Question / Technical Uncertainty
                       │
                       ▼
            Research Subject
        (idea / mechanism / component / slice / system)
                       │
                       ▼
            Evidence Acquisition
   (reasoning / probe / replay / spike / simulator / judge)
                       │
                       ▼
       Observation → Belief Update → next intervention
```

The core invariant: **evidence is the stable abstraction**, not
candidate-or-evaluator. A project may start with nothing but a problem
statement, an SDK, and some data — and the system has to work from there.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Agent loop (Claude Code · Codex · pi)                       │
│  reads AGENTS.md at session start                            │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   ┌─────────┐         ┌─────────┐         ┌──────────────┐
   │ Skills  │         │  tools/ │         │   research/  │
   │  (8)    │         │research │         │ ACTIVE.json  │
   │         │         │   log   │         │ CURRENT.md   │
   │ router  │         │         │         │ ARCHITECT.md │
   │ table   │         │ 20 sub- │         │ FINDINGS.md  │
   │         │         │commands │         │ ledger/      │
   │         │         │         │         │ runs/        │
   └─────────┘         └─────────┘         └──────────────┘
```

**Skills** (8) live in `skills/` and are copied into `.claude/skills/` and
`.agents/skills/` by the installer. The main router picks which skill to
load based on observation, not on the agent's preference.

**`tools/researchlog`** is a zero-dependency Python CLI. Every subcommand
returns a JSON envelope — the agent branches on `exit_code` and reads
`findings`, never parses prose. Same inputs, same outputs, no wall-clock
drift.

**`research/`** carries the durable state. The agent reads it at the start
of every session and treats it as the only source of truth — chat context
is disposable by design.

---

## Commands

The most-used `researchlog` subcommands:

```bash
researchlog init            # create the research state skeleton
researchlog validate        # schema + invariant check
researchlog reconcile       # ACTIVE ↔ Git ↔ runs ↔ evidence
researchlog record          # append an evidence record
researchlog run             # execute an experiment, capture provenance
researchlog compare         # common measurements + attribution between two EVs
researchlog findings        # durable beliefs (Established / Provisional / Refuted / ...)
researchlog synthesize      # block-close 1-2 page synthesis for the architect
researchlog telemetry       # §21 productivity KPI table
```

The full 20-subcommand reference lives in `docs/V1_ACCEPTANCE_GUIDE.md`
and the in-tool `--help`.

---

## Documentation

| Document | What it is |
| --- | --- |
| [`docs/WORK_LOG.md`](docs/WORK_LOG.md) | Dated, append-only record of developing this tool. **Start here** if you want to follow the work. |
| [`docs/V1_ACCEPTANCE_GUIDE.md`](docs/V1_ACCEPTANCE_GUIDE.md) | V1 acceptance criteria, drill protocols, measured results. |
| [`docs/V1_CASES.md`](docs/V1_CASES.md) | V1 drill suite — each drill has an executable command and a PASS signal. |
| [`docs/GOTCHAS.md`](docs/GOTCHAS.md) | Traps currently live in the codebase. Kept as **state**, not a log: a fixed trap is deleted. |
| [`docs/RESEARCH_ENGINEERING_V1.5_REVIEW.html`](docs/RESEARCH_ENGINEERING_V1.5_REVIEW.html) | Design review and revision log. |

The canonical contract for AI agents is [`AGENTS.md`](AGENTS.md) — it's
always-loaded. The detailed protocol lives in the skills and is loaded on
demand.

---

## Contributing

This is an active research project. The honest shape of "how to
contribute" is:

1. Read [`docs/WORK_LOG.md`](docs/WORK_LOG.md) to see what's in flight and
   what just closed.
2. Read [`docs/GOTCHAS.md`](docs/GOTCHAS.md) before touching anything —
   traps are state, not a log.
3. For protocol changes: write an entry in `docs/WORK_LOG.md` first; the
   `Core invariants` block in `AGENTS.md` is the contract.
4. For new skills: add to `skills/` (canonical) and re-run
   `tools/install_research_skills.py --target <your test repo>`.
5. Tests run in `tools/researchlog/tests/` — run with
   `PYTHONPATH=tools python3 -m unittest discover -t tools -s tools/researchlog/tests`.

---

## License

MIT. See [LICENSE](LICENSE).

---

## Status

<a name="status"></a>

- **V1 tool layer is closed** as of 2026-09-19. Drill suite **8/9** complete.
- **45 PASS + 0 deferred + 4 ENV_BLOCKED** across 49 acceptance criteria.
- **304 tests passing** across `tools/researchlog/tests/`.
- The remaining 4 ENV_BLOCKED are M6/M7 claude-pending under the
  minimax-compat endpoint this sandbox uses — they resolve when a
  native Anthropic subscription is available.
- The repo's own `research/ACTIVE.json` is **idle** — V1 closure is a
  delivered, not running, artifact.

What is *not* in scope here: the project's own live research activity.
New research is gated on Architect decisions (extend telemetry,
switch endpoint, or pick a hypothesis).