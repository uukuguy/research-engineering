"""`researchlog record` — append one immutable evidence record to the ledger.

Raw evidence is append-only and is the only thing in the system that cannot be rebuilt
from something else, so this command is deliberately strict:

* the identifier is **claimed**, not counted — `ids.claim_new` reserves it with an
  exclusive create, so two worktrees cannot mint the same EV id;
* `counts_as_evidence_iteration` is **recomputed** from the fields that derive it, and a
  caller-supplied value that disagrees is rejected rather than quietly overwritten;
* the invariant checks and the schema check both run **before** anything is written, so a
  rejected record leaves the ledger untouched — no half-record, no empty shard.

`--from-orphan` is a template, not a repair. It copies the factual fields out of a run
manifest (what ran, on what code, in what environment) and refuses to invent the
scientific ones: what was observed, what it meant, and how much belief moved. A tool that
generates those is inventing evidence, which is the one thing this is not allowed to do.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from researchlog import constraints, ids, ioutil, jgit, repo, schema, state
from researchlog.errors import (
    Finding,
    PreconditionMissing,
    Result,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    StateInvalid,
)

NAME = "record"
HELP = "append one immutable evidence record to research/ledger"

SCIENTIFIC_FIELDS: tuple[str, ...] = (
    "observations",
    "research_outcome",
    "belief_delta",
    "confidence",
)
ORPHAN_FACTUAL_FIELDS: tuple[str, ...] = (
    "question",
    "subject",
    "hypothesis_ids",
    "inputs",
    "environment",
    "code_state",
    "experiment_id",
)
CONFIDENCES: tuple[str, ...] = ("low", "moderate", "high", "certain")
EXECUTION_STATUSES: tuple[str, ...] = (
    "completed",
    "interrupted",
    "infra_failed",
    "env_blocked",
    "env_unsupported",
    "resource_exceeded",
    "invalid",
)
RESEARCH_OUTCOMES: tuple[str, ...] = (
    "confirmed",
    "refuted",
    "inconclusive",
    "failed",
    "informative_failure",
    "promising",
    "none",
)


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=None)
    source = parser.add_argument_group("source document")
    source.add_argument(
        "--evidence-file", metavar="PATH", default=None, help="a JSON document, or - for stdin"
    )
    source.add_argument(
        "--from-json", metavar="JSON", default=None, help="a JSON document given inline"
    )
    source.add_argument(
        "--from-orphan", metavar="EXP-ID", default=None, help="pre-fill facts from a run manifest"
    )

    parser.add_argument("--question", default=None)
    parser.add_argument("--subject-type", default=None)
    parser.add_argument("--subject-id", default=None)
    parser.add_argument("--level", choices=constraints.EVIDENCE_LEVELS, default=None)
    parser.add_argument("--target-level", choices=constraints.EVIDENCE_LEVELS, default=None)
    parser.add_argument("--surrogate", action="store_true")
    parser.add_argument("--surrogate-contract", metavar="PATH", default=None)
    parser.add_argument("--execution-status", choices=EXECUTION_STATUSES, default=None)
    parser.add_argument("--research-outcome", choices=RESEARCH_OUTCOMES, default=None)
    parser.add_argument("--confidence", choices=CONFIDENCES, default=None)
    parser.add_argument("--experiment-id", default=None)
    parser.add_argument(
        "--no-experiment", action="store_true", help="record no experiment provenance"
    )
    parser.add_argument("--hypothesis", action="append", default=[], metavar="H-ID")
    parser.add_argument("--hypotheses-differentiated", default=None, metavar="H-A,H-B")
    parser.add_argument("--belief-delta", choices=sorted(constraints.BELIEF_DELTAS), default=None)
    parser.add_argument("--observation", action="append", default=[], metavar="TEXT")
    parser.add_argument("--measurement", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--supports", action="append", default=[], metavar="FND-ID")
    parser.add_argument("--contradicts", action="append", default=[], metavar="FND-ID")
    parser.add_argument("--limitation", action="append", default=[], metavar="TEXT")
    parser.add_argument("--artifact", action="append", default=[], metavar="PATH")
    parser.add_argument("--artifact-role", default=None, help="role applied to every --artifact")
    parser.add_argument("--invalidated-if", action="append", default=[], metavar="PREDICATE")
    parser.add_argument("--anchor", action="store_true")


def run(args: argparse.Namespace) -> Result:
    paths = repo.require(args.root)
    document, warnings = _build(args, paths)
    document["evidence_id"] = ids.mint("evidence")  # provisional, for validation only

    findings = _inspect(document, warnings)
    errors = [f for f in findings if f.severity == SEVERITY_ERROR]
    if errors:
        raise StateInvalid(errors)

    evidence_id, path = ids.claim_new("evidence", paths.evidence)
    document["evidence_id"] = evidence_id
    validator = schema.load_validator("evidence")
    ioutil.write_json_atomic(path, document, validator=validator)

    # V1 P1: every recorded evidence is followed by a commit so the next session
    # can reconcile against git rather than disk state. The commit message lives
    # in a tmpfile (lesson E1: backticks in `git commit -m` are silently command-
    # substituted). Failure throws — the evidence is on disk but untracked, and
    # the rest of the session needs to know not to keep stacking on top.
    evidence_relpath = path.relative_to(paths.root).as_posix()
    _commit_evidence(paths, evidence_id, evidence_relpath)

    result = Result(
        payload={
            "evidence_id": evidence_id,
            "path": str(path),
            "experiment_id": document.get("experiment_id"),
            "evidence_level": document.get("evidence_level"),
            "counts_as_evidence_iteration": document["counts_as_evidence_iteration"],
            "code_state": document.get("code_state"),
        }
    )
    for finding in findings:
        result.add(finding)
    result.human = f"recorded {evidence_id} at {path}"
    return result


def _build(
    args: argparse.Namespace, paths: repo.ResearchPaths
) -> tuple[dict[str, Any], list[Finding]]:
    warnings: list[Finding] = []
    document = _source_document(args, paths)
    document.setdefault("schema_version", "1.0")
    _apply_identity(document, args)
    _apply_science(document, args, paths, warnings)
    _apply_links(document, args)
    document.setdefault("created_at", _now())
    if document.get("code_state") is None:
        document["code_state"] = jgit.code_state(paths.root).to_dict()
    if document.get("block_id") is None:
        # Which block this evidence was produced under. Without it, membership has to be
        # guessed from the hypotheses the record names, and a block opened later on the same
        # hypotheses silently inherits this one's iterations.
        document["block_id"] = _current_block_id(paths)
    if document.get("environment") is None:
        _snapshot_environment(document, paths)
    if args.from_orphan is not None:
        _require_scientific(document, args.from_orphan)
    _derive_counts(document)
    return document, warnings


def _current_block_id(paths: repo.ResearchPaths) -> Any:
    """The id of the block that is open, or None.

    Tolerant on purpose: a record must still be writable when ACTIVE is missing or
    unreadable, because refusing to record evidence is worse than recording it with no
    block. The block is bookkeeping; the evidence is the product.
    """
    try:
        return state.load_active(paths).get("block.id")
    except Exception:  # noqa: BLE001 - a broken ACTIVE must not block a record
        return None


def _snapshot_environment(document: dict[str, Any], paths: repo.ResearchPaths) -> None:
    """Record the environment this evidence was produced in.

    Without it a `changed` predicate has nothing to compare against, because `then` is
    read back from the record itself. A record written before any environment change has
    no values to carry yet, so only the identity fields are set — which is still enough
    for a later `changed` to report UNRESOLVED honestly rather than silently pass.
    """
    environment, inputs = state.current_environment(paths)
    if environment is None:
        return
    document["environment"] = environment
    if inputs and not document.get("inputs"):
        document["inputs"] = inputs


def _source_document(args: argparse.Namespace, paths: repo.ResearchPaths) -> dict[str, Any]:
    chosen = [
        name
        for name, value in (
            ("--evidence-file", args.evidence_file),
            ("--from-json", args.from_json),
            ("--from-orphan", args.from_orphan),
        )
        if value is not None
    ]
    if len(chosen) > 1:
        raise StateInvalid(
            [
                Finding(
                    "EVIDENCE_SOURCE_AMBIGUOUS",
                    SEVERITY_ERROR,
                    "-",
                    f"more than one source document given: {', '.join(chosen)}",
                    "exactly one of --evidence-file, --from-json or --from-orphan may be used",
                )
            ]
        )
    if args.evidence_file is not None:
        return _parse_document(_read_source(args.evidence_file), "--evidence-file")
    if args.from_json is not None:
        return _parse_document(args.from_json, "--from-json")
    if args.from_orphan is not None:
        return _orphan_template(paths, args.from_orphan)
    return {}


def _orphan_template(paths: repo.ResearchPaths, experiment_id: str) -> dict[str, Any]:
    manifest_path = paths.manifest(experiment_id)
    if not manifest_path.is_file():
        raise PreconditionMissing(
            "MANIFEST_ABSENT",
            f"no manifest for {experiment_id} at {manifest_path}",
            "check the experiment id, or record this evidence without --from-orphan",
        )
    manifest = ioutil.load_json(manifest_path)
    template: dict[str, Any] = {"experiment_id": experiment_id}
    for key in ORPHAN_FACTUAL_FIELDS:
        value = manifest.get(key)
        if value:
            template[key] = value
    artifacts = [
        entry
        for entry in (manifest.get("artifacts") or [])
        if isinstance(entry, dict) and entry.get("path")
    ]
    if artifacts:
        template["artifacts"] = artifacts
    return template


def _apply_identity(document: dict[str, Any], args: argparse.Namespace) -> None:
    if args.no_experiment and args.experiment_id is not None:
        raise StateInvalid(
            [
                Finding(
                    "EXPERIMENT_FLAG_CONFLICT",
                    SEVERITY_ERROR,
                    "-",
                    "--no-experiment and --experiment-id cannot both be given",
                    "drop --no-experiment if you meant to bind this evidence to an experiment, "
                    "or drop --experiment-id if you meant a standalone observation",
                )
            ]
        )
    if args.experiment_id is not None:
        document["experiment_id"] = args.experiment_id
    elif args.no_experiment:
        document["experiment_id"] = None
    if args.question is not None:
        document["question"] = args.question
    if args.subject_type is not None or args.subject_id is not None:
        if not (args.subject_type and args.subject_id):
            raise StateInvalid(
                [
                    Finding(
                        "SUBJECT_INCOMPLETE",
                        SEVERITY_ERROR,
                        "-",
                        "a subject needs both a type and an id",
                        "for example --subject-type mechanism --subject-id M-014",
                    )
                ]
            )
        document["subject"] = {"type": args.subject_type, "id": args.subject_id}


def _apply_science(
    document: dict[str, Any],
    args: argparse.Namespace,
    paths: repo.ResearchPaths,
    warnings: list[Finding],
) -> None:
    for name, value in (
        ("evidence_level", args.level),
        ("target_evidence_level", args.target_level),
        ("execution_status", args.execution_status),
        ("research_outcome", args.research_outcome),
        ("confidence", args.confidence),
        ("belief_delta", args.belief_delta),
    ):
        if value is not None:
            document[name] = value
    if args.surrogate:
        document["surrogate"] = True
    if args.surrogate_contract is not None:
        document["surrogate_contract"] = _parse_document(
            _read_source(args.surrogate_contract), "--surrogate-contract"
        )
    if args.observation:
        document["observations"] = list(args.observation)
    if args.measurement:
        document["measurements"] = _measurements(args.measurement)
    if args.artifact:
        document["artifacts"] = _artifacts(args.artifact, args.artifact_role, paths, warnings)
    elif args.artifact_role is not None:
        raise StateInvalid(
            [
                Finding(
                    "ARTIFACT_ROLE_WITHOUT_ARTIFACT",
                    SEVERITY_ERROR,
                    "-",
                    "--artifact-role was given without --artifact",
                    "pass --artifact PATH alongside --artifact-role ROLE, or remove --artifact-role",
                )
            ]
        )


def _apply_links(document: dict[str, Any], args: argparse.Namespace) -> None:
    for name, value in (
        ("hypothesis_ids", args.hypothesis),
        ("supports", args.supports),
        ("contradicts", args.contradicts),
        ("limitations", args.limitation),
        ("invalidated_if", args.invalidated_if),
    ):
        if value:
            document[name] = list(value)
    if args.hypotheses_differentiated is not None:
        document["hypotheses_differentiated"] = _split_list(args.hypotheses_differentiated)
    if args.anchor:
        document["anchor"] = True


def _derive_counts(document: dict[str, Any]) -> None:
    supplied = document.get("counts_as_evidence_iteration")
    derived = constraints.derive_counts_as_evidence_iteration(document)
    if supplied is not None and bool(supplied) != derived:
        raise StateInvalid(
            [
                Finding(
                    "EVIDENCE_ITERATION_COUNT_FALSE",
                    SEVERITY_ERROR,
                    str(document.get("evidence_id", "?")),
                    f"counts_as_evidence_iteration={supplied!r} was supplied but the fields derive "
                    f"{derived!r}",
                    "this field is computed from execution_status, research_outcome, "
                    "hypotheses_differentiated and belief_delta; do not set it by hand",
                )
            ]
        )
    document["counts_as_evidence_iteration"] = derived


def _require_scientific(document: dict[str, Any], experiment_id: str) -> None:
    missing = [name for name in SCIENTIFIC_FIELDS if document.get(name) in (None, "", [])]
    if missing:
        raise StateInvalid(
            [
                Finding(
                    "ORPHAN_SCIENTIFIC_FIELDS_MISSING",
                    SEVERITY_ERROR,
                    experiment_id,
                    f"the manifest supplies only the factual fields; still missing: {', '.join(missing)}",
                    "a manifest records what ran, not what it meant — --from-orphan is a template, "
                    "not a repair. Supply --observation, --research-outcome, --belief-delta and "
                    "--confidence from your own reading of the run",
                )
            ]
        )


def _inspect(document: dict[str, Any], warnings: list[Finding]) -> list[Finding]:
    findings = [*warnings]
    findings.extend(schema.load_validator("evidence").check(document))
    findings.extend(constraints.check_evidence(document))
    return findings


def _read_source(location: str) -> str:
    if location == "-":
        return sys.stdin.read()
    try:
        return Path(location).read_text(encoding="utf-8")
    except OSError as exc:
        raise PreconditionMissing(
            "EVIDENCE_FILE_UNREADABLE",
            f"cannot read {location}: {exc}",
            "check the path, permissions, and that the file exists; pass - to read from stdin",
        ) from exc


def _parse_document(raw: str, origin: str) -> dict[str, Any]:
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StateInvalid(
            [
                Finding(
                    "EVIDENCE_SOURCE_MALFORMED",
                    SEVERITY_ERROR,
                    origin,
                    f"line {exc.lineno} column {exc.colno}: {exc.msg}",
                    "validate the JSON locally with `python -m json.tool < source` and "
                    "fix the parse error before re-invoking record",
                )
            ]
        ) from exc
    if not isinstance(document, dict):
        raise StateInvalid(
            [
                Finding(
                    "EVIDENCE_SOURCE_NOT_OBJECT",
                    SEVERITY_ERROR,
                    origin,
                    "top level is not an object",
                    "wrap the evidence in {...} at the top level; arrays and scalars are "
                    "not valid evidence documents",
                )
            ]
        )
    return document


def _measurements(pairs: list[str]) -> dict[str, Any]:
    measurements: dict[str, Any] = {}
    for pair in pairs:
        key, separator, raw = pair.partition("=")
        if not separator or not key.strip():
            raise StateInvalid(
                [
                    Finding(
                        "MEASUREMENT_MALFORMED",
                        SEVERITY_ERROR,
                        pair,
                        "expected KEY=VALUE",
                        "for example --measurement success_rate=0.82",
                    )
                ]
            )
        measurements[key.strip()] = _literal(raw)
    return measurements


def _artifacts(
    paths_in: list[str],
    role: str | None,
    paths: repo.ResearchPaths,
    warnings: list[Finding],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for raw in paths_in:
        target = Path(raw)
        resolved = (target if target.is_absolute() else paths.root / target).resolve()
        entry: dict[str, Any] = {"path": _relative(resolved, paths.root), "role": role}
        if resolved.is_file():
            entry["sha256"] = _sha256(resolved)
            entry["size"] = resolved.stat().st_size
        else:
            entry["sha256"] = None
            entry["size"] = None
            warnings.append(
                Finding(
                    "ARTIFACT_UNREADABLE",
                    SEVERITY_WARNING,
                    str(raw),
                    "the file is not readable, so its sha256 could not be recorded",
                    "compare needs the digest to tell an unchanged artifact from a changed one",
                )
            )
        entries.append(entry)
    return entries


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _split_list(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _literal(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# V1 P1: the commit message that pairs with an evidence record. Built once per
# `record` invocation. V0 lesson E1 says the message must travel through a
# file because backticks / `$` / `!` in `git commit -m` are silently consumed
# by the shell — the message lands with words missing and no error to read.
# `_commit_evidence` is the only call site, and it owns the temp file lifecycle.
_RECORD_COMMIT_SUBJECT = "research: record {evidence_id}"


def _commit_evidence(
    paths: repo.ResearchPaths,
    evidence_id: str,
    evidence_relpath: str,
) -> None:
    """Stage the freshly written ledger file and commit it.

    Failure modes are surfaced as `COMMIT_FAILED` (state invalid, exit 2) so the
    session sees the same shape `checkpoint` already raises for the same
    underlying failure (`CHECKPOINT_COMMIT_FAILED`). Detached HEAD is *not* a
    failure: `git commit` is legal there, and a no-branch commit is the right
    shape when the agent has lost its session.
    """
    if not jgit.is_repository(paths.root):
        raise StateInvalid(
            [
                Finding(
                    "COMMIT_FAILED",
                    SEVERITY_ERROR,
                    "git commit",
                    f"{paths.root} is not a git repository",
                    "run `git init` (or clone the research repo) before invoking "
                    "`researchlog record`; V1 P1 requires the ledger entry to "
                    "land in git, not just on disk",
                )
            ]
        )

    staged = jgit.add_paths(paths.root, [evidence_relpath])
    if not staged.ok:
        raise StateInvalid(
            [
                Finding(
                    "COMMIT_FAILED",
                    SEVERITY_ERROR,
                    "git add",
                    staged.stderr.strip() or "git add returned non-zero",
                    "inspect the file path and git's index state; the ledger entry "
                    "is on disk but untracked",
                )
            ]
        )

    message = _RECORD_COMMIT_SUBJECT.format(evidence_id=evidence_id)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", suffix=".txt", delete=False
    ) as handle:
        handle.write(message + "\n")
        message_path = Path(handle.name)
    try:
        committed = jgit.commit_with_message_file(paths.root, message_path)
    finally:
        message_path.unlink(missing_ok=True)

    if not committed.ok:
        raise StateInvalid(
            [
                Finding(
                    "COMMIT_FAILED",
                    SEVERITY_ERROR,
                    "git commit",
                    committed.stderr.strip() or "git commit returned non-zero",
                    "the ledger entry is on disk but untracked; resolve the "
                    "commit failure (hooks, identity, detached HEAD policy) "
                    "and re-invoke `researchlog record` after `git add` of "
                    f"{evidence_relpath}",
                )
            ]
        )
