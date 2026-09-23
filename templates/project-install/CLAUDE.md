@AGENTS.md

# Claude Code adapter

Use project-local `.claude/skills/`; these are the same RE protocol installed for
Codex under `.agents/skills/`. `/research-resume` is sufficient to recover this
project read-only, brief the architect and wait. No Makefile launcher is required.
Do not treat `/resume` (client conversation history) as RE project recovery.

Model, authentication and permission policy belong to Claude's own settings. RE
does not change providers or inject a model alias. When using a DeepSeek backend,
do not pass a Claude model alias to subagents; preserve the configured backend model.
Cross-client handoff uses the shared `.research/` and Git, not another client's memory.
Never write this state concurrently with another research client.

The optional `make re-start CLIENT=claude` adds the terminal charset guard; direct
`claude` does not. Both use the same resume skill. Project settings block known
delivery-workflow skills; new machine plugins require checking/updating that policy.
