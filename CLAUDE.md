@AGENTS.md

# Claude Code adapter

Project skills live under `.claude/skills/`. They are generated from `skills/` by
`tools/install_research_skills.py --self` — edit the canonical source, never the copy,
and run `--check` to detect drift.

Claude-specific hooks, subagents, and MCP servers may accelerate research, but removing
all of them must not change the protocol in `AGENTS.md`.

## The workflow block

`AGENTS.md` says the generic software-delivery workflow skills are disabled for this project
mechanically, and that their absence is the point — brainstorming, a written plan, TDD, a
review checklist. This is where that claim is made true, and the two mechanisms are **not**
interchangeable:

- **`permissions.deny` takes an exact skill name.** `Skill(gsd-*)` matches nothing. That was
  checked by invoking `gsd-plan-phase` under a settings file denying exactly that pattern and
  watching it load. Plugin-namespaced skills need this mechanism, listed one by one.
- **`skillOverrides` takes exact names, and applies to personal-level skills** — which is
  where a locally installed suite lives. It blocks model invocation while leaving the skill
  in the architect's `/` menu, which is the direction wanted here.

The block is true only as long as it covers what is actually installed, and it quietly
stopped being true: it was written against one family, and this machine later grew sixty-five
more skills that between them supply a written plan, TDD, review checklists and the phase
scaffolding built on them. Nothing noticed, because the block is a list and the machine is
not.

```bash
python3 tools/check_workflow_block.py    # exit 1 lists every uncovered delivery workflow
```

That is a configuration drift check, not a test suite: it reads this machine's own skill
inventory, because this machine's inventory is the thing that drifts. It also fails if a
skill `AGENTS.md` deliberately leaves available — `systematic-debugging`,
`using-git-worktrees` — has been switched off by mistake.
