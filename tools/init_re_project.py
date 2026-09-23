#!/usr/bin/env python3
"""Install a frozen local RE deployment, not research conclusions or state.

Existing different files are refused before writing. Re-running with a lock only
checks that snapshot; it never updates a live project from a moving checkout.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

LOCK = "re-install.json"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def files_under(directory: Path):
    for path in sorted(directory.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            yield path


def check(target: Path) -> int:
    lock = json.loads((target / LOCK).read_text())
    bad = []
    for name, expected in lock["files"].items():
        path = target / name
        if not path.is_file() or digest(path.read_bytes()) != expected:
            bad.append(name)
    for directory in lock["owned_directories"]:
        for path in files_under(target / directory):
            if path.relative_to(target).as_posix() not in lock["files"]:
                bad.append(path.relative_to(target).as_posix())
    if bad:
        raise ValueError("RE snapshot drift; refusing overwrite: " + ", ".join(sorted(set(bad))))
    print(f"RE snapshot OK: {len(lock['files'])} files; no state created or changed.")
    return 0


def install(source: Path, target: Path) -> int:
    if (target / LOCK).exists():
        return check(target)
    if source == target or not (target / ".git").exists():
        raise ValueError("Target must be a separate, initialized Git project")
    if (target / ".research").exists() or (target / "research/ACTIVE.json").exists():
        raise ValueError("Existing research state: reconcile and migrate explicitly, do not initialize")
    spec = importlib.util.spec_from_file_location("re_skill_installer", source / "tools/install_research_skills.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    payload = {}
    owned = ["tools/researchlog", "templates/research"]
    for directory in owned:
        if not (source / directory).is_dir():
            raise ValueError(f"Missing source: {directory}")
        for path in files_under(source / directory):
            rel = path.relative_to(source)
            if "tests" not in rel.parts:
                payload[rel.as_posix()] = path.read_bytes()
    for name in ("tools/re", "tools/init_re_project.py"):
        payload[name] = (source / name).read_bytes()
    for client in ('.agents', '.claude'):
        skills = module.expected_tree(source / "skills", client)
        for name, data in skills.items():
            payload[client + "/skills/" + name] = data
        owned += sorted({client + "/skills/" + name.split("/")[0] for name in skills})
    for path in files_under(source / "templates/project-install"):
        payload[path.relative_to(source / "templates/project-install").as_posix()] = path.read_bytes()
    # Local operator files are project-owned after install, not frozen runtime.
    policy_spec = importlib.util.spec_from_file_location('re_install_policy', source / 'templates/project-install/tools/re_workflow_policy.py')
    policy = importlib.util.module_from_spec(policy_spec)
    policy_spec.loader.exec_module(policy)
    payload['.claude/settings.json'] = (json.dumps(policy.claude_policy(target), indent=2) + '\n').encode()
    editable = {"Makefile", "AGENTS.md", "CLAUDE.md", "docs/RE_OPERATIONS.md", ".codex/config.toml", ".claude/settings.json"}
    for name, data in payload.items():
        dest = target / name
        if dest.exists() and dest.read_bytes() != data:
            if name in editable:
                raise ValueError(f"Existing {name} differs; merge explicitly, never overwrite")
            raise ValueError(f"Conflicting destination: {name}")
    for directory in owned:
        for path in files_under(target / directory):
            if path.relative_to(target).as_posix() not in payload:
                raise ValueError(f"Unexpected existing file: {path}")
    head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"], text=True))
    for name, data in payload.items():
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            dest.write_bytes(data)
    frozen = {name: digest(data) for name, data in sorted(payload.items()) if name not in editable}
    lock = {"schema_version": 1, "source_commit": head, "source_dirty": dirty,
            "files": frozen, "owned_directories": owned}
    (target / LOCK).write_text(json.dumps(lock, indent=2) + "\n")
    print("Installed local RE tools and same-source Codex/Claude Code skills. Research bootstrap has NOT run.")
    return check(target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=Path.cwd())
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        return check(args.target.resolve()) if args.check else install(args.source.resolve(), args.target.resolve())
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"RE initialization refused: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
