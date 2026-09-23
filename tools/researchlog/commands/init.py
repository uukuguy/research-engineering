"""`researchlog init` — create the minimum durable state a research repo needs.

Bookkeeping, not research: it copies a skeleton, stamps versions, and then checks
whether the repository's own `.gitignore` would silently exclude run provenance.

That last check earns its place because the failure it catches is invisible. An
unanchored `runs/` pattern excludes `research/runs/**` at any depth, and Git cannot
re-include a file whose an excluded directory — so `manifest.json` never reaches
the remote, the loss shows up only on another machine, and by then the run identity is
gone.

Plus a second concern: the operator (Architect, AI session, or downstream CI)
needs surface affordances — a `Makefile` plus `docs/OPERATIONS.md` — to read
state, observe progress, and spawn sessions without memorising long CLI
incantations. Those helpers live in `templates/workspace-helpers/` next to the
canonical-state skeleton and are written once on `init`, against the same
idempotency rules as the rest of the skeleton (`--merge` preserves existing files).
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from researchlog import ioutil, jgit, repo, schema
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

# Operator-affordance files written alongside the canonical state. Each entry
# is a (source-relative-name, target-relative-name) pair. Source paths are
# rooted at `templates/workspace-helpers/`; target paths are rooted at the
# cwd. Placeholders of the form `__FOO__` are substituted with the actual
# protocol root path so the cwd Makefile can find its toolchain regardless
# of where it was installed.
OPERATOR_HELPERS: tuple[tuple[str, str], ...] = (
    ("Makefile", "Makefile"),
    ("docs/OPERATIONS.md", "docs/OPERATIONS.md"),
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
    # A default re-init must keep the layout already used by this repository.
    # Creating .research beside a legacy research would silently hide its history.
    if not args.legacy and not paths.active.exists():
        legacy = repo.build(root, research_dir="research")
        if legacy.active.exists():
            paths = legacy
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

    if existed:
        document = ioutil.load_json(paths.active)
        schema.require_writable("active", paths.active, document)
    if args.submission_budget is not None and paths.boundaries.exists():
        block = schema.require_block(
            paths.boundaries.read_text(encoding="utf-8"), "boundaries", source="BOUNDARIES.md"
        )
        schema.require_writable("boundaries", paths.boundaries, block)

    repo.initialize_dirs(paths)
    written, kept = _copy_skeleton(source, paths, merge=args.merge)
    operator_written, operator_kept = _copy_operator_helpers(root, merge=args.merge)
    written = sorted(written + operator_written)
    kept = sorted(kept + operator_kept)
    if not existed:
        _stamp_active(paths)
    # V1 Block 2 / T5: open the first session event so the cumulative
    # telemetry KPI has an anchor to count from. Append-only: a re-init
    # (`init` without --merge) refuses earlier; `--merge` skips the
    # existing line by leaving the file alone (idempotent on the
    # session log, just like on the canonical markdown files).
    if not paths.sessions.exists():
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
            block_id=(active.get("block") or {}).get("id"),
        )
        if not active.get("session_epoch"):
            active["session_epoch"] = epoch
            ioutil.write_json_atomic(paths.active, active, validator=schema.load_validator("active"))

    result = Result(
        payload={
            "root": str(root),
            "research_dir": str(paths.research),
            "written": sorted(written),
            "kept": sorted(kept),
            "already_initialized": existed,
            "protocol_root": str(repo.protocol_root()),
        }
    )
    if args.submission_budget is not None:
        _set_submission_budget(paths, args.submission_budget)
        result.payload["submission_budget"] = args.submission_budget

    for finding in _guard_gitignore(root, research_dir=paths.research.name):
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


def _copy_operator_helpers(root: Path, *, merge: bool) -> tuple[list[str], list[str]]:
    """Write the cwd-local `Makefile` and `docs/OPERATIONS.md` if absent.

    These are non-canonical-state operator affordances: writing them once
    on `init` keeps the cwd usable without the Architect memorising long
    CLI invocations. `--merge` keeps an existing file unchanged, the same
    idempotency rule the canonical state follows.

    The `__RE_PROTOCOL_ROOT__` placeholder in `Makefile` is substituted
    with the protocol's actual install root, so cwd Makefile entries
    reach the toolchain regardless of where it lives on disk.
    """
    source_root = repo.workspace_helpers_dir()
    if not source_root.is_dir():
        return [], []
    protocol = repo.protocol_root()
    written: list[str] = []
    kept: list[str] = []
    for src_rel, tgt_rel in OPERATOR_HELPERS:
        target = root / tgt_rel
        if target.exists():
            if merge:
                kept.append(tgt_rel)
                continue
            # Avoid clobbering unless --merge (the user almost always wants
            # to keep their local Makefile edits on re-init).
            kept.append(tgt_rel)
            continue
        body = (source_root / src_rel).read_text(encoding="utf-8")
        body = body.replace("__RE_PROTOCOL_ROOT__", str(protocol))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        written.append(tgt_rel)
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
    ioutil.write_json_atomic(paths.active, data, validator=schema.load_validator("active"))


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


def _guard_gitignore(root: Path, *, research_dir: str = repo.RESEARCH_DIR) -> list[Finding]:
    """Catch the .gitignore pattern that would swallow run provenance."""
    if not jgit.is_repository(root):
        return []
    probe = f"{research_dir}/{repo.RUNS_DIR}/EXP-probe/manifest.json"
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
