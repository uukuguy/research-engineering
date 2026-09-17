"""`researchlog reconcile` — compare the state planes and report. Never repair.

There is deliberately no `--fix-orphans`. Reconstructing a missing evidence record
requires observations, an outcome and a belief delta — the scientific content — and a
tool that generates those is inventing evidence. What the tool can do is make detection
cheap enough that skipping it is inexcusable, and hand back a *template* whose factual
fields are pre-filled from the run manifest and whose scientific fields must come from
the agent.

The detectors below are each a restatement of one invariant from the design, expressed
as something a machine can check.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from researchlog import constraints, jgit, repo, schema, state
from researchlog.errors import (
    Finding,
    Result,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    StateInvalid,
)

NAME = "reconcile"
HELP = "compare ACTIVE, Git, run manifests and evidence; report inconsistencies"

STALE_RUNNING_MINUTES = 120


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--stale-after",
        type=int,
        default=STALE_RUNNING_MINUTES,
        help="minutes after which a running manifest with no heartbeat is stale",
    )


def run(args: argparse.Namespace) -> Result:
    paths = repo.require(args.root)
    ledger = state.load_ledger(paths)
    result = Result(payload={"root": str(paths.root)})

    for finding in ledger.unreadable:
        result.add(finding)
    for finding in _active_load_findings(paths):
        result.add(finding)

    detectors = (
        _orphan_runs,
        _missing_results,
        _stale_running,
        _dangling_evidence,
        _active_git_mismatch,
        _active_manifest_stale,
        _self_referential_commits,
        _superseded_findings_cited,
        _incomplete_signals,
        _expired_signals,
        _submission_budget,
        _token_budget,
        _gitignore_guard,
        _worktree_multi_writer,
    )
    for detector in detectors:
        for finding in detector(paths, ledger, args):
            result.add(finding)

    result.payload["evidence_records"] = len(ledger.records)
    result.payload["manifests"] = len(ledger.manifests)
    result.payload["clean"] = not result.findings
    return result


def _active_load_findings(paths: repo.ResearchPaths) -> list[Finding]:
    """What happened while reading ACTIVE, reported rather than swallowed.

    Every detector below reads ACTIVE through a loader that catches its own failure, so an
    unreadable execution pointer used to produce `clean: true` — the one answer a resume
    must never give, since it declares the state intact at the exact moment the file the
    session resumes from cannot be parsed. Recovery from the last commit is reported here
    too, so a state that had to be recovered is never mistaken for an untouched one.
    """
    try:
        active, findings = state.load_active_with_findings(paths)
    except StateInvalid as exc:
        return list(exc.findings)
    # A pointer written by a newer tool is readable and cannot be written, so a resume has
    # to hear about it now rather than on its first attempt to update something.
    return [*findings, *schema.version_findings("active", active.raw, where="ACTIVE.json")]


def _orphan_runs(paths: repo.ResearchPaths, ledger: state.Ledger, _args: argparse.Namespace) -> list[Finding]:
    """A finished run whose result was never turned into evidence."""
    referenced = ledger.experiments_referenced()
    findings: list[Finding] = []
    for experiment_id, manifest in sorted(ledger.manifests.items()):
        if experiment_id in referenced:
            continue
        if not state.manifest_completed(manifest):
            continue
        if not paths.result(experiment_id).is_file():
            continue
        findings.append(
            Finding(
                "ORPHAN_RUN",
                SEVERITY_ERROR,
                experiment_id,
                "the run finished and produced a result, but no evidence record references it",
                f"run `researchlog record --from-orphan {experiment_id}` to fill in the scientific "
                f"fields; do not start new work until this is recorded",
            )
        )
    return findings


def _missing_results(paths: repo.ResearchPaths, ledger: state.Ledger, _args: argparse.Namespace) -> list[Finding]:
    findings: list[Finding] = []
    for experiment_id, manifest in sorted(ledger.manifests.items()):
        if manifest.get("status") != "completed":
            continue
        if not paths.result(experiment_id).is_file():
            findings.append(
                Finding(
                    "MANIFEST_RESULT_MISSING",
                    SEVERITY_ERROR,
                    experiment_id,
                    "the manifest says completed but no result.json was written",
                    "the run may have been finalised outside the tool; check stdout.log before trusting it",
                )
            )
    return findings


def _stale_running(
    paths: repo.ResearchPaths, ledger: state.Ledger, args: argparse.Namespace
) -> list[Finding]:
    findings: list[Finding] = []
    for experiment_id, manifest in sorted(ledger.manifests.items()):
        if manifest.get("status") != "running":
            continue
        age = _age_minutes(manifest.get("execution", {}).get("heartbeat_or_last_observed_at"))
        if age is not None and age > args.stale_after:
            findings.append(
                Finding(
                    "MANIFEST_STALE_RUNNING",
                    SEVERITY_WARNING,
                    experiment_id,
                    f"manifest still says running but its last heartbeat was {age:.0f} minutes ago",
                    f"run `researchlog job --experiment-id {experiment_id}` to establish liveness",
                )
            )
    return findings


def _dangling_evidence(
    paths: repo.ResearchPaths, ledger: state.Ledger, _args: argparse.Namespace
) -> list[Finding]:
    findings: list[Finding] = []
    for evidence_id, record in sorted(ledger.records.items()):
        experiment_id = record.get("experiment_id")
        if not experiment_id:
            continue
        if not paths.manifest(str(experiment_id)).is_file():
            findings.append(
                Finding(
                    "DANGLING_EVIDENCE",
                    SEVERITY_ERROR,
                    evidence_id,
                    f"cites experiment {experiment_id}, for which no manifest exists",
                    "the evidence is still valid; the provenance pointer is not",
                )
            )
    return findings


def _active_git_mismatch(
    paths: repo.ResearchPaths, _ledger: state.Ledger, _args: argparse.Namespace
) -> list[Finding]:
    if not jgit.is_repository(paths.root):
        return []
    try:
        active = state.load_active(paths)
    except Exception:  # noqa: BLE001 - a broken ACTIVE is reported by `validate`
        return []
    expected_dirty = active.get("git.dirty_expected")
    actual_dirty = jgit.is_dirty(paths.root)
    if expected_dirty is False and actual_dirty:
        return [
            Finding(
                "ACTIVE_GIT_MISMATCH",
                SEVERITY_ERROR,
                "ACTIVE.json",
                "ACTIVE expects a clean tree but the working tree is dirty",
                "reconcile the worktree against ACTIVE before starting new research",
            )
        ]
    return []


def _active_manifest_stale(
    paths: repo.ResearchPaths, ledger: state.Ledger, _args: argparse.Namespace
) -> list[Finding]:
    try:
        active = state.load_active(paths)
    except Exception:  # noqa: BLE001
        return []
    if active.get("execution.status") != "running":
        return []
    experiment_id = active.get("experiment_id")
    manifest = ledger.manifests.get(str(experiment_id)) if experiment_id else None
    if manifest and manifest.get("status") not in (None, "running"):
        return [
            Finding(
                "ACTIVE_MANIFEST_STALE",
                SEVERITY_ERROR,
                str(experiment_id),
                f"ACTIVE still says running but the manifest is {manifest.get('status')!r}",
                "the run finished while the session was away; review it, do not restart it",
            )
        ]
    return []


def _self_referential_commits(
    paths: repo.ResearchPaths, ledger: state.Ledger, _args: argparse.Namespace
) -> list[Finding]:
    """A commit citing evidence whose code_state points back at that same commit."""
    if not jgit.is_repository(paths.root):
        return []
    findings: list[Finding] = []
    for sha, evidence_id in jgit.evidence_trailers(paths.root):
        record = ledger.records.get(evidence_id)
        if not record:
            continue
        code_state = record.get("code_state") or {}
        if code_state.get("commit") == sha:
            findings.append(
                Finding(
                    "SELF_REFERENTIAL_COMMIT",
                    SEVERITY_ERROR,
                    sha[:12],
                    f"commit cites {evidence_id}, whose code_state points back at this same commit",
                    "code_state must name the state that produced the evidence, not the commit "
                    "that stored the record",
                )
            )
    return findings


def _superseded_findings_cited(
    _paths: repo.ResearchPaths, ledger: state.Ledger, _args: argparse.Namespace
) -> list[Finding]:
    superseded = {
        str(entry.get("id")) for entry in ledger.findings_entries if entry.get("status") == "Superseded"
    }
    if not superseded:
        return []
    findings: list[Finding] = []
    for evidence_id, record in sorted(ledger.records.items()):
        cited = superseded & set(record.get("supports") or [])
        if cited:
            findings.append(
                Finding(
                    "SUPERSEDED_FINDING_CITED",
                    SEVERITY_WARNING,
                    evidence_id,
                    f"still cites superseded finding(s): {', '.join(sorted(cited))}",
                    "re-point it at the replacement, or the belief graph has a stale edge",
                )
            )
    return findings


def _signal_blocks(paths: repo.ResearchPaths) -> list[dict]:
    """The `research:signal` blocks in ARCHITECT.md, or none if it cannot be read."""
    if not paths.architect.is_file():
        return []
    try:
        return schema.extract_blocks(paths.architect.read_text(encoding="utf-8")).get("signal", [])
    except Exception:  # noqa: BLE001 - reported by validate
        return []


def _incomplete_signals(
    paths: repo.ResearchPaths, _ledger: state.Ledger, _args: argparse.Namespace
) -> list[Finding]:
    """A signal that lost the wording it was given.

    The rule lives in `constraints` with the other meanings the schema cannot express.
    It is surfaced here as well as in `validate` because `reconcile` is the entry point
    the resume protocol actually runs, and a rule reported only on a path nobody takes
    is a rule that never fires.
    """
    findings: list[Finding] = []
    for signal in _signal_blocks(paths):
        findings.extend(constraints.check_signal(signal))
    return findings


def _expired_signals(
    paths: repo.ResearchPaths, _ledger: state.Ledger, _args: argparse.Namespace
) -> list[Finding]:
    """Only mechanically checkable expiries are enforced.

    `expiry` carries one of two things. An ISO 8601 timestamp is a date, and a date is
    exactly what a machine is for. A free-text promise such as "recovery checkpoint" is
    kept by a human, and the tool says so by ignoring it rather than pretending to
    evaluate it.
    """
    now = datetime.now(timezone.utc)
    findings: list[Finding] = []
    for signal in _signal_blocks(paths):
        if signal.get("active") is False:
            continue
        expiry = signal.get("expiry")
        if not isinstance(expiry, str):
            continue
        try:
            deadline = datetime.fromisoformat(expiry)
        except ValueError:
            continue  # a free-text expiry; a promise, deliberately not evaluated
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if deadline < now:
            findings.append(
                Finding(
                    "EXPIRED_ARCHITECT_SIGNAL",
                    SEVERITY_WARNING,
                    str(signal.get("id", "?")),
                    f"{signal.get('type')} signal expired at {expiry} but is still active",
                    "re-confirm it or let it lapse; a temporary constraint must not become doctrine",
                )
            )
    return findings


def _submission_budget(
    paths: repo.ResearchPaths, _ledger: state.Ledger, _args: argparse.Namespace
) -> list[Finding]:
    if not paths.boundaries.is_file():
        return []
    try:
        block = schema.find_block(paths.boundaries.read_text(encoding="utf-8"), "boundaries")
    except Exception:  # noqa: BLE001
        return []
    if not block:
        return []
    budget = block.get("submission_budget")
    used = block.get("submissions_used") or 0
    if isinstance(budget, int) and used >= budget:
        return [
            Finding(
                "BOUNDARIES_BUDGET_LOW",
                SEVERITY_ERROR,
                "BOUNDARIES.md",
                f"{used} of {budget} official submissions used",
                "official submissions cannot be recovered by working harder; this needs the architect",
            )
        ]
    return []


def _token_budget(
    paths: repo.ResearchPaths, _ledger: state.Ledger, _args: argparse.Namespace
) -> list[Finding]:
    """Report a block that reported more spend than it declared.

    This is telemetry, not enforcement. Token spend happens in the agent runtime and
    never reaches the filesystem on its own, so the number here is self-reported and the
    check is retrospective. Calling it a budget would overstate what a file-based tool
    can do.
    """
    try:
        active = state.load_active(paths)
    except Exception:  # noqa: BLE001 - a broken ACTIVE is reported by `validate`
        return []
    limit = active.get("block.max_tokens")
    used = active.get("block.tokens_used")
    if not isinstance(limit, int) or not isinstance(used, int) or used <= limit:
        return []
    return [
        Finding(
            "BLOCK_TOKEN_BUDGET_EXCEEDED",
            SEVERITY_WARNING,
            str(active.get("block.id") or "block"),
            f"reported spend {used} exceeds the declared max_tokens {limit}",
            "close the block and synthesise what was learned; the number is a signal "
            "about search discipline, not a hard stop",
        )
    ]


def _gitignore_guard(
    paths: repo.ResearchPaths, _ledger: state.Ledger, _args: argparse.Namespace
) -> list[Finding]:
    if not jgit.is_repository(paths.root):
        return []
    probe = f"{repo.RESEARCH_DIR}/{repo.RUNS_DIR}/EXP-probe/manifest.json"
    pattern = jgit.check_ignore(paths.root, probe)
    if pattern is None:
        return []
    return [
        Finding(
            "RUNS_DIR_IGNORED_BY_GITIGNORE",
            SEVERITY_ERROR,
            probe,
            f"run manifests are excluded from Git by the pattern {pattern!r}",
            "anchor it to the repository root; Git cannot re-include a file inside an "
            "excluded directory, so negation patterns will not help",
        )
    ]


def _worktree_multi_writer(
    paths: repo.ResearchPaths, _ledger: state.Ledger, _args: argparse.Namespace
) -> list[Finding]:
    """P9 single-writer enforcement: only one worktree may write research/ at a time.

    Multi-writer is structurally unsafe — a merge conflict in canonical state silently
    loses one writer's work. The detector flags every dirty worktree beyond the first,
    so the agent has a name to act on rather than a vague "stop writing".

    The check is on `research/` specifically, not the whole tree: `code_state` already
    tracks general dirtiness, and a code change on a sibling worktree is unrelated to
    canonical state. The protocol binds canonical state, not code.
    """
    if not jgit.is_repository(paths.root):
        return []
    worktrees = _list_worktrees(paths.root)
    if len(worktrees) <= 1:
        return []
    dirty: list[dict[str, str]] = []
    for wt in worktrees:
        wt_path = wt.get("path")
        if not wt_path:
            continue
        # Skip detached worktrees the porcelain check can't address safely — detached
        # worktrees that dirty research/ are still illegal; we just can't reach them here
        # without making the detector's false-negative rate worse than its signal.
        porcelain = jgit.git(
            ["status", "--porcelain", "--", repo.RESEARCH_DIR], cwd=Path(wt_path)
        )
        if porcelain.ok and porcelain.stdout.strip():
            dirty.append(wt)
    if len(dirty) <= 1:
        return []
    paths_repr = ", ".join(wt["path"] for wt in dirty)
    return [
        Finding(
            "WORKTREE_MULTI_WRITER",
            SEVERITY_ERROR,
            repo.RESEARCH_DIR,
            f"{len(dirty)} worktrees have dirty changes under {repo.RESEARCH_DIR}: "
            f"{paths_repr}",
            "P9 enforces single-writer on research/. Commit / stash the other writers "
            "first, then re-run `reconcile`; merging canonical state across worktrees "
            "loses one writer's record silently",
        )
    ]


def _list_worktrees(root: Path) -> list[dict[str, str]]:
    """Parse `git worktree list --porcelain` into a list of {path, head, branch}.

    Format (per worktree, blank-line separated):
        worktree /abs/path
        HEAD abc1234
        branch refs/heads/main

    Detached worktrees carry no `branch` line and are skipped from the dict — they are
    still surfaced via `path` and `head`, which is enough to decide whether to probe them.
    """
    result = jgit.git(["worktree", "list", "--porcelain"], cwd=root)
    if not result.ok:
        return []
    worktrees: list[dict[str, str]] = []
    for block in result.stdout.split("\n\n"):
        if not block.strip():
            continue
        entry: dict[str, str] = {}
        for line in block.splitlines():
            if line.startswith("worktree "):
                entry["path"] = line[len("worktree ") :].strip()
            elif line.startswith("HEAD "):
                entry["head"] = line[len("HEAD ") :].strip()
            elif line.startswith("branch "):
                # refs/heads/<branch> → <branch>
                parts = line[len("branch ") :].strip().split("/")
                entry["branch"] = parts[-1] if parts else ""
        if "path" in entry:
            worktrees.append(entry)
    return worktrees


def _age_minutes(timestamp: object) -> float | None:
    if not isinstance(timestamp, str):
        return None
    try:
        moment = datetime.fromisoformat(timestamp)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - moment).total_seconds() / 60.0
