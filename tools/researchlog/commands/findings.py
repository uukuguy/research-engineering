"""`researchlog findings` — the only writer of FINDINGS.md.

FINDINGS.md holds a `research:findings` block that is the source of truth, and prose
above it that is regenerated from that block. The design only works while the agent is
not a writer: the moment the block can be edited by hand as well, the block and the prose
drift apart and neither is canonical. So every mutation lives here, and `render` is the
one that repairs drift rather than causing it.

Belief changes are explicit verbs, never a side effect:

* `supersede` — a finding we believed has been replaced. Requires the replacement and a
  reason, because a belief that quietly disappears makes the false-confidence rate
  uncomputable.
* `demote` — weaken a status with the reason recorded.
* `env query` never demotes anything. Confidence is a belief, and a belief changes
  through a belief-changing command, not through an environment scan.

`max_evidence_level` is derived from the cited records. A value supplied by the caller is
rejected when it disagrees; a stale value already in the file is recomputed, because that
is the field's whole purpose.
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from researchlog import constraints, ids, repo, schema, state
from researchlog.errors import (
    Finding,
    PreconditionMissing,
    Result,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    StateInvalid,
)

NAME = "findings"
HELP = "durable beliefs: add, update, supersede, demote, render"

STATUSES: tuple[str, ...] = ("Established", "Provisional", "Refuted", "Superseded", "Open")
CONFIDENCES: tuple[str, ...] = ("low", "moderate", "high", "certain")

BEGIN_MARKER = "<!-- researchlog:findings:begin -->"
END_MARKER = "<!-- researchlog:findings:end -->"
_FENCE = re.compile(r"^```json[ \t]+research:findings[ \t]*$")

RESERVATION_DIR = "id-reservations"


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=None)
    actions = parser.add_subparsers(dest="action", required=True, metavar="ACTION")

    add = actions.add_parser("add", help="record a new durable belief")
    add.add_argument("--title", required=True)
    add.add_argument("--status", choices=STATUSES, required=True)
    add.add_argument("--confidence", choices=CONFIDENCES, required=True)
    add.add_argument("--evidence", required=True, metavar="EV-a,EV-b")
    add.add_argument("--implication", default=None)
    add.add_argument("--limitation", default=None)
    add.add_argument(
        "--max-evidence-level",
        choices=constraints.EVIDENCE_LEVELS,
        default=None,
        help="rejected when it disagrees with the level the cited evidence reaches",
    )

    update = actions.add_parser("update", help="change status, confidence or citations")
    update.add_argument("--id", required=True)
    update.add_argument("--status", choices=STATUSES, default=None)
    update.add_argument("--confidence", choices=CONFIDENCES, default=None)
    update.add_argument("--add-evidence", default=None, metavar="EV-a,EV-b")
    update.add_argument(
        "--max-evidence-level",
        choices=constraints.EVIDENCE_LEVELS,
        default=None,
        help="rejected when it disagrees with the level the cited evidence reaches",
    )

    supersede = actions.add_parser("supersede", help="replace a belief with another")
    supersede.add_argument("--id", required=True)
    supersede.add_argument("--by", required=True)
    supersede.add_argument("--reason", required=True)

    demote = actions.add_parser("demote", help="weaken a belief, recording why")
    demote.add_argument("--id", required=True)
    demote.add_argument("--to", choices=STATUSES, required=True)
    demote.add_argument("--reason", required=True)

    render = actions.add_parser("render", help="regenerate the prose from the block")
    render.add_argument("--check", action="store_true", help="report drift; writes nothing")

    for action in (add, update, supersede, demote, render):
        _accept_shared_flags(action)


def _accept_shared_flags(action: argparse.ArgumentParser) -> None:
    """Let the global flags appear after the action too, as `findings add ... --json`."""
    action.add_argument("--root", type=Path, default=argparse.SUPPRESS)
    action.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    action.add_argument("--quiet", action="store_true", default=argparse.SUPPRESS)


def run(args: argparse.Namespace) -> Result:
    paths = repo.require(args.root)
    text = _read(paths)
    block = schema.require_block(text, "findings", source=paths.findings.name)
    entries = [entry for entry in (block.get("entries") or []) if isinstance(entry, dict)]

    if args.action == "render":
        return _render(paths, text, block, entries, check=args.check)

    levels = state.load_ledger(paths).evidence_levels()
    changed = _mutate(entries, args, levels, paths)
    block["entries"] = entries
    warnings = _validate(entries, levels, changed)
    return _commit(paths, text, block, entries, changed, warnings)


def _read(paths: repo.ResearchPaths) -> str:
    try:
        return paths.findings.read_text(encoding="utf-8")
    except OSError as exc:
        raise PreconditionMissing(
            "FINDINGS_UNREADABLE",
            f"cannot read {paths.findings}: {exc}",
            "run `researchlog init --merge` to restore a missing canonical file",
        ) from exc


def _mutate(
    entries: list[dict[str, Any]],
    args: argparse.Namespace,
    levels: dict[str, str],
    paths: repo.ResearchPaths,
) -> set[str]:
    if args.action == "add":
        return {_add(entries, args, levels, paths)}
    entry = _require_entry(entries, args.id)
    if args.action == "update":
        return {_update(entry, args, levels)}
    if args.action == "supersede":
        return {_supersede(entry, args, entries)}
    if args.action == "demote":
        return {_demote(entry, args)}
    raise StateInvalid(f"unknown action {args.action!r}")  # pragma: no cover - argparse guards


def _add(
    entries: list[dict[str, Any]],
    args: argparse.Namespace,
    levels: dict[str, str],
    paths: repo.ResearchPaths,
) -> str:
    finding_id, _ = ids.claim_new("finding", lambda fid: paths.derived / RESERVATION_DIR / fid)
    entry: dict[str, Any] = {
        "id": finding_id,
        "title": args.title,
        "status": args.status,
        "confidence": args.confidence,
        "evidence": _split(args.evidence),
        "implication": args.implication,
        "limitation": args.limitation,
        "created_at": _now(),
        "updated_at": _now(),
    }
    entries.append(entry)
    _derive_level(entry, levels, args.max_evidence_level)
    return finding_id


def _update(entry: dict[str, Any], args: argparse.Namespace, levels: dict[str, str]) -> str:
    if args.add_evidence:
        cited = [str(ev) for ev in entry.get("evidence") or []]
        entry["evidence"] = cited + [ev for ev in _split(args.add_evidence) if ev not in cited]
    if args.status is not None:
        entry["status"] = args.status
    if args.confidence is not None:
        entry["confidence"] = args.confidence
    entry["updated_at"] = _now()
    _derive_level(entry, levels, args.max_evidence_level)
    return str(entry["id"])


def _supersede(
    entry: dict[str, Any], args: argparse.Namespace, entries: list[dict[str, Any]]
) -> str:
    if args.by not in {str(other.get("id")) for other in entries}:
        raise StateInvalid(
            [
                Finding(
                    "FINDING_REPLACEMENT_UNKNOWN",
                    SEVERITY_ERROR,
                    args.by,
                    f"{args.id} cannot be superseded by a finding that does not exist",
                    "a Superseded entry must point at a real replacement, or the belief graph "
                    "has a dangling edge",
                )
            ]
        )
    entry["status"] = "Superseded"
    entry["superseded_by"] = args.by
    entry["reason"] = args.reason
    entry["updated_at"] = _now()
    return str(entry["id"])


def _demote(entry: dict[str, Any], args: argparse.Namespace) -> str:
    entry["status"] = args.to
    entry["reason"] = args.reason
    entry["updated_at"] = _now()
    return str(entry["id"])


def _derive_level(entry: dict[str, Any], levels: dict[str, str], supplied: str | None) -> None:
    cited = [str(ev) for ev in entry.get("evidence") or []]
    derived = constraints.highest_level(cited, levels)
    if derived is None:
        raise StateInvalid(
            [
                Finding(
                    "FINDING_WITHOUT_DERIVABLE_LEVEL",
                    SEVERITY_ERROR,
                    str(entry.get("id", "?")),
                    f"none of the cited evidence exists in the ledger: {', '.join(cited) or '(none)'}",
                    "max_evidence_level is derived from real records, and a belief that cites "
                    "no real evidence cannot claim one",
                )
            ]
        )
    if supplied is not None and supplied != derived:
        raise StateInvalid(
            [
                Finding(
                    "FINDING_LEVEL_MISMATCH",
                    SEVERITY_ERROR,
                    str(entry.get("id", "?")),
                    f"--max-evidence-level {supplied} was supplied but its evidence reaches {derived}",
                    f"this field is derived; set it to {derived} or omit it",
                )
            ]
        )
    entry["max_evidence_level"] = derived


def _validate(
    entries: list[dict[str, Any]], levels: dict[str, str], changed: set[str]
) -> list[Finding]:
    validator = schema.load_validator("findings-entry")
    findings: list[Finding] = []
    for entry in entries:
        if str(entry.get("id")) not in changed:
            continue
        findings.extend(validator.check(entry))
        findings.extend(constraints.check_finding(entry, evidence_levels=levels))
    errors = [f for f in findings if f.severity == SEVERITY_ERROR]
    if errors:
        raise StateInvalid(errors)
    return findings


def _commit(
    paths: repo.ResearchPaths,
    text: str,
    block: dict[str, Any],
    entries: list[dict[str, Any]],
    changed: set[str],
    warnings: list[Finding],
) -> Result:
    schema.require_writable("findings-entry", paths.findings, block)
    updated = _with_section(schema.replace_block(text, "findings", block), entries)
    paths.findings.write_text(updated, encoding="utf-8")
    result = Result(
        payload={"changed": sorted(changed), "entries": len(entries), "drift": True},
        human=f"FINDINGS.md: {', '.join(sorted(changed))}",
    )
    for finding in warnings:
        result.add(finding)
    return result


def _render(
    paths: repo.ResearchPaths,
    text: str,
    block: dict[str, Any],
    entries: list[dict[str, Any]],
    *,
    check: bool,
) -> Result:
    expected = _with_section(text, entries)
    drift = expected != text
    if check:
        result = Result(payload={"drift": drift, "checked": True})
        if drift:
            result.add(
                Finding(
                    "FINDINGS_RENDER_DRIFT",
                    SEVERITY_WARNING,
                    "FINDINGS.md",
                    "the prose and the research:findings block disagree",
                    "run `researchlog findings render` to regenerate the prose from the block",
                )
            )
            result.human = "FINDINGS.md: drift"
        else:
            result.human = "FINDINGS.md: prose matches the block"
        return result
    if drift:
        schema.require_writable("findings-entry", paths.findings, block)
        paths.findings.write_text(expected, encoding="utf-8")
    return Result(
        payload={"drift": drift, "written": drift},
        human=f"FINDINGS.md: {'regenerated' if drift else 'already current'}",
    )


def _with_section(text: str, entries: list[dict[str, Any]]) -> str:
    lines = text.splitlines()
    section = _section(entries)
    begin, end = _marker(lines, BEGIN_MARKER), _marker(lines, END_MARKER)
    if begin is None and end is None:
        fence = next((i for i, line in enumerate(lines) if _FENCE.match(line)), None)
        if fence is None:
            raise StateInvalid("FINDINGS.md has no research:findings fence to anchor the prose to")
        return "\n".join([*lines[:fence], *section, *lines[fence:]]) + "\n"
    if begin is None or end is None or end < begin:
        raise StateInvalid(
            [
                Finding(
                    "FINDINGS_RENDER_MARKER_DAMAGED",
                    SEVERITY_ERROR,
                    "FINDINGS.md",
                    "one of the generated-prose markers is missing or out of order",
                    f"restore both {BEGIN_MARKER} and {END_MARKER}, or delete both and re-run render",
                )
            ]
        )
    return "\n".join([*lines[:begin], *section, *lines[end + 1 :]]) + "\n"


def _section(entries: list[dict[str, Any]]) -> list[str]:
    lines = [BEGIN_MARKER, "", "## Findings", ""]
    if not entries:
        lines.append("No durable beliefs recorded yet.")
    for entry in entries:
        lines.extend(_entry_lines(entry))
    lines.extend(["", END_MARKER])
    return lines


def _entry_lines(entry: dict[str, Any]) -> list[str]:
    lines = [
        f"### {entry.get('id')} — {entry.get('title')}",
        "",
        f"- status: `{entry.get('status')}` · confidence: `{entry.get('confidence')}` · "
        f"max evidence level: `{entry.get('max_evidence_level')}`",
        f"- evidence: {_cited(entry)}",
    ]
    if entry.get("implication"):
        lines.append(f"- implication: {entry['implication']}")
    if entry.get("limitation"):
        lines.append(f"- limitation: {entry['limitation']}")
    if entry.get("superseded_by"):
        lines.append(
            f"- superseded by: `{entry['superseded_by']}` — {entry.get('reason') or ''}".rstrip()
        )
    lines.append("")
    return lines


def _cited(entry: dict[str, Any]) -> str:
    cited = [f"`{ev}`" for ev in entry.get("evidence") or []]
    return ", ".join(cited) if cited else "(none)"


def _require_entry(entries: list[dict[str, Any]], identifier: str) -> dict[str, Any]:
    for entry in entries:
        if entry.get("id") == identifier:
            return entry
    raise PreconditionMissing(
        "FINDING_NOT_FOUND",
        f"no entry {identifier} in FINDINGS.md",
        "run `researchlog findings render` then read the block, or `validate` to check the file",
    )


def _marker(lines: list[str], marker: str) -> int | None:
    return next((index for index, line in enumerate(lines) if line.strip() == marker), None)


def _split(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
