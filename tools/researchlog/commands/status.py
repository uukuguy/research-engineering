"""`researchlog status` — persist a milestone cache the next session can read quickly.

V1 Block 2 / T3. The output is **derived state**: a plain markdown snapshot with a
two-line comment header that names what it is and how stale it is allowed to be.
`reconcile` reads `STATUS.md`, parses the `last_evidence_modified:` header line, and
flags `STATUS_STALE` when the ledger has moved past that anchor.

The header line `<!-- DERIVED SNAPSHOT — NOT SOURCE OF TRUTH -->` is the contract: a
reader who only sees this file must not mistake it for canonical state. The second
header line `<!-- last_evidence_modified: <epoch> -->` is the anchor `reconcile`
parses.

By default this command writes nothing, for the same reason `snapshot` does not:
a status query that persists dirtied the working tree under V0, and a dirty tree is
what `RECOVERY_REQUIRECILIATION` exists to resolve.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from researchlog import jgit, repo
from researchlog.commands import snapshot
from researchlog.errors import (
    Finding,
    RefusedByPolicy,
    Result,
    SEVERITY_WARNING,
)

NAME = "status"
HELP = "write a milestone cache to STATUS.md; writes nothing by default"

# Anchor parsed by `reconcile._stale_status`. Anchored on a known prefix so a
# prose line that happens to mention `last_evidence_modified:` cannot fool the
# detector into a false positive. Epoch seconds, not ISO: regex-stable, no
# timezone ambiguity, easy to compare to file mtime.
LAST_MODIFIED_LINE = re.compile(
    r"<!--\s*last_evidence_modified:\s*(\d+)\s*-->"
)

DEFAULT_PATH = "STATUS.md"


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--write",
        metavar="PATH",
        default=None,
        help="persist the cache (default: STATUS.md in the repository root)",
    )


def run(args: argparse.Namespace) -> Result:
    paths = repo.require(args.root)
    snapshot_data = snapshot._build(paths)
    ledger_mtime = _ledger_mtime(paths)
    body = _render(snapshot_data, ledger_mtime)

    result = Result(
        payload={
            "generated_at": snapshot_data["generated_at"],
            "last_evidence_modified": ledger_mtime,
            "wrote": None,
        },
        human=body,
    )

    if args.write is None:
        return result

    target = _target(paths, args.write)
    target.write_text(body, encoding="utf-8")
    result.payload["wrote"] = str(target)
    for finding in _guard_ignored(paths, target):
        result.add(finding)
    return result


def _render(snapshot_data: dict[str, Any], ledger_mtime: int | None) -> str:
    """Markdown with a two-line comment header `reconcile` parses.

    The header is a single leading block; below it a small key-value table
    summarises git / environment / active / reconcile. The exact same data
    shapes as `snapshot` are used — `status` is the milestone cache form,
    `snapshot` is the on-demand read; same content, different purpose.
    """
    git = snapshot_data["git"]
    env = snapshot_data["environment"]
    active = snapshot_data["active"]
    reconcile_summary = snapshot_data["reconcile"]
    return "\n".join(
        [
            "<!-- DERIVED SNAPSHOT — NOT SOURCE OF TRUTH -->",
            f"<!-- last_evidence_modified: {ledger_mtime if ledger_mtime is not None else 0} -->",
            "",
            "# Status",
            "",
            f"- generated_at: `{snapshot_data['generated_at']}`",
            f"- git: `{git.get('branch') or '-'}@{_short(git.get('commit'))}` "
            f"({'dirty' if git.get('dirty') else 'clean'})",
            f"- environment: `{env.get('fingerprint') or '-'}` "
            f"({env.get('status') or '-'})",
            f"- active: `{active.get('status') or '-'}` / "
            f"`{active.get('block_id') or '-'}`",
            f"- reconcile: "
            f"{'clean' if reconcile_summary['clean'] else ', '.join(reconcile_summary['codes'])} "
            f"({reconcile_summary['finding_count']} finding(s))",
            "",
        ]
    )


def _target(paths: repo.ResearchPaths, raw: str) -> Path:
    """Resolve a write path relative to the repo root, refusing `..` escapes.

    `STATUS.md` lives at the root by convention. Other paths are allowed so
    callers can stash the cache under `research/.derived/` or wherever their
    pipeline expects, but a `..` component is refused outright.
    """
    candidate = Path(raw)
    if candidate.is_absolute():
        target = candidate.resolve()
    else:
        target = (paths.root / candidate).resolve()
    if not target.is_relative_to(paths.root.resolve()):
        raise RefusedByPolicy(
            "STATUS_PATH_OUTSIDE_ROOT",
            f"{raw!r} resolves to {target}, outside {paths.root}",
            "milestone caches belong at or under the repo root; pass a relative "
            "path, or move the cache into research/.derived/ if that is the intent",
        )
    return target


def _guard_ignored(paths: repo.ResearchPaths, target: Path) -> list[Finding]:
    """A STATUS.md at the root dirties the tree unless it is gitignored.

    Mirrors `snapshot`'s SNAPSHOT_NOT_IGNORED pattern: the warning names the
    file and the fix, but does not refuse the write — the caller asked for it.
    """
    if not jgit.is_repository(paths.root):
        return []
    relative = target.relative_to(paths.root.resolve()).as_posix()
    if jgit.check_ignore(paths.root, relative) is not None:
        return []
    return [
        Finding(
            "STATUS_NOT_IGNORED",
            SEVERITY_WARNING,
            relative,
            "the status path is not excluded by .gitignore, so writing it dirties the tree",
            f"add '{relative}' (or its parent directory) to .gitignore; a status "
            "cache is derived state and must not be a source of truth on disk",
        )
    ]


def _ledger_mtime(paths: repo.ResearchPaths) -> int | None:
    """The newest mtime across ledger entries, as an epoch integer.

    `None` means the ledger is empty (no entries to be stale against); the
    cache header then writes `last_evidence_modified: 0`, which `reconcile`
    compares as "any real ledger move is later than this".
    """
    ledger_dir = paths.ledger
    if not ledger_dir.is_dir():
        return None
    latest: int | None = None
    for entry in ledger_dir.iterdir():
        if entry.is_file():
            mtime = int(entry.stat().st_mtime)
            if latest is None or mtime > latest:
                latest = mtime
    return latest


def _short(commit: Any) -> str:
    return str(commit)[:12] if commit else "-"