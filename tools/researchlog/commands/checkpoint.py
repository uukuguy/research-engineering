"""`researchlog checkpoint` — a recoverable Git commit of the research state.

This is the command most able to destroy work, so it is the one with the narrowest verbs:
`add`, `commit`, `tag`, `rev-parse`. It never pushes, never resets, never rewrites
history, and never `git add -A`. A checkpoint that could also throw away work would be a
command an agent should not be trusted to run unattended, and most of the value here comes
from it being safe to run unattended.

Three guards earn their place:

* **Protected paths.** Run directories hold logs and artifacts that are large, churn
  constantly, and are reproducible; committing them bloats the repository and makes every
  subsequent diff unreadable. `research/.checkpointignore` overrides the built-in list.
* **A size ceiling.** A single file above 20 MiB is refused with the instruction to
  reference it as an artifact instead. A manifest pointing at a file is durable; a
  hundred megabytes of binary in Git history is permanent.
* **Provenance trailers.** Every commit states the block, the hypotheses, the evidence and
  the ACTIVE status it belongs to, so a commit can be traced to a belief without reading
  the diff.
"""

from __future__ import annotations

import argparse
import fnmatch
from datetime import datetime, timezone
from pathlib import Path

from researchlog import ioutil, jgit, repo, schema, state
from researchlog.errors import (
    Finding,
    PreconditionMissing,
    RefusedByPolicy,
    Result,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    StateInvalid,
)
from researchlog.model import Record

NAME = "checkpoint"
HELP = "create a recoverable Git checkpoint of the research state"

IGNORE_FILE = ".checkpointignore"
DEFAULT_PROTECTED: tuple[str, ...] = (
    "runs/",
    "*.log",
    "data/",
    "*.tmp",
    ".derived/",
    "*.pt",
    "*.ckpt",
)
MAX_FILE_BYTES = 20 * 1024 * 1024
RESEARCH_PREFIX = "research/"


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--message", default=None)
    parser.add_argument("--paths", action="append", default=[], metavar="PATH")
    parser.add_argument(
        "--all-expected", action="store_true", help="also stage every modified file"
    )
    parser.add_argument("--tag", default=None)
    # V1 Block 3 / S2: `--baseline-tag` is an annotated tag whose message can carry a
    # `--gh-status <url>` link. Promotion-bound baselines (see docs/verification/gate-3.md)
    # use this so a reader can trace the baseline back to its Gate-3 verifier output.
    parser.add_argument(
        "--baseline-tag",
        default=None,
        metavar="NAME",
        help="annotated tag for a promotion-bound baseline; tag message can carry --gh-status URL",
    )
    parser.add_argument(
        "--gh-status",
        default=None,
        metavar="URL",
        help="optional Gate-3 run URL to embed in the --baseline-tag annotation; never blocks",
    )
    parser.add_argument("--dry-run", action="store_true", help="report what would be committed")
    parser.add_argument("--include-untracked", action="store_true")
    parser.add_argument("--require-change", action="store_true", help="fail when nothing changed")


def run(args: argparse.Namespace) -> Result:
    paths = repo.require(args.root)
    if not jgit.is_repository(paths.root):
        raise PreconditionMissing(
            "NOT_A_GIT_REPOSITORY",
            f"{paths.root} is not a Git repository",
            "a checkpoint is a commit; run `git init` first",
        )
    if args.gh_status and not args.baseline_tag:
        # V1 #5 acceptance: `--gh-status` must not block the checkpoint when no
        # --baseline-tag is requested (i.e. the user wants a plain commit).
        # Warn rather than fail; the URL is silently dropped in this case.
        args.gh_status = None
    active, recovery = state.load_active_with_findings(paths)
    explicit = [_normalize(paths.root, raw) for raw in args.paths]
    requested = _requested(paths, active, args, explicit)
    patterns = _protected(paths)
    files, findings = _screen(paths, requested, patterns)
    findings.extend(_warn_unmatched(paths, explicit, files))

    result = Result(payload={"root": str(paths.root), "files": files, "count": len(files)})
    for finding in recovery + findings:
        result.add(finding)

    if not files:
        return _nothing_to_commit(result, args)
    if args.dry_run:
        result.payload["message"] = _message(active, state.load_ledger(paths), args)
        result.payload["dry_run"] = True
        result.human = "would stage:\n" + "\n".join(f"  {path}" for path in files)
        return result
    return _commit(paths, active, files, args, result)


def _nothing_to_commit(result: Result, args: argparse.Namespace) -> Result:
    if args.require_change:
        result.add(
            Finding(
                "CHECKPOINT_NOTHING_TO_COMMIT",
                SEVERITY_WARNING,
                "checkpoint",
                "no files matched the requested path set",
                "check --paths, or drop --require-change if an empty checkpoint is acceptable",
            )
        )
    else:
        result.human = "nothing to commit"
    return result


def _commit(
    paths: repo.ResearchPaths,
    active: Record,
    files: list[str],
    args: argparse.Namespace,
    result: Result,
) -> Result:
    message = _message(active, state.load_ledger(paths), args)
    staged = jgit.git(["add", "--", *files], cwd=paths.root)
    if not staged.ok:
        raise StateInvalid(
            [Finding("CHECKPOINT_STAGE_FAILED", SEVERITY_ERROR, "git add", staged.stderr.strip())]
        )
    if not jgit.git(["diff", "--cached", "--name-only"], cwd=paths.root).stdout.strip():
        return _nothing_to_commit(result, args)

    committed = jgit.git(["commit", "-m", message], cwd=paths.root)
    if not committed.ok:
        raise StateInvalid(
            [
                Finding(
                    "CHECKPOINT_COMMIT_FAILED",
                    SEVERITY_ERROR,
                    "git commit",
                    committed.stderr.strip(),
                )
            ]
        )
    sha = jgit.head_commit(paths.root)
    result.payload.update({"commit": sha, "message": message, "dry_run": False})
    if args.tag:
        finding = _tag(paths, args.tag)
        if finding is not None:
            result.add(finding)
        result.payload["tag"] = args.tag
    if args.baseline_tag:
        finding = _baseline_tag(paths, args.baseline_tag, args.gh_status, message)
        if finding is not None:
            result.add(finding)
        result.payload["baseline_tag"] = args.baseline_tag
        if args.gh_status:
            result.payload["gh_status"] = args.gh_status
    _stamp_active(paths, active, sha)
    result.payload["active_updated"] = True
    result.human = f"checkpoint {sha[:12] if sha else '?'} — {len(files)} file(s)\n{message}"
    return result


def _tag(paths: repo.ResearchPaths, name: str) -> Finding | None:
    """A tag failure is reported, never fatal: the commit is already made and worth keeping."""
    tagged = jgit.git(["tag", name], cwd=paths.root)
    if tagged.ok:
        return None
    return Finding(
        "CHECKPOINT_TAG_FAILED",
        SEVERITY_WARNING,
        name,
        f"the commit succeeded but the tag did not: {tagged.stderr.strip()}",
        "tag it by hand once the name is valid and unused",
    )


def _baseline_tag(
    paths: repo.ResearchPaths,
    name: str,
    gh_status: str | None,
    commit_message: str,
) -> Finding | None:
    """V1 Block 3 / S2: annotated tag for a promotion-bound baseline.

    Annotation message includes the commit's first line (so the tag reads as a
    promotion-bound marker) and, when `--gh-status URL` was passed, an extra
    `Gate-3: <url>` line. Tag failure is non-fatal: the commit is already made.
    """
    annotation_lines = [
        f"baseline: {commit_message.splitlines()[0] if commit_message else 'checkpoint'}",
    ]
    if gh_status:
        annotation_lines.append(f"Gate-3: {gh_status}")
    annotation = "\n".join(annotation_lines)
    tagged = jgit.git(["tag", "-a", name, "-m", annotation], cwd=paths.root)
    if tagged.ok:
        return None
    return Finding(
        "CHECKPOINT_BASELINE_TAG_FAILED",
        SEVERITY_WARNING,
        name,
        f"the commit succeeded but the baseline tag did not: {tagged.stderr.strip()}",
        "run `git tag -a <name> -m <msg>` by hand once the name is valid and unused",
    )


def _stamp_active(paths: repo.ResearchPaths, active: Record, sha: str | None) -> None:
    schema.require_writable("active", paths.active, active.raw)
    active.set("git.checkpoint_commit", sha)
    active.set("updated_at", _now())
    ioutil.write_json_atomic(paths.active, active.raw, validator=schema.load_validator("active"))


def _requested(
    paths: repo.ResearchPaths,
    active: Record,
    args: argparse.Namespace,
    explicit: list[str],
) -> list[str]:
    requested = list(explicit)
    if paths.research.is_dir():
        requested.append(RESEARCH_PREFIX)
    requested.extend(
        _normalize(paths.root, raw) for raw in active.get("git.expected_touched_files") or []
    )
    if args.all_expected:
        requested.extend(_modified(paths, include_untracked=args.include_untracked))
    elif args.include_untracked:
        requested.extend(_modified(paths, include_untracked=True))
    return _dedupe(requested)


def _modified(paths: repo.ResearchPaths, *, include_untracked: bool) -> list[str]:
    """Every path Git currently reports as changed — the explicit opt-in to a wider stage."""
    found: list[str] = []
    for line in jgit.status_porcelain(paths.root):
        code, name = line[:2], line[3:]
        if code.strip() == "??" and not include_untracked:
            continue
        found.append(_normalize(paths.root, _status_path(name)))
    return found


def _status_path(name: str) -> str:
    """`git status --porcelain` reports a rename as `old -> new`; the new path is the file."""
    return name.strip().strip('"').split(" -> ")[-1]


def _screen(
    paths: repo.ResearchPaths,
    requested: list[str],
    patterns: tuple[str, ...],
) -> tuple[list[str], list[Finding]]:
    files: list[str] = []
    findings: list[Finding] = []
    for relative in _expand(paths, requested):
        pattern = _protected_by(relative, patterns)
        if pattern is not None:
            # Info, not a warning: excluding run logs is the designed behaviour of the
            # default path set, and a warning on the normal case trains people to ignore them.
            findings.append(
                Finding(
                    "CHECKPOINT_PATH_PROTECTED",
                    SEVERITY_INFO,
                    relative,
                    f"excluded by the pattern {pattern!r}",
                    f"run directories and large binaries stay out; list one in {IGNORE_FILE} to change this",
                )
            )
            continue
        target = paths.root / relative
        if not target.is_file():
            continue  # a tracked file deleted from the worktree; git add stages the deletion
        size = target.stat().st_size
        if size > MAX_FILE_BYTES:
            raise RefusedByPolicy(
                "CHECKPOINT_FILE_TOO_LARGE",
                f"{relative} is {size} bytes, above the {MAX_FILE_BYTES} byte ceiling",
                "reference it as an artifact in the evidence record instead of committing it; "
                "a pointer is durable, a large binary in history is permanent",
            )
        files.append(relative)
    return sorted(set(files)), findings


def _expand(paths: repo.ResearchPaths, requested: list[str]) -> list[str]:
    """Only files Git would actually add: tracked, or untracked and not ignored."""
    if not requested:
        return []
    listed = jgit.git(
        ["ls-files", "--cached", "--others", "--exclude-standard", "--", *requested],
        cwd=paths.root,
    )
    if not listed.ok:
        raise PreconditionMissing(
            "CHECKPOINT_LS_FILES_FAILED", listed.stderr.strip() or "git ls-files failed"
        )
    return [line.strip() for line in listed.stdout.splitlines() if line.strip()]


def _warn_unmatched(
    paths: repo.ResearchPaths, explicit: list[str], files: list[str]
) -> list[Finding]:
    findings: list[Finding] = []
    for relative in explicit:
        if any(path == relative or path.startswith(f"{relative.rstrip('/')}/") for path in files):
            continue
        findings.append(
            Finding(
                "CHECKPOINT_PATH_UNMATCHED",
                SEVERITY_WARNING,
                relative,
                "--paths named a file that Git has nothing to add for",
                "check the spelling, or the file may be ignored by .gitignore",
            )
        )
    return findings


def _normalize(root: Path, raw: str) -> str:
    candidate = Path(raw)
    if ".." in candidate.parts:
        raise RefusedByPolicy(
            "CHECKPOINT_PATH_ESCAPES_REPO",
            f"{raw!r} contains '..'",
            "pass a path relative to the repository root",
        )
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise RefusedByPolicy(
            "CHECKPOINT_PATH_OUTSIDE_REPO",
            f"{raw!r} resolves to {resolved}, outside {root}",
            "a checkpoint commits this repository only",
        ) from exc


def _protected(paths: repo.ResearchPaths) -> tuple[str, ...]:
    ignore_file = paths.research / IGNORE_FILE
    if not ignore_file.is_file():
        return DEFAULT_PROTECTED
    lines = [line.strip() for line in ignore_file.read_text(encoding="utf-8").splitlines()]
    listed = tuple(line for line in lines if line and not line.startswith("#"))
    return listed or DEFAULT_PROTECTED


def _protected_by(relative: str, patterns: tuple[str, ...]) -> str | None:
    parts = relative.split("/")
    for pattern in patterns:
        if pattern.endswith("/"):
            if pattern[:-1] in parts:
                return pattern
        elif fnmatch.fnmatch(parts[-1], pattern) or fnmatch.fnmatch(relative, pattern):
            return pattern
    return None


def _message(active: Record, ledger: state.Ledger, args: argparse.Namespace) -> str:
    block_id = active.get("block.id") or "-"
    hypotheses = [str(h) for h in active.get("hypothesis_ids") or []]
    evidence = _evidence_ids(ledger, hypotheses)
    base = args.message or f"checkpoint {block_id if block_id != '-' else 'research state'}"
    return "\n".join(
        [
            base,
            "",
            f"Research-Block: {block_id}",
            f"Hypotheses: {' '.join(hypotheses) or '-'}",
            f"Evidence: {' '.join(evidence) or '-'}",
            f"ACTIVE-Status: {active.get('status') or '-'}",
        ]
    )


def _evidence_ids(ledger: state.Ledger, hypotheses: list[str]) -> list[str]:
    if not hypotheses:
        return []
    wanted = set(hypotheses)
    return sorted(
        evidence_id
        for evidence_id, record in ledger.records.items()
        if wanted & {str(h) for h in record.get("hypothesis_ids") or []}
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for value in values:
        seen.setdefault(value, None)
    return list(seen)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
