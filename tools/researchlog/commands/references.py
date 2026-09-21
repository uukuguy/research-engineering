"""`researchlog references` — register and inspect external read-mostly research targets.

The RE workspace cwd records the projects it studies in `.research/references.json`.
Each entry points at a sibling project the cwd reads from, and carries the
constraints reconcile enforces: presence of path, expected sha256 anchors
(when the project publishes them), and reading-mode flags.

The verb is the contract an Architect or a session uses to set up that
machine-readable record before any evidence is recorded. A workspace that
records an EV whose `artifacts[]` references an unregistered path surfaces
a `REFERENCE_UNREGISTERED` finding on the next reconcile.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from researchlog import ioutil, repo
from researchlog.errors import (
    Finding,
    PreconditionMissing,
    RefusedByPolicy,
    Result,
    SEVERITY_INFO,
    SEVERITY_WARNING,
)

NAME = "references"
HELP = "register, list, or check external research targets in .research/references.json"

REF_FILENAME = "references.json"
SCHEMA_VERSION = "1.0"
VALID_PURPOSES = frozenset(
    {
        "primary_read_only_target",
        "secondary_evidence_source",
        "local_baseline",
    }
)
DEFAULT_PURPOSE = "secondary_evidence_source"


def _ref_path(paths: repo.ResearchPaths) -> Path:
    """The canonical location of references.json inside the state root.

    Honors the same `.research/` vs `research/` switch as the rest of the
    tool, so a workspace on the dotted layout and a legacy workspace coexist
    without a hard-coded dirname.
    """
    return paths.research / REF_FILENAME


def _read_refs(paths: repo.ResearchPaths) -> dict[str, Any]:
    """Return the parsed references document, or a blank one when missing."""
    target = _ref_path(paths)
    if not target.exists():
        return {"schema_version": SCHEMA_VERSION, "external_refs": []}
    return json.loads(target.read_text(encoding="utf-8"))


def _write_refs(paths: repo.ResearchPaths, doc: dict[str, Any]) -> None:
    target = _ref_path(paths)
    ioutil.write_json_atomic(
        target,
        doc,
        validator=_refs_validator(),
    )


def _refs_validator():
    from researchlog import schema

    return schema.load_validator("references")


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="workspace root (default: search upward from cwd like every other verb)",
    )
    sub = parser.add_subparsers(dest="sub", required=True)

    add = sub.add_parser(
        "add",
        help="add or replace a registered external research target",
    )
    add.add_argument(
        "id_positional",
        nargs="?",
        default=None,
        help="stable id used to reference this target (positional; equivalent to --id)",
    )
    add.add_argument(
        "path_positional",
        nargs="?",
        default=None,
        type=Path,
        help="absolute path to the target (positional; equivalent to --path)",
    )
    add.add_argument("--id", dest="id", default=None, help="stable id used to reference this target")
    add.add_argument("--path", dest="path", default=None, type=Path, help="absolute path to the target")
    add.add_argument(
        "--type",
        default="experimental_project",
        choices=["experimental_project", "experimental_project_data", "local_baseline", "other"],
        help="category of the target (default: experimental_project)",
    )
    add.add_argument(
        "--purpose",
        default=DEFAULT_PURPOSE,
        choices=sorted(VALID_PURPOSES),
        help="how this target is used (default: secondary_evidence_source)",
    )
    add.add_argument(
        "--read-only",
        dest="read_only",
        action="store_true",
        default=True,
        help="the workspace does not write to this target (default)",
    )
    add.add_argument(
        "--writable",
        dest="writable",
        action="store_true",
        default=False,
        help="the workspace may write to this target (rare; registration must explicitly allow it)",
    )
    add.add_argument(
        "--doc-anchor",
        action="append",
        metavar="REL-PATH",
        default=[],
        help="repeatable relative path inside the target; surfaces as a discovery hint",
    )
    add.add_argument(
        "--size-gb",
        type=float,
        default=None,
        help="approximate size in GB; recorded as `size_gb` for the human reader",
    )
    add.add_argument(
        "--invalidated-if",
        action="append",
        metavar="PREDICATE",
        default=[],
        help="repeatable predicate string; checks recorded against EV `invalidated_if`",
    )

    sub.add_parser("list", help="show every registered target as JSON")

    check = sub.add_parser(
        "check",
        help="verify every registered target is reachable and report findings",
    )
    check.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero if any finding is reported (default: report only)",
    )

    sub.add_parser(
        "sync",
        help="recompute and pin git/sha256 fingerprints for every registered target",
    )


def _ref_id_already_exists(doc: dict[str, Any], ref_id: str) -> bool:
    return any(r.get("id") == ref_id for r in doc.get("external_refs", []))


def run_add(args: argparse.Namespace, paths: repo.ResearchPaths) -> Result:
    # The operator may pass either `id / path` as `--id X --path Y` (explicit)
    # or positionally as `references add <id> <path>` (compact). Merge both
    # before any validation so the two forms behave identically.
    args.id = args.id or args.id_positional
    args.path = args.path or args.path_positional
    if not args.id:
        raise PreconditionMissing(
            "REFERENCE_ID_MISSING",
            "an id is required (positional first arg or --id)",
            "pass `references add <id> <path>` or `references add --id X --path Y`",
        )
    if not args.path:
        raise PreconditionMissing(
            "REFERENCE_PATH_MISSING_ON_ARGPARSE",
            "a path is required (positional second arg or --path)",
            "pass `references add <id> <path>` or `references add --id X --path Y`",
        )

    if args.purpose not in VALID_PURPOSES:
        raise RefusedByPolicy(
            "INVALID_PURPOSE",
            f"unknown purpose {args.purpose!r}; valid: {sorted(VALID_PURPOSES)}",
            "pick one of the documented purposes or extend the enum",
        )

    target = Path(args.path).expanduser().resolve()
    if not target.exists():
        raise PreconditionMissing(
            "REFERENCE_PATH_MISSING",
            f"{target} does not exist",
            "pass a path that exists on disk; the workspace never copies data",
        )

    doc = _read_refs(paths)
    if _ref_id_already_exists(doc, args.id):
        # Replace in place, preserving insertion order.
        doc["external_refs"] = [
            r for r in doc["external_refs"] if r.get("id") != args.id
        ]

    fingerprint: dict[str, Any] = {}
    if (target / ".git").is_dir():
        try:
            from researchlog import jgit

            fingerprint["git"] = {
                "branch": jgit.current_branch(target),
                "head_commit": jgit.head_commit(target),
            }
        except Exception:
            fingerprint["git"] = {"branch": None, "head_commit": None}

    read_only = not bool(args.writable)

    entry: dict[str, Any] = {
        "id": args.id,
        "type": args.type,
        "path": str(target),
        "purpose": args.purpose,
        "read_only": read_only,
        "doc_anchors": list(args.doc_anchor),
    }
    if args.size_gb is not None:
        entry["size_gb"] = float(args.size_gb)
    if args.invalidated_if:
        entry["invalidated_if"] = list(args.invalidated_if)
    if fingerprint:
        entry["fingerprint"] = fingerprint

    doc.setdefault("schema_version", SCHEMA_VERSION)
    doc.setdefault("external_refs", [])
    doc["external_refs"].append(entry)
    _write_refs(paths, doc)

    result = Result(
        payload={
            "id": args.id,
            "path": str(target),
            "purpose": args.purpose,
            "read_only": read_only,
            "fingerprint": fingerprint,
        }
    )
    result.add(
        Finding(
            "REFERENCE_REGISTERED",
            SEVERITY_INFO,
            args.id,
            f"registered {args.id} -> {target} (purpose={args.purpose}, read_only={bool(args.read_only)})",
            "run `researchlog references list` to inspect, or `references sync` to refresh fingerprints",
        )
    )
    return result


def run_list(_args: argparse.Namespace, paths: repo.ResearchPaths) -> Result:
    doc = _read_refs(paths)
    return Result(payload=doc)


def run_check(args: argparse.Namespace, paths: repo.ResearchPaths) -> Result:
    doc = _read_refs(paths)
    refs = doc.get("external_refs", [])
    if not refs:
        return Result(payload={"checked": 0, "findings": 0})

    result = Result(payload={"checked": len(refs), "findings": 0})
    for ref in refs:
        path = Path(ref.get("path", ""))
        if not path.exists():
            result.add(
                Finding(
                    "REFERENCE_PATH_GONE",
                    SEVERITY_WARNING,
                    ref.get("id", "?"),
                    f"registered path no longer exists: {path}",
                    "re-register with `references add`, or drop the entry",
                )
            )
            continue
        anchor_files = [path / rel for rel in ref.get("doc_anchors", []) if rel]
        for anchor in anchor_files:
            if anchor.exists():
                continue
            result.add(
                Finding(
                    "REFERENCE_ANCHOR_MISSING",
                    SEVERITY_WARNING,
                    ref.get("id", "?"),
                    f"doc_anchor not at expected path: {anchor}",
                    "fix the path or drop the anchor",
                )
            )

    findings_count = sum(1 for f in result.findings)
    result.payload["findings"] = findings_count
    if args.strict and findings_count:
        return Result(
            payload=result.payload,
            findings=result.findings,
            exit_code=4,
        )
    return result


def run_sync(_args: argparse.Namespace, paths: repo.ResearchPaths) -> Result:
    doc = _read_refs(paths)
    refs = doc.get("external_refs", [])
    if not refs:
        return Result(payload={"updated": 0})

    updated = 0
    for ref in refs:
        target = Path(ref.get("path", ""))
        if not target.exists() or not (target / ".git").is_dir():
            continue
        try:
            from researchlog import jgit

            ref.setdefault("fingerprint", {})["git"] = {
                "branch": jgit.current_branch(target),
                "head_commit": jgit.head_commit(target),
            }
            updated += 1
        except Exception:
            continue

    _write_refs(paths, doc)
    return Result(payload={"updated": updated})


def run(args: argparse.Namespace, paths: repo.ResearchPaths | None = None) -> Result:
    if paths is None:
        if args.root is not None:
            target = Path(args.root).expanduser().resolve()
            paths = repo.build(target)
        else:
            paths = repo.require()
    if args.sub == "add":
        return run_add(args, paths)
    if args.sub == "list":
        return run_list(args, paths)
    if args.sub == "check":
        return run_check(args, paths)
    if args.sub == "sync":
        return run_sync(args, paths)
    raise RefusedByPolicy(
        "UNKNOWN_SUBCOMMAND",
        f"unknown subcommand {args.sub!r}",
        "valid subcommands: add, list, check, sync",
    )
