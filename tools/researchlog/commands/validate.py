"""`researchlog validate` — schema and invariant check across the canonical state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from researchlog import constraints, repo, schema, state
from researchlog.errors import (
    EXIT_OK,
    Finding,
    PreconditionMissing,
    Result,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    StateInvalid,
)

NAME = "validate"
HELP = "check schemas and invariants across the canonical research state"

KINDS = ("active", "evidence", "manifest", "findings-entry")


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    parser.add_argument(
        "--print-schema",
        choices=KINDS,
        default=None,
        help="print a packaged schema and exit; writes nothing",
    )


def run(args: argparse.Namespace) -> Result:
    if args.print_schema:
        return _print_schema(args.print_schema)

    paths = repo.require(args.root)
    result = Result(payload={"root": str(paths.root)})

    active, recovery = state.load_active_with_findings(paths)
    for finding in recovery:
        result.add(finding)
    for finding in schema.load_validator("active").check(active.raw):
        result.add(finding)
    for finding in schema.version_findings("active", active.raw, where="ACTIVE.json"):
        result.add(finding)

    ledger = state.load_ledger(paths)
    for finding in ledger.unreadable:
        result.add(finding)
    for finding in state.unreadable_warning(ledger, "ledger"):
        result.add(finding)

    result.payload["evidence_records"] = len(ledger.records)
    result.payload["findings_entries"] = len(ledger.findings_entries)
    result.payload["manifests"] = len(ledger.manifests)

    _check_evidence(paths, ledger, result)
    _check_findings(ledger, result)
    _check_manifests(ledger, result)
    _check_block(active, ledger, result)
    _check_signals(paths, result)

    if args.strict:
        _promote_warnings(result)
    return result


def _check_evidence(paths: repo.ResearchPaths, ledger: state.Ledger, result: Result) -> None:
    validator = schema.load_validator("evidence")
    # The declared hypotheses are the only registry V0 has, and they are the same set the
    # block covers. This used to pass `sorted(ledger.records)` — the evidence IDs — as
    # `known_hypotheses`, which made UNKNOWN_HYPOTHESIS fire on every record that named a
    # hypothesis at all, since an H-* is never an EV-*. A check whose registry is the wrong
    # ID space does not report a fact about the record; it reports that it was wired wrong.
    allowed = sorted(active_hypotheses(paths))
    for evidence_id, record in sorted(ledger.records.items()):
        for finding in validator.check(record):
            result.add(finding)
        for finding in constraints.check_evidence(
            record,
            known_hypotheses=allowed or None,
            allowed_hypotheses=allowed or None,
        ):
            result.add(finding)
        for finding in schema.version_findings("evidence", record, where=evidence_id):
            result.add(finding)
        evidence_path = paths.evidence(evidence_id)
        if not evidence_path.is_file():
            result.add(
                Finding(
                    "EVIDENCE_SHARD_MISSING",
                    SEVERITY_ERROR,
                    evidence_id,
                    f"record is present in memory but {evidence_path.name} is absent",
                )
            )


def _check_findings(ledger: state.Ledger, result: Result) -> None:
    validator = schema.load_validator("findings-entry")
    levels = ledger.evidence_levels()
    for entry in ledger.findings_entries:
        for finding in validator.check(entry):
            result.add(finding)
        for finding in constraints.check_finding(entry, evidence_levels=levels):
            result.add(finding)
        for finding in schema.version_findings("findings-entry", entry, where=str(entry.get("id") or "?")):
            result.add(finding)


def _check_manifests(ledger: state.Ledger, result: Result) -> None:
    """The fourth kind.

    `validate` offers `--print-schema manifest` and never checked a manifest against it:
    `_load_manifests` catches a parse error and says nothing about a document that parses
    while violating its own schema. A manifest is the run's identity, so an unvalidated one
    is exactly the kind of thing that quietly misleads every detector downstream.
    """
    validator = schema.load_validator("manifest")
    for experiment_id, manifest in sorted(ledger.manifests.items()):
        for finding in validator.check(manifest):
            result.add(finding)
        for finding in schema.version_findings("manifest", manifest, where=experiment_id):
            result.add(finding)


def _check_signals(paths: repo.ResearchPaths, result: Result) -> None:
    """Signals have no schema, so their invariants are checked here instead."""
    try:
        signals = _signals(paths)
    except StateInvalid as exc:
        for finding in exc.findings:
            result.add(finding)
        return
    for signal in signals:
        for finding in constraints.check_signal(signal):
            result.add(finding)


def _check_block(active: object, ledger: state.Ledger, result: Result) -> None:
    block = active.get("block")  # type: ignore[attr-defined]
    if not isinstance(block, dict):
        return
    members = constraints.block_members(active.raw, list(ledger.records.values()))  # type: ignore[attr-defined]
    for finding in constraints.check_block_contract(block, member_records=members):
        result.add(finding)


def _signals(paths: repo.ResearchPaths) -> list[dict]:
    """The `research:signal` blocks in ARCHITECT.md.

    A malformed block raises `StateInvalid` rather than returning an empty list. The
    alternative was the state this replaced: a signal file that cannot be parsed made
    every signal check quietly pass, because the check that reads it was the only thing
    that noticed, and it reported nothing.
    """
    if not paths.architect.is_file():
        return []
    return schema.extract_blocks(paths.architect.read_text(encoding="utf-8")).get("signal", [])


def active_hypotheses(paths: repo.ResearchPaths) -> list[str]:
    try:
        active = state.load_active(paths)
    except Exception:  # noqa: BLE001 - validation must not fail on a broken ACTIVE
        return []
    return [str(h) for h in (active.get("hypothesis_ids") or [])]


def _print_schema(kind: str) -> Result:
    path = schema.schema_dir() / f"{kind}.schema.json"
    if not path.is_file():
        raise PreconditionMissing("SCHEMA_ABSENT", f"no packaged schema at {path}")
    document = json.loads(path.read_text(encoding="utf-8"))
    return Result(exit_code=EXIT_OK, payload={"kind": kind, "schema": document})


def _promote_warnings(result: Result) -> None:
    promoted = [
        Finding(f.code, SEVERITY_ERROR, f.subject, f.message, f.fix_hint)
        for f in result.findings
        if f.severity == SEVERITY_WARNING
    ]
    if promoted:
        result.findings = [f for f in result.findings if f.severity != SEVERITY_WARNING] + promoted
        result.exit_code = max(result.exit_code, 2)
