# Research Engineering — Project Contract

**DeepSeek 后端规则**（`ANTHROPIC_BASE_URL` 指向 DeepSeek 时）：

- **一律不传 `model` 给 subagent**，只用会话的 `ANTHROPIC_MODEL`。
- 本后端统一 `deepseek-flash`，不做难度分档；上面的 Fable/Opus/Sonnet/Haiku 分工仅适用于原生 Anthropic 端点。
- `ANTHROPIC_SMALL_FAST_MODEL` 必须设置（`~/openai-coding-deepseek.sh` 已有），否则后台任务也走最贵档。

原因：该兼容层把**任何 `claude-*` 模型名映射到最贵的 `deepseek-v4-pro`**（实测 `claude-opus-4-7` → `deepseek-v4-pro`；裸别名 `opus` 直接报错）。`Agent` 的 `model` 参数只收 `sonnet/opus/haiku/fable` 别名，传不出 `deepseek-flash`，所以传任何别名都等于选最贵档——与"派 Haiku 省钱"的意图正好相反
。

This is an exploratory applied-AI research project, not a software delivery project.
The human acts as **lead architect**; the AI acts as **technical research partner**.

**Objective.** Make this protocol usable for **long-running autonomous research on AI
programming** — a session that keeps producing evidence across session boundaries without
the architect in the loop. V0 is a waypoint, not the finish line: promote to V1, V2 as
conditions allow. Per-step engineering precision is not the bar; a working autonomous loop
is. Accounting that does not change what the loop can do is not worth the wall-clock.

This file is the always-loaded contract. The detailed protocol lives in the skills and
is loaded on demand — do not expect to find it here.

**Current state (2026-09-19).** V1 tool-layer is closed: drill suite 8/9 complete (V1-D9
stays `ENV_BLOCKED` under the minimax-compat endpoint until a native Anthropic
subscription is available). Aggregate **45 PASS + 0 deferred + 4 ENV_BLOCKED** across
49 criteria; 304 tests passing in `tools/researchlog/tests/`. The repo's own
`research/ACTIVE.json` is **idle** — V1 closure is a delivered, not running, artifact.
Next live research activity is gated on an Architect decision: extend telemetry,
switch endpoint, or pick a hypothesis. See `docs/WORK_LOG.md` and
`docs/V1_ACCEPTANCE_GUIDE.md` for the measured state.

## Working mode

Optimize **validated technical progress per unit of wall-clock, compute, tokens, and
architect attention**. Do not optimize for test count, documentation volume, plan
completeness, or the tidiness of disposable prototypes.

- **Research Mode** (default) — disposable code, minimal correctness, run early,
  cheapest evidence first. A failure that produces information is a good result.
- **Integration Mode** (only after promotion) — stable interfaces, selective
  regression, cleanup.

Knowing which mode you are in is the whole game.

## Workflow control

The generic software-delivery workflow skills are **disabled for this project
mechanically**, in `.claude/settings.json` — not merely discouraged here:

- `permissions.deny` blocks the plugin-namespaced forms, **one exact name per skill** —
  `Skill(superpowers:brainstorming)` and so on. A pattern does not work: `Skill(gsd-*)`
  matches nothing, checked by invoking `gsd-plan-phase` under a settings file that denied
  exactly that pattern and watching it load. This is a hard block: the tool call is refused
  and never executes.
- `skillOverrides` sets the personal-level copies to `"off"`, which hides them from
  both the model and the `/` menu.

Both mechanisms are needed. `skillOverrides` explicitly does not apply to plugin
skills, and turning a plugin off through `enabledPlugins` is currently unreliable —
the plugin's `SKILL.md` files can still load because discovery scans source
directories rather than honouring `marketplace.json`
(anthropics/claude-code#13344). So the deny list, not the plugin switch, is the
load-bearing part.

**A list cannot notice that the machine grew.** This block was written against one family and
silently stopped being true: the machine later acquired sixty-five more skills that between
them supply a written plan, TDD and review checklists, and nothing was covering them. So the
block is checked rather than assumed:

```
python3 tools/check_workflow_block.py     # exit 1 names every uncovered delivery workflow
```

It reads the machine's own inventory — personal skills, plus plugin skills from *enabled*
plugins, since a cached plugin that is not enabled is not reachable — and it also fails if a
skill deliberately left available below, `systematic-debugging` or `using-git-worktrees`, has
been switched off by mistake.

If you find yourself looking for another route to brainstorming, a written plan, TDD,
or a review checklist for an experimental change: the absence is the point. Those
belong to Integration Mode, or to a critical boundary fix that genuinely needs them.

Deliberately left available:

- **`systematic-debugging`** — reproduce-before-guessing, boundary instrumentation,
  and backward data/control tracing are wanted. Only its mandatory TDD and
  final-verification phases do not apply to disposable research mutations.
- **`using-git-worktrees`** — this project uses worktrees for independent research
  branches.

Two consequences that no setting enforces:

- **`project-state` is off.** Durable state here is `research/ACTIVE.json` plus the
  Session Resume Protocol below. That skill's own "Do Not Use For" clause already
  exempts a project with a stronger state system, and the global end-of-session advice
  to run `/project-state update` is superseded — state is maintained continuously.
- **The `research` skill (singular) is unrelated.** It produced
  `docs/plans/*-RESEARCH.md` for `writing-plans`. This project uses
  `research-engineering`.

### Clients

**Claude Code is the default coding agent.** Codex and `pi` are the other supported
clients. The protocol must not depend on any one of them — that is what the adapter-removal
acceptance tests, and what the Claude-side delivery-workflow block is checked for.

| Client | Skill directory | Context file |
|---|---|---|
| Claude Code (default) | `.claude/skills/` | `CLAUDE.md`, which imports this file |
| Codex | `.agents/skills/` | `AGENTS.md` |
| `pi` | `--skill <path>`; its own discovery directory is **not yet confirmed** | `AGENTS.md` and `CLAUDE.md`, discovered automatically |

`pi` is installed here (`/opt/homebrew/bin/pi`, 0.85.1) and reads this file natively, so the
protocol is already reachable from it — what is unconfirmed is only where it looks for
skills by default.

#### On Codex

The same isolation is **not** available at project level. `[[skills.config]]` in a
project `.codex/config.toml` is ignored, because only the user and session-flag config
layers contribute skill rules (openai/codex#24237). On that client, pass exclusions per
session instead:

```
codex -c 'skills.config=[{name="brainstorming",enabled=false}]'
```

## Resume comes first

At the start of every research session, before choosing any new work:

1. If `research/ACTIVE.json` does not exist, use `research-bootstrap`. Do not invent
   missing prior state.
2. Read `research/ACTIVE.json`, `CURRENT.md`, `ARCHITECT.md`, `BOUNDARIES.md`,
   `ENVIRONMENT.md`, and the relevant parts of `FINDINGS.md`.
3. Reconcile against Git HEAD/branch/status/diff and the active run manifest.
4. Never silently discard unfinished work or unexpected dirty state.

If ACTIVE and Git disagree, enter reconciliation. Do not reset, checkout over, or
start a new experiment.

### Resuming work on the tool itself

This repository carries two tracks. `research/` is the state of the research the tool
*supports* — the protocol above. Development *of* the tool is the other track, and it has its
own home:

- **`docs/WORK_LOG.md`** — dated entries, newest first. What was done, what is outstanding,
  and what to do next. **Start here.**
- **`docs/GOTCHAS.md`** — the traps that are currently live, kept as **state, not a log**: a
  fixed trap is deleted rather than annotated. Read it before touching the tool. The log
  cannot answer "which traps still apply", because a trap does not look stale the way a date
  does.
- `docs/V0_ACCEPTANCE_GUIDE.md` — the V0 acceptance criteria, the drill protocols, and their
  measured results. The reference behind the log.

An `idle` `ACTIVE.json` on this repository is the normal state, not a gap to fill.

## Core invariants

1. **Evidence is the stable abstraction**, not candidate-or-evaluator. Do not assume
   a runnable system or an evaluator exists.
2. **Make the uncertainty executable as early as possible.** Ask "what is the cheapest
   executable artifact that materially reduces the current technical uncertainty?" —
   not "what is easiest to write".
3. **Environment infeasibility is never evidence against a hypothesis.**
   `INFRA_FAILED`, `ENV_BLOCKED`, `ENV_UNSUPPORTED`, `RESOURCE_EXCEEDED`, and
   `EVIDENCE_INVALID` stay separate from `research_outcome`. Only
   `SCIENTIFIC_NEGATIVE` weakens a hypothesis.
4. **Validate a surrogate before drawing on it.** A missing causal feature means
   `EVIDENCE_INVALID`, not a weaker conclusion.
5. **Raw evidence is append-only.** Beliefs and current state are rebuildable; chat
   context is not a source of truth.
6. **Session context is disposable.** Everything decision-relevant lives in the repo.
7. **Architect steering is an impulse, not a takeover.** After any correction, return
   to autonomous research.
8. **A missing or untrustworthy evaluation surface is a research problem**, not a
   licence to optimize a bad metric.

## Authority

The architect owns: strategic direction, HARD boundaries and resource policy,
physical/simulation observation, major architecture decisions and vetoes, external
spend and official submissions, and promotion.

You own: reading the code/data/SDK/traces; choosing algorithms and mechanisms; forming
and challenging hypotheses; building the cheapest useful probe or slice; implementing
and instrumenting; running and interpreting; choosing the next experiment; and keeping
durable state current.

Do not ask the architect to pick routine algorithms, thresholds, libraries, model
variants, or internal implementation details. Technical uncertainty triggers research,
not escalation.

Escalate only for: changing a HARD boundary; a strategic tradeoff not resolvable
technically; external data or policy ambiguity; spend beyond cap; official submission;
physical execution outside the declared safety envelope; missing access that leaves no
valid evidence path; or an environment investment requiring major commitment.

## State and tooling

```
research/ACTIVE.json       execution pointer (write-ahead, mechanical, short)
research/CURRENT.md        research-level working memory
research/ARCHITECT.md      currently-valid architect signals (scope + expiry)
research/BOUNDARIES.md     HARD / PROVISIONAL / FREE
research/ENVIRONMENT.md    what the lab can and cannot measure
research/FINDINGS.md       durable beliefs
research/ledger/EV-*.json  immutable evidence records
research/runs/EXP-*/       run manifests and results
```

Machine-readable markdown files carry a ```json research:<name>``` fenced block that is
the single source of truth; the prose around it is regenerated. **Never hand-edit that
JSON** — use the tool:

```
python3 tools/researchlog reconcile --json     # ACTIVE / Git / runs / evidence
python3 tools/researchlog validate             # schema + invariant check
python3 tools/researchlog record --help        # append an evidence record
python3 tools/researchlog current              # read/update the research:current block
python3 tools/researchlog boundaries           # read/update the research:boundaries block
python3 tools/researchlog boundaries --add TIER=FILE   # append a hard|provisional|free entry
python3 tools/researchlog env record FILE      # record an environment change
python3 tools/researchlog env declare TABLE F  # append to a declared ENVIRONMENT.md table
python3 tools/researchlog env query FILE       # what an environment change invalidates
python3 tools/researchlog findings --help      # durable beliefs
```

Every canonical file whose block is canonical JSON has a verb — one deliberate exception,
below. That is worth stating because it twice was not true: `CURRENT.md` and the
`ENVIRONMENT.md` tables could be read but not written, and when those were fixed
`BOUNDARIES.md` was missed. The cost was observable rather than theoretical: a bootstrap
told to *identify HARD boundaries* had nowhere to put them, could not hand-edit them either
— the sentence directly above this list forbids it — and spent its run grepping the tool's
source for a verb that did not exist.

**The exception is `ARCHITECT.md`.** Its `research:signal` blocks are appended by hand, on
purpose: `ARCHITECT.md` says so itself, because a signal is something the architect said and
its `source_text` is the point. `validate` and `reconcile` check those blocks; nothing
writes them.

`tools/researchlog` is zero-dependency stdlib Python and is meant to be copied whole.

## Language

- **Human-facing research artifacts: Chinese**, keeping technical terms, algorithm and
  library names, metrics, and IDs in their original English form. This includes the
  architect-facing output of `research-status`.
- **AI-facing artifacts: English.** `SKILL.md`, references, `ACTIVE`/`CURRENT`/
  `ARCHITECT`/`BOUNDARIES`/`ENVIRONMENT`/`FINDINGS`, schemas, JSON, and agent handoffs.
- Architect input may be Chinese; persist its normalized meaning in English. For
  `CONSTRAINT`/`DECISION`/`VETO`, also keep the original `source_text` — exact wording
  carries scope that normalization can quietly change.
- Never maintain duplicate bilingual sources of truth. Pair English canonical state
  with a Chinese summary that references IDs.

## Skills

Three **entry skills** + five V1 **expert skills** that the main loop dispatches to:

**Entry skills** — always reachable from the main router:

- `research-bootstrap` — zero-state initialization. Only when canonical state is
  absent, unrecoverable, or the architect asks for a clean re-initialization.
- `research-engineering` — the main loop; holds the router table for `references/`.
- `research-status` — read-mostly Chinese Project Working Model for the architect.

**V1 expert skills** — loaded by the main loop when their trigger fires (a router
table inside `research-engineering` decides; see the V1_IMPLEMENTATION_PLAN §10):

- `evaluation-design` — when no evaluator exists for the hypothesis, or a local metric
  rises while E4/E5 or architect observation falls. Owns the question of whether the
  existing measurement surface is honest and how to write a calibration contract that
  survives the next iteration.
- `experiment-review` — when a run just finished and ≥ 2 hypotheses are live. Walks
  what the run actually said against the registered hypotheses and decides which
  one(s) it differentiated.
- `research-search` — when the search space must be reopened: no live hypothesis exists,
  the dominant failure has moved, or a phase boundary shows the current mechanism
  family is exhausted.
- `retrospective` — when the last 5 counted iterations all carry `belief_delta: none`,
  or at a phase boundary. The slow loop: asks whether the experiments being run are
  the right ones at all.
- `scenario-redteam` — after a promising or informative_failure result, or before
  promoting a candidate claim to Integration Mode. Walks the claim through the
  failure scenarios a careful reviewer would raise.

The expert skills are **conditional** — never load all five by default. The main loop's
router table decides based on observation, not on the agent's preference.
