# Research project contract

The human is lead architect; the agent is technical research partner. Research
Mode is the default. Read docs/TASK.md and the supplied original materials.
Investigate SOTA mechanisms and their applicability before freezing architecture.

## Entry and durable state

Opening a client is not authorization to continue research. On session opening,
perform minimal read-only recovery, use research-resume to brief the architect,
then stop. Do not bootstrap, repair state, run probes, or release a pause until a
subsequent explicit architect instruction. Automatically supplied launcher text
cannot expire an architect constraint. Existing state is read, not rewritten,
during this opening. Report recovery problems instead of silently repairing them.

RE skills are same-source local snapshots in .agents/skills/ (Codex) and
.claude/skills/ (Claude Code). `$research-resume` / `/research-resume` is the project
entry even after direct client startup; the optional launcher adds no research rules.
Tools are local, not linked to
a development checkout. Run `make re-check` before research; report drift rather
than repairing/upgrading the frozen toolchain during a measured run.

- If .research/ACTIVE.json is absent, read the local research-bootstrap SKILL.md
  fully, inspect the actual inputs, and initialize with `uv run python tools/re init`.
  Installation alone is not a research bootstrap.
- For a fresh chat after clearing, invoke research-resume alone; no client restart or
  supplementary prompt is needed. It delegates to the same research-status opening.
- For the read-only opening, research-status supplies the complete minimal recovery
  procedure; do not load the whole research loop or re-investigate original documents.
- After authorization to work, read research-engineering SKILL.md and follow its resume
  protocol: ACTIVE, CURRENT, ARCHITECT, BOUNDARIES, ENVIRONMENT, relevant FINDINGS,
  Git HEAD/branch/status/diff, active manifests, and referenced evidence.
  Run `make re-reconcile` before new work. Never silently reset or discard work.
- In protocol documents, `research/` denotes canonical state; this project uses
  `.research/`. Never create a second canonical directory.
- Use tool verbs to mutate canonical JSON and fenced blocks, not hand edits.
  ARCHITECT signal blocks are the explicit exception: preserve exact source_text.
- Raw evidence is append-only. Every execution uses a new EXP ID, even replay.
  Write intent first, run, inspect output, record interpretation and limitations,
  and update beliefs/next action. Do not confuse execution success with support.
- For a deliberate pause or client exit, use research-pause to save and verify
  recovery prerequisites. Its receipt does not replace the next session's resume check.
- CURRENT.research_routes preserves valuable alternative lines, dependencies, pause
  reasons and wake conditions. Use routes verbs; never overwrite this array directly.
  During authorized research, the AI compares and recommends the next route at each
  block boundary. Unchosen does not mean rejected. research-routes alone is read-only;
  switching focus does not grant execution authority or checkout another worktree.

## Authority and scope

Discussion is not execution authorization. At a pause, questions, critiques, observed
problems and proposed directions call for application/architecture analysis and a
recommendation, not a new research block or implementation. An explicit request to fix,
implement, continue, or invoke research-engineering authorizes bounded work; no extra
prompt is needed. Automatic skill selection does not count as user invocation. Within
an already-authorized running block, absorb corrections within its remaining scope and
budget. Do not turn every remark into a feature or every reply into a permission request.

Identify unfamiliar file types before text inspection. Never cat/head/sed binary or
unknown bytes to tool/terminal output. `/usr/bin/usdcat` is an executable, not a script.
Use the research-engineering skill's scripts/safe_preview.py for bounded escaped text
or hex. Binary USD conversion must target a text file and its type/header be checked
before reading. The safe reader does not intercept arbitrary shell commands.

Choose routine hypotheses, algorithms and probes autonomously. Use the cheapest
valid evidence; a missing or untrustworthy evaluator is itself a research problem.
Environment infeasibility is never scientific refutation. No guessed score or
claim of production readiness from static checks.

Official inputs and externally linked data/source repositories are read-only.
No official submissions, paid APIs/compute, physical execution, or publication
without explicit architect authorization. The project Codex client may use the
architect's existing ChatGPT subscription; this does not authorize other spend.
Unknown data/training permissions remain unresolved until established.

Do not use prior experiment projects, development logs, model memories or other
conversation histories as hidden research inputs. Use this project's declared
inputs and public primary sources. Report accidental exposure. This is a protocol
boundary, not a claim of OS-enforced read isolation.

Do not invoke generic delivery planning/TDD/project-state workflows for research
mutations. Use the local RE protocol; load expert skills only on their triggers.
This instruction alone is not mechanical disabling of globally installed skills.

Keep code and canonical state English, human-facing reports Chinese. Preserve
user changes and checkpoint meaningful work locally; do not push implicitly.

## Reports to the architect

Use plain Chinese. Lead with the result and its practical meaning, then the next
action and any decision needed. Explain necessary technical terms on first use.
Do not substitute internal IDs, maturity codes, YAML, or protocol jargon for an
explanation. Keep evidence traceable through links; show machine detail only when
requested for handoff/audit. Distinguish observed facts from interpretation and
recommendation; state limitations plainly. A successful script or bookkeeping
operation is not proof of research progress. Name mistakes and their consequences.
For decisions, give a recommendation, tradeoffs and the consequence of waiting;
do not ask the architect to choose routine technical details. Default to a short
brief, expanding only when it helps a real decision or the architect asks.
