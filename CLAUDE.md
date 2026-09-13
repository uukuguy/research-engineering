@AGENTS.md

# Claude Code adapter

Project skills live under `.claude/skills/`. They are generated from `skills/` by
`tools/install_research_skills.py --self` — edit the canonical source, never the copy,
and run `--check` to detect drift.

Claude-specific hooks, subagents, and MCP servers may accelerate research, but removing
all of them must not change the protocol in `AGENTS.md`.
