"""Project-session exclusions; never modify a user's global skill configuration."""
from pathlib import Path
import json
import re

ALLOW = {"systematic-debugging", "using-git-worktrees"}
BLOCK = {
    "brainstorming", "writing-plans", "executing-plans", "test-driven-development",
    "requesting-code-review", "receiving-code-review", "verification-before-completion",
    "subagent-driven-development", "dispatching-parallel-agents",
    "finishing-a-development-branch", "using-superpowers", "planning-with-files",
    "project-state", "ai-project-manager",
}


def blocked(name: str, path: Path) -> bool:
    short = name.split(":")[-1]
    if short in ALLOW:
        return False
    return (short in BLOCK or short.startswith("gsd-") or
            name.startswith(("superpowers:", "gsd:")) or
            "superpowers" in path.parts)


def rules(root: Path, home: Path | None = None) -> list[dict]:
    home = home or Path.home()
    # Seed names even when discovery is unavailable, and expand GSD/plugin exact
    # names from this machine. No wildcard matching is assumed by the client.
    names = set(BLOCK) | {"superpowers:" + name for name in BLOCK if name not in ALLOW}
    roots = [home / ".agents/skills", home / ".codex/skills",
             root / ".agents/skills", root / ".codex/skills",
             home / ".codex/plugins/cache"]
    for directory in roots:
        if not directory.is_dir():
            continue
        for path in directory.rglob("SKILL.md"):
            text = path.read_text(encoding="utf-8", errors="replace")
            match = re.search(r"^name:\s*([^\n]+)", text, re.M)
            name = match.group(1).strip().strip('\"\'') if match else path.parent.name
            for candidate in {name, path.parent.name}:
                if blocked(candidate, path):
                    names.add(candidate)
    return [{"name": name, "enabled": False} for name in sorted(names)]


def config_override(root: Path) -> str:
    return "skills.config=[" + ",".join(
        '{name=' + json.dumps(rule["name"]) + ',enabled=false}' for rule in rules(root)
    ) + "]"


def claude_policy(root: Path, home: Path | None = None) -> dict:
    """Exact project-local denies; no auth/model/permission-mode settings."""
    home = home or Path.home()
    names = set(BLOCK) | {'superpowers:' + name for name in BLOCK}
    for directory in (home / '.claude/skills', home / '.agents/skills',
                      root / '.claude/skills', home / '.claude/plugins/cache'):
        if not directory.is_dir():
            continue
        for path in directory.rglob('SKILL.md'):
            match = re.search(r'^name:\s*([^\n]+)', path.read_text(errors='replace'), re.M)
            name = match.group(1).strip().strip('\"\'') if match else path.parent.name
            candidates = {name, path.parent.name}
            if 'cache' in path.parts and 'skills' in path.parts:
                index = len(path.parts) - 1 - list(reversed(path.parts)).index('skills')
                if index >= 2:
                    candidates.add(path.parts[index - 2] + ':' + path.parent.name)
            names.update(candidate for candidate in candidates if blocked(candidate, path))
    names = sorted(name for name in names if name.split(':')[-1] not in ALLOW)
    return {'permissions': {'deny': [f'Skill({name})' for name in names]},
            'skillOverrides': {name: 'off' for name in names if ':' not in name}}
