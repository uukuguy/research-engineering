# Research Engineering — Project Contract

This is an exploratory applied-AI research project, not a software delivery project.
The human acts as **lead architect**; the AI acts as **technical research partner**.

This file is the always-loaded contract. The detailed protocol lives in the skills and
is loaded on demand — do not expect to find it here.

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

- `permissions.deny` blocks the plugin-namespaced forms (`Skill(superpowers:*)`).
  This is a hard block: the tool call is refused and never executes.
- `skillOverrides` sets the personal-level copies to `"off"`, which hides them from
  both the model and the `/` menu.

Both mechanisms are needed. `skillOverrides` explicitly does not apply to plugin
skills, and turning a plugin off through `enabledPlugins` is currently unreliable —
the plugin's `SKILL.md` files can still load because discovery scans source
directories rather than honouring `marketplace.json`
(anthropics/claude-code#13344). So the deny list, not the plugin switch, is the
load-bearing part.

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

### On Codex

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

This repository is two tracks. `research/` is the state of the research the tool *supports*
— the protocol above. Development *of* the tool is the other track, and its handoff is
**`docs/status/RESUME-NEXT-SESSION.md`**, with the commit log and
`docs/V0_ACCEPTANCE_GUIDE.md` as its record. If you are here to work on the tool, start
there. An `idle` `ACTIVE.json` on this repository is the normal state, not a gap to fill.

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
python3 tools/researchlog env query FILE       # what an environment change invalidates
python3 tools/researchlog findings --help      # durable beliefs
```

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

- `research-bootstrap` — zero-state initialization. Only when canonical state is
  absent, unrecoverable, or the architect asks for a clean re-initialization.
- `research-engineering` — the main loop; holds the router table for `references/`.
- `research-status` — read-mostly Chinese Project Working Model for the architect.
