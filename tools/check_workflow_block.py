#!/usr/bin/env python3
"""Check that the project's workflow block still covers the delivery workflows on this machine.

`AGENTS.md` says the generic software-delivery workflow skills are disabled for this project
mechanically, and that their absence is the point: brainstorming, a written plan, TDD, a
review checklist. That claim is only true as long as the block covers whatever is installed.

It stopped being true without anyone noticing. The block was written against the superpowers
family; the machine later grew the `gsd-*` suite — sixty-five skills that between them supply
a written plan, TDD, review checklists and the phase scaffolding built on them — and none of
them was covered. A claim in a contract file drifted away from the configuration that was
supposed to make it true, which is the failure this repository keeps rediscovering.

Two mechanisms, and they are not interchangeable (this is the part that is easy to get wrong):

* `permissions.deny` takes an **exact** skill name. `Skill(gsd-*)` matches nothing; verified
  by invoking `gsd-plan-phase` under a settings file that denied exactly that pattern and
  watching it load.
* `skillOverrides` takes exact names too, and applies to **personal-level** skills, which is
  where the `gsd-*` suite lives. It disables model invocation while leaving the skill
  available to the architect, which is the wanted direction.

Exit 0 when every known delivery workflow is covered; exit 1 listing the ones that are not.
A keyword sweep for uncovered skills that *look* like delivery workflows is reported as a
warning — it is a prompt to look, not a verdict.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
PERSONAL_SKILLS = pathlib.Path.home() / ".claude" / "skills"

# Families that are delivery workflow by construction, rather than by reading a description.
DELIVERY_FAMILIES: tuple[str, ...] = ("gsd-",)

# Individually judged, and switched off for the same reason as the families above.
DELIVERY_SKILLS: frozenset[str] = frozenset(
    {
        "discuss",              # decisions gathered before a plan is written
        "review-plan",          # review of a plan, before execution
        "code-review-changes",  # produces a review checklist
        "test",                 # run the comprehensive suite
        "frontend-test",
    }
)

# The same judgement for plugin-namespaced skills, which need permissions.deny instead —
# `skillOverrides` does not reach plugin skills. Names are `plugin:skill`, and the plugin is
# the directory above the version: under the `omc` marketplace the plugin is
# `oh-my-claudecode`, so `Skill(omc:...)` would match nothing while looking correct.
PLUGIN_DELIVERY_FAMILIES: tuple[str, ...] = ("dev-phase-manager", "planning-with-files")
PLUGIN_DELIVERY_SKILLS: frozenset[str] = frozenset(
    f"oh-my-claudecode:{skill}"
    for skill in (
        "autopilot",             # idea to working code
        "plan", "ralplan",       # strategic planning, and consensus planning before execution
        "ralph",                 # loop until task completion
        "ultraqa",               # test, verify, fix, repeat
        "ultrawork",             # parallel execution engine
        "verify",                # verify before claiming completion
        "self-improve",          # autonomous code improvement
        "release",
        "deep-interview", "deep-dive",   # requirements before autonomous execution
        "project-session-manager",       # issues, PRs, features
    )
)

# Started by AGENTS.md as deliberately available, so they must NOT be blocked.
DELIBERATELY_AVAILABLE: frozenset[str] = frozenset({"systematic-debugging", "using-git-worktrees"})

PLUGIN_CACHE = pathlib.Path.home() / ".claude" / "plugins" / "cache"

DELIVERY_WORDS = re.compile(r"plan|brainstorm|test-driven|review checklist|roadmap|phase", re.I)


def blocked_skill_names(settings: dict) -> set[str]:
    """Every skill the two mechanisms cover, by exact name."""
    names = {name for name, value in (settings.get("skillOverrides") or {}).items() if value == "off"}
    for entry in (settings.get("permissions") or {}).get("deny") or []:
        match = re.fullmatch(r"Skill\(([^)]+)\)", entry.strip())
        if match and not match.group(1).endswith("*"):
            names.add(match.group(1))
    return names


def personal_skills() -> dict[str, str]:
    """{skill name: description} for the personal skills installed on this machine."""
    found: dict[str, str] = {}
    if not PERSONAL_SKILLS.is_dir():
        return found
    for path in sorted(PERSONAL_SKILLS.iterdir()):
        skill = path / "SKILL.md"
        if not path.is_dir() or not skill.is_file():
            continue
        text = skill.read_text(encoding="utf-8", errors="replace")[:2000]
        match = re.search(r"^description:\s*(.+)$", text, re.M)
        found[path.name] = (match.group(1) if match else "").strip()
    return found


def enabled_plugins() -> set[str]:
    """Plugin names the user has switched on. A cached plugin that is not enabled is not
    reachable, so treating the cache as the available set reports a block that is not
    needed — and would hide a real one behind it."""
    settings_file = pathlib.Path.home() / ".claude" / "settings.json"
    if not settings_file.is_file():
        return set()
    declared = json.loads(settings_file.read_text(encoding="utf-8")).get("enabledPlugins") or {}
    entries = declared.items() if isinstance(declared, dict) else ((e, True) for e in declared)
    return {name.split("@")[0] for name, on in entries if on}


def plugin_skills() -> dict[str, str]:
    """{plugin:skill: description} for the plugin skills reachable on this machine.

    The plugin name is the directory above the version; the marketplace directory above that
    is a different name, and reading the wrong one silently matches nothing.
    """
    found: dict[str, str] = {}
    if not PLUGIN_CACHE.is_dir():
        return found
    enabled = enabled_plugins()
    for skills_dir in PLUGIN_CACHE.glob("*/*/*/skills"):
        plugin = skills_dir.parts[-3]
        if plugin not in enabled:
            continue
        for skill in sorted(skills_dir.iterdir()):
            manifest = skill / "SKILL.md"
            if not skill.is_dir() or not manifest.is_file():
                continue
            text = manifest.read_text(encoding="utf-8", errors="replace")[:2000]
            match = re.search(r"^description:\s*(.+)$", text, re.M)
            found[f"{plugin}:{skill.name}"] = (match.group(1) if match else "").strip()
    return found


def main() -> int:
    if not SETTINGS.is_file():
        print(f"no project settings at {SETTINGS}; the block is not configured at all", file=sys.stderr)
        return 1

    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    covered = blocked_skill_names(settings)
    installed = {**personal_skills(), **plugin_skills()}

    expected = {
        name
        for name in installed
        if name.startswith(DELIVERY_FAMILIES)
        or name in DELIVERY_SKILLS
        or name.split(":")[0] in PLUGIN_DELIVERY_FAMILIES
        or name in PLUGIN_DELIVERY_SKILLS
    }
    missing = sorted(expected - covered)
    leaked = sorted(DELIBERATELY_AVAILABLE & covered)

    # Skills nobody classified, whose own description reads like a delivery workflow.
    suspicious = sorted(
        name
        for name, description in installed.items()
        if name not in covered
        and name.split(":")[-1] not in DELIBERATELY_AVAILABLE
        and DELIVERY_WORDS.search(description or "")
    )

    for name in missing:
        print(f"uncovered delivery workflow: {name}", file=sys.stderr)
    for name in leaked:
        print(f"blocked but AGENTS.md leaves it available: {name}", file=sys.stderr)
    for name in suspicious:
        print(f"warning: not blocked, and its description mentions a delivery workflow: {name}")

    if missing or leaked:
        print(
            "\nAdd the uncovered ones to skillOverrides in .claude/settings.json, or record why\n"
            "they are deliberately available. Fix the block, not this check.",
            file=sys.stderr,
        )
        return 1

    print(
        f"workflow block covers {len(expected)} delivery-workflow skills "
        f"({len(covered)} names blocked in total); {len(suspicious)} unclassified warning(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
