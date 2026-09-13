"""`researchlog snapshot` — a fingerprint of Git, the environment, and the state planes.

**By default this command writes nothing.** That is not an oversight. A status query that
persists a file dirties the working tree; a dirty tree is what `RECOVERY_RECONCILIATION`
exists to resolve; so a query that writes makes the next resume trip over the query's own
footprints. Reading is free, so reading is the default, and `--write` is the one explicit
way to persist — into `research/.derived/`, which is scratch space by construction.

The reconcile section is a *summary*: counts and finding codes, not the full findings. A
snapshot is meant to be cheap to take and cheap to read, and anything more belongs in
`reconcile` itself.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from researchlog import ioutil, jgit, repo, schema, state
from researchlog.commands import reconcile
from researchlog.errors import (
    Finding,
    RefusedByPolicy,
    Result,
    SEVERITY_WARNING,
)

NAME = "snapshot"
HELP = "print a compact Git/environment/state fingerprint; writes nothing by default"


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--write", metavar="PATH", default=None, help="persist under research/.derived/"
    )


def run(args: argparse.Namespace) -> Result:
    paths = repo.require(args.root)
    snapshot = _build(paths)
    result = Result(payload=snapshot, human=_human(snapshot))
    if args.write is None:
        return result

    target = _target(paths, args.write)
    ioutil.write_json_atomic(target, snapshot)
    result.payload["written"] = str(target)
    for finding in _guard_ignored(paths, target):
        result.add(finding)
    return result


def _build(paths: repo.ResearchPaths) -> dict[str, Any]:
    """Everything here is read-only; a snapshot that wrote would be its own worst case."""
    active_status, block_id = _active_pointers(paths)
    return {
        "generated_at": _now(),
        "root": str(paths.root),
        "git": _git(paths),
        "environment": _environment(paths),
        "active": {"status": active_status, "block_id": block_id},
        "reconcile": _reconcile(paths),
    }


def _active_pointers(paths: repo.ResearchPaths) -> tuple[Any, Any]:
    try:
        active = state.load_active(paths)
    except Exception:  # noqa: BLE001 - a broken ACTIVE is reported by the reconcile summary
        return None, None
    return active.get("status"), active.get("block.id")


def _git(paths: repo.ResearchPaths) -> dict[str, Any]:
    if not jgit.is_repository(paths.root):
        return {"repository": False}
    return {
        "repository": True,
        "branch": jgit.current_branch(paths.root),
        "commit": jgit.head_commit(paths.root),
        "dirty": jgit.is_dirty(paths.root),
        "touched": list(jgit.status_porcelain(paths.root)),
    }


def _environment(paths: repo.ResearchPaths) -> dict[str, Any]:
    if not paths.environment.is_file():
        return {"present": False}
    try:
        block = (
            schema.find_block(paths.environment.read_text(encoding="utf-8"), "environment") or {}
        )
    except Exception:  # noqa: BLE001 - a malformed block is reported by reconcile/validate
        return {"present": True, "readable": False}
    comparability = block.get("comparability") or {}
    return {
        "present": True,
        "readable": True,
        "id": block.get("environment_id"),
        "fingerprint": comparability.get("fingerprint"),
        "status": comparability.get("status"),
        "last_material_change": comparability.get("last_material_change"),
    }


def _reconcile(paths: repo.ResearchPaths) -> dict[str, Any]:
    """A one-level summary of the consistency detectors, not the findings themselves."""
    outcome = reconcile.run(
        argparse.Namespace(root=paths.root, stale_after=reconcile.STALE_RUNNING_MINUTES)
    )
    severities = Counter(finding.severity for finding in outcome.findings)
    return {
        "clean": not outcome.findings,
        "exit_code": outcome.exit_code,
        "finding_count": len(outcome.findings),
        "by_severity": dict(sorted(severities.items())),
        "codes": sorted({finding.code for finding in outcome.findings}),
        "evidence_records": outcome.payload.get("evidence_records"),
        "manifests": outcome.payload.get("manifests"),
    }


def _target(paths: repo.ResearchPaths, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        target = candidate.resolve()
    elif candidate.parent == Path("."):
        target = (paths.derived / candidate).resolve()
    else:
        target = (paths.root / candidate).resolve()
    if not target.is_relative_to(paths.derived.resolve()):
        raise RefusedByPolicy(
            "SNAPSHOT_PATH_OUTSIDE_DERIVED",
            f"{raw!r} resolves to {target}, outside {paths.derived}",
            "a snapshot is derived state; writing it anywhere else would put a second "
            "source of truth next to the canonical files",
        )
    return target


def _guard_ignored(paths: repo.ResearchPaths, target: Path) -> list[Finding]:
    if not jgit.is_repository(paths.root):
        return []
    relative = target.relative_to(paths.root.resolve()).as_posix()
    if jgit.check_ignore(paths.root, relative) is not None:
        return []
    return [
        Finding(
            "SNAPSHOT_NOT_IGNORED",
            SEVERITY_WARNING,
            relative,
            "the snapshot path is not excluded by .gitignore, so writing it dirties the tree",
            "add 'research/.derived/' to .gitignore; a status query must not create dirty state",
        )
    ]


def _human(snapshot: dict[str, Any]) -> str:
    git = snapshot["git"]
    reconcile_summary = snapshot["reconcile"]
    lines = [
        f"root       {snapshot['root']}",
        f"git        {git.get('branch')}@{_short(git.get('commit'))} "
        f"{'dirty' if git.get('dirty') else 'clean'}",
        f"environment {snapshot['environment'].get('fingerprint') or '-'} "
        f"({snapshot['environment'].get('status') or '-'})",
        f"active     {snapshot['active'].get('status') or '-'} / "
        f"{snapshot['active'].get('block_id') or '-'}",
        f"reconcile  {'clean' if reconcile_summary['clean'] else ', '.join(reconcile_summary['codes'])}",
    ]
    return "\n".join(lines)


def _short(commit: Any) -> str:
    return str(commit)[:12] if commit else "-"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
