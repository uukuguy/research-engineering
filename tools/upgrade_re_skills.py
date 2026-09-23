#!/usr/bin/env python3
"""Explicit installed-client skill migration; never alter research state or runtime.

Run only between research sessions. Defaults to a preview. The old lock and changed
files are retained under .re-install-history for recovery if the copy is interrupted.
This is a bounded local-development migration, not the future general RE installer.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess

from init_re_project import LOCK, check, digest, files_under


def upgrade(source: Path, target: Path, *, apply: bool = False) -> list[str]:
    source, target = source.resolve(), target.resolve()
    if source == target or not (target / ".git").exists():
        raise ValueError("Target must be a separate Git project")
    check(target)
    lock_bytes = (target / LOCK).read_bytes()
    old = json.loads(lock_bytes)
    spec = importlib.util.spec_from_file_location("skill_source", source / "tools/install_research_skills.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    clients = [c for c in ('.agents', '.claude')
               if any(name.startswith(c + '/skills/') for name in old['files'])]
    payload = {client + '/skills/' + name: data for client in clients for name, data in
               module.expected_tree(source / 'skills', client).items()}
    prior = {name for name in old["files"] if any(name.startswith(c + '/skills/') for c in clients)}
    if prior - payload.keys():
        raise ValueError("Skill removal needs a separate migration")
    for name in payload:
        dest = target / name
        if any(p.is_symlink() for p in [dest, *dest.parents] if p.is_relative_to(target)):
            raise ValueError(f"Symlink destination refused: {name}")
        if dest.exists() and name not in prior:
            raise ValueError(f"Unowned destination refused: {name}")
    owned = {'/'.join(Path(name).parts[:3]) for name in payload}
    for directory in owned:
        for path in files_under(target / directory):
            if path.relative_to(target).as_posix() not in payload:
                raise ValueError(f"Unexpected file in skill destination: {path}")
    changed = sorted(name for name, data in payload.items()
                     if old["files"].get(name) != digest(data))
    print("Skill migration: " + (", ".join(changed) if changed else "already current"))
    if not apply or not changed:
        return changed
    archive = target / ".re-install-history" / digest(lock_bytes)
    if archive.exists() or archive.parent.is_symlink():
        raise ValueError("Migration archive already exists or is symlinked; inspect before retry")
    # All expected refusals above occur before any writes. Keep original bytes so
    # interruption never requires guessing what the previous snapshot contained.
    archive.mkdir(parents=True)
    (archive / LOCK).write_bytes(lock_bytes)
    for name in changed:
        dest = target / name
        if dest.exists():
            backup = archive / name
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(dest.read_bytes())
    new = json.loads(lock_bytes)
    head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"], text=True))
    new.setdefault("skill_migrations", []).append({
        "previous_lock_sha256": digest(lock_bytes), "source_commit": head,
        "source_dirty": dirty, "changed_files": changed,
        "backup": archive.relative_to(target).as_posix(),
    })
    for name, data in payload.items():
        new["files"][name] = digest(data)
    new["owned_directories"] = sorted(set(new["owned_directories"]) | owned)
    for name in changed:
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload[name])
    # Write the lock last: a partial copy stays detectably inconsistent.
    (target / LOCK).write_text(json.dumps(new, indent=2) + "\n")
    check(target)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        upgrade(Path(__file__).resolve().parents[1], args.target.resolve(), apply=args.apply)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Skill migration refused: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
