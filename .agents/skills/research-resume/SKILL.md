---
name: research-resume
description: Restore an established RE project after clearing chat or starting a fresh session. Give a read-only application and research-route briefing, then wait; does not authorize research or initialize state.
---

# Research Resume

This invocation alone is sufficient. Recover from this project's persisted state,
not a previous chat, another project, or global memories. Use the project's declared
state directory and CLI; installed projects use `.research/` and `uv run python tools/re`.

This is the client-independent project entry, whether the client was started directly,
through a launcher, or after clearing chat. Codex invokes `$research-resume`; Claude
Code invokes `/research-resume`. No launcher-only prompt is required. Load the sibling
research-status skill from this same project installation, not a global older copy.
Do not import another client's chat, private memory, job IDs or worker sessions as state.
For a client handoff, inspect persisted unfinished execution; a new client cannot assume
ownership of an old client's background tools. Only one client may write canonical state.
Report missing client capabilities without upgrading tools or changing configuration.

Read the local research-status SKILL.md and follow its lightweight opening procedure.
It is the single recovery/briefing implementation; do not also load the full research
loop, re-extract original source documents, or duplicate its checks.

Explain in Chinese what application capability exists, what is actually demonstrated,
the current focus, materially different queued/parked/blocked routes, and the recommended
next step. CURRENT.research_routes, when present, holds route identities and restart
conditions. Its active route is a focus, not proof of a running process or permission.
If absent, report that routes are not registered; do not invent or migrate them in this
read-only opening. Missing state means report initialization needed, not bootstrap.

Stop after the brief. Do not repair, write metadata, wake routes, change priorities,
checkout branches, start experiments, or treat a saved next probe as authorization.
Report unfinished execution and inconsistencies before offering new research.

The user can deliberately close with research-pause, clear the chat, then invoke this
skill without restarting the client. This skill does not intercept `/clear`, install
hooks, or promise automatic invocation. The next explicit research-engineering invocation
or accepted instruction to continue can authorize a bounded block under existing limits.
