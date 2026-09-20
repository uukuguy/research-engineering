"""`researchlog init` — create the minimum durable state a research repo needs.

Bookkeeping, not research: it copies a skeleton, stamps versions, and then checks
whether the repository's own `.gitignore` would silently exclude run provenance.

That last check earns its place because the failure it catches is invisible. An
unanchored `runs/` pattern excludes `research/runs/**` at any depth, and Git cannot
re-include a file whose parent directory is excluded — so `manifest.json` never reaches
the remote, the loss shows up only on another machine, and by then the run identity is
gone.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from researchlog import jgit, repo
from researchlog.errors import (
    Finding,
    PreconditionMissing,
    RefusedByPolicy,
    Result,
    SEVERITY_INFO,
    SEVERITY_WARNING,
)

NAME = "init"
HELP = "create the research state skeleton in this repository"

SKELETON = (
    "ACTIVE.json",
    "CURRENT.md",
    "ARCHITECT.md",
    "BOUNDARIES.md",
    "ENVIRONMENT.md",
    "FINDINGS.md",
)


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=None, help="repository root (default: search upward)")
    parser.add_argument(
        "--submission-budget",
        type=int,
        default=None,
        help="number of official submissions available; reaching it becomes an error",
    )
    parser.add_argument("--merge", action="store_true", help="fill in missing files without overwriting")
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="create the unprefixed `research/` directory instead of `.research/` "
             "(only when an existing repo on the older layout must be preserved)",
    )


def run(args: argparse.Namespace) -> Result:
    root = (args.root or Path.cwd()).resolve()
    paths = repo.build(root, research_dir=("research" if args.legacy else None))
    existed = paths.active.exists()

    if existed and not args.merge:
        raise RefusedByPolicy(
            "RESEARCH_STATE_EXISTS",
            f"{paths.active} already exists",
            "pass --merge to fill in missing files, or pick a different --root",
        )

    source = repo.templates_dir()
    if not source.is_dir():
        raise PreconditionMissing(
            "TEMPLATES_ABSENT",
            f"the skeleton templates are missing from {source}",
            "copy the whole tools/ directory, templates included",
        )

    repo.initialize_dirs(paths)
    written, kept = _copy_skeleton(source, paths, merge=args.merge)
    _stamp_active(paths)
    # V1 Block 2 / T5: open the first session event so the cumulative
    # telemetry KPI has an anchor to count from. Append-only: a re-init
    # (`init` without --merge) refuses earlier; `--merge` skips the
    # existing line by leaving the file alone (idempotent on the
    # session log, just like on the canonical markdown files).
    if not existed or args.merge:
        # Import by absolute module path to avoid re-entering this
        # package's `__init__.py` (which already imports `init` and
        # would self-trigger). The runtime resolver see this as
        # `researchlog.commands.sessions` either way; the difference
        # is only that Pyright can statically resolve it without
        # treating the package as a self-reference.
        import importlib
        sessions_module = importlib.import_module("researchlog.commands.sessions")
        active = json.loads(paths.active.read_text(encoding="utf-8"))
        epoch = active.get("session_epoch") or sessions_module.mint_epoch()
        sessions_module.append_event(
            paths=paths,
            epoch=epoch,
            kind="started",
            block_id=active.get("block.id"),
        )
        if "session_epoch" not in active:
            active["session_epoch"] = epoch
            paths.active.write_text(
                json.dumps(active, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    result = Result(
        payload={
            "root": str(root),
            "research_dir": str(paths.research),
            "written": sorted(written),
            "kept": sorted(kept),
            "already_initialized": existed,
        }
    )
    if args.submission_budget is not None:
        _set_submission_budget(paths, args.submission_budget)
        result.payload["submission_budget"] = args.submission_budget

    for finding in _guard_gitignore(root):
        result.add(finding)
    if result.payload["already_initialized"] is False and _tree_is_dirty(root):
        result.add(
            Finding(
                "INITIAL_STATE_UNCOMMITTED",
                SEVERITY_INFO,
                f"{repo.RESEARCH_DIR}/",
                "the research state is not committed yet, so the working tree is dirty",
                "commit it, then set git.dirty_expected to false — until then reconcile "
                "reports ACTIVE_GIT_MISMATCH, which is accurate rather than a defect",
            )
        )
    return result


def _tree_is_dirty(root: Path) -> bool:
    return jgit.is_repository(root) and jgit.is_dirty(root)


def _copy_skeleton(source: Path, paths: repo.ResearchPaths, *, merge: bool) -> tuple[list[str], list[str]]:
    written: list[str] = []
    kept: list[str] = []
    for name in SKELETON:
        target = paths.markdown(name)
        if target.exists() and merge:
            kept.append(name)
            continue
        shutil.copyfile(source / name, target)
        written.append(name)
    return written, kept


def _stamp_active(paths: repo.ResearchPaths) -> None:
    data = json.loads(paths.active.read_text(encoding="utf-8"))
    data["updated_at"] = _now()
    data["git"] = _initial_git_state(paths)
    # V1 P2: backfill block.reproduction_iterations on ACTIVE instances that
    # pre-date the field. The template ships with the key set, but a repo that
    # ran `init` before P2 still has it missing; without this line the next
    # validate / reconcile against a P2-era schema would refuse the file.
    block = data.setdefault("block", {})
    block.setdefault("reproduction_iterations", 0)
    paths.active.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _initial_git_state(paths: repo.ResearchPaths) -> dict[str, object]:
    """Describe the tree as it actually is, so reconciliation does not cry wolf on day one.

    Straight after `init` the research directory is untracked, which makes the working
    tree dirty. Writing `dirty_expected: false` there would be a claim the repository
    contradicts the moment anyone looks, and `reconcile` would report a mismatch on a
    state this very command just created.
    """
    root = paths.root
    blank: dict[str, object] = {
        "branch": None,
        "base_commit": None,
        "checkpoint_commit": None,
        "dirty_expected": False,
        "expected_touched_files": [],
    }
    if not jgit.is_repository(root):
        return blank
    return {
        "branch": jgit.current_branch(root),
        "base_commit": jgit.head_commit(root),
        "checkpoint_commit": None,
        "dirty_expected": jgit.is_dirty(root),
        # Reflects whatever directory name `init` (or `--legacy`) actually
        # wrote, so reconcile sees the real path under either layout.
        "expected_touched_files": [f"{paths.research.name}/"],
    }


def _set_submission_budget(paths: repo.ResearchPaths, budget: int) -> None:
    from researchlog import schema

    text = paths.boundaries.read_text(encoding="utf-8")
    block = schema.require_block(text, "boundaries", source="BOUNDARIES.md")
    block["submission_budget"] = budget
    paths.boundaries.write_text(schema.replace_block(text, "boundaries", block), encoding="utf-8")


def _guard_gitignore(root: Path) -> list[Finding]:
    """Catch the .gitignore pattern that would swallow run provenance."""
    if not jgit.is_repository(root):
        return []
    probe = f"{repo.RESEARCH_DIR}/{repo.RUNS_DIR}/EXP-probe/manifest.json"
    pattern = jgit.check_ignore(root, probe)
    if pattern is None:
        return []
    return [
        Finding(
            "RUNS_DIR_IGNORED_BY_GITIGNORE",
            SEVERITY_WARNING,
            probe,
            f"run manifests would be excluded from Git by the pattern {pattern!r}",
            "anchor the pattern to the repository root (use '/runs/' rather than 'runs/'), "
            "since Git cannot re-include a file inside an excluded directory",
        )
    ]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
