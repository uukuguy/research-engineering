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
    _check_block(active, ledger, result)

    if args.strict:
        _promote_warnings(result)
    return result


def _check_evidence(paths: repo.ResearchPaths, ledger: state.Ledger, result: Result) -> None:
    validator = schema.load_validator("evidence")
    known = sorted(ledger.records)
    allowed = set(active_hypotheses(paths))
    for evidence_id, record in sorted(ledger.records.items()):
        for finding in validator.check(record):
            result.add(finding)
        for finding in constraints.check_evidence(
            record,
            known_hypotheses=known if known else None,
            allowed_hypotheses=sorted(allowed) if allowed else None,
        ):
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


def _check_block(active: object, ledger: state.Ledger, result: Result) -> None:
    block = active.get("block")  # type: ignore[attr-defined]
    if not isinstance(block, dict):
        return
    members = _block_members(active, ledger)  # type: ignore[arg-type]
    for finding in constraints.check_block_contract(block, member_records=members):
        result.add(finding)


def _block_members(active: object, ledger: state.Ledger) -> list[dict]:
    hypothesis_ids = set(active.get("hypothesis_ids") or [])  # type: ignore[attr-defined]
    if not hypothesis_ids:
        return list(ledger.records.values())
    return [
        record
        for record in ledger.records.values()
        if hypothesis_ids & set(record.get("hypothesis_ids") or [])
    ]


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
