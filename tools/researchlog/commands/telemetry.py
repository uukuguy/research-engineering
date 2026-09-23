"""`researchlog telemetry` — report §21 productivity KPIs.

V1 Block 2 / T5 expands the `max_tokens` self-report into a small KPI
table. The five KPIs the V1 plan names today:

* `time_to_first_e1` — wall-clock from session start to the first E1
  evidence record.
* `time_to_first_e3` — same, at E3.
* `cumulative_evidence_iterations` — total belief-changing iterations
  across all sessions recorded in `research/sessions.jsonl`. Computable
  since V1 Block 2 / T5 landed the session-event log; was previously
  `session_recovery_accuracy` placeholder.
* `session_recovery_accuracy` — fraction of session rotations that
  re-established a coherent ACTIVE without reconciler findings.
* `discriminating_experiment_without_architect_correction` — ratio
  of records whose `hypotheses_differentiated` advanced belief to
  records that landed an ARCHITECT `CHALLENGE` signal in the same
  window.

The first three are computable today from the ledger + ACTIVE +
`sessions.jsonl`. The latter two need infrastructure the lab has not
yet installed — a session-recovery ledger, and a reader of
ARCHITECT.md signals. The report marks unavailable rows with the reason,
so the gap is visible rather than silently zero.
"""

from __future__ import annotations

import argparse
import importlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from researchlog import repo, state
from researchlog.errors import Finding, Result, SEVERITY_WARNING

NAME = "telemetry"
HELP = "report the §21 productivity KPI table for the current block"


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--report",
        action="store_true",
        help="emit the KPI table as a JSON envelope (default behaviour)",
    )


def run(args: argparse.Namespace) -> Result:
    paths = repo.require(args.root)
    ledger = state.load_ledger(paths)
    active_record = state.load_active(paths)
    # Local import to avoid pulling `commands.__init__` into telemetry's
    # import graph; see init.py / active.py for the same dance.
    sessions_module = importlib.import_module("researchlog.commands.sessions")
    events = sessions_module.read_events(paths)

    rows = [
        _time_to_first(ledger, active_record, target_level="E1"),
        _time_to_first(ledger, active_record, target_level="E3"),
        _cumulative_evidence_iterations(ledger, events),
        _unavailable(
            "session_recovery_accuracy",
            "no session-recovery ledger: rotations are not currently classified by outcome",
        ),
        _unavailable(
            "discriminating_experiment_without_architect_correction",
            "ARCHITECT.md signals are not yet read into telemetry",
        ),
    ]

    result = Result(
        payload={
            "kpis": rows,
            "block_id": active_record.get("block.id"),
            "session_epoch": active_record.get("session_epoch"),
            "evidence_records": len(ledger.records),
            "manifests": len(ledger.manifests),
            "session_events": len(events),
        },
        human=_human(rows),
    )
    for row in rows:
        if row.get("status") == "unavailable":
            result.add(
                Finding(
                    "TELEMETRY_KPI_UNAVAILABLE",
                    SEVERITY_WARNING,
                    row["kpi"],
                    row["reason"],
                    f"install the prerequisite for {row['kpi']} before relying on this row",
                )
            )
    return result


def _time_to_first(
    ledger: state.Ledger, active: state.Record, *, target_level: str
) -> dict[str, Any]:
    """Find the first record at `target_level` and time it against the
    session epoch.

    `session_epoch` is an id minted on rotation, not a timestamp; the
    closest available anchor is the ledger entry's `created_at`. The
    row reports the gap as `null` when either side is missing rather
    than computing a misleading zero.
    """
    epoch_id = active.get("session_epoch")
    if not epoch_id:
        return _unavailable(
            f"time_to_first_{target_level.lower()}",
            "no session_epoch on ACTIVE; rotate the session at least once before measuring",
        )
    epoch_stamp = _id_to_epoch(epoch_id)
    if epoch_stamp is None:
        return _unavailable(f"time_to_first_{target_level.lower()}", "session_epoch has no valid timestamp")
    first: dict[str, Any] | None = None
    first_dt: datetime | None = None
    for record in ledger.records.values():
        if record.get("evidence_level") != target_level:
            continue
        if record.get("session_epoch") not in (None, epoch_id):
            continue
        created_at = record.get("created_at")
        if not created_at:
            continue
        try:
            recorded_at = datetime.fromisoformat(str(created_at))
        except ValueError:
            continue
        if recorded_at.tzinfo is None:
            recorded_at = recorded_at.replace(tzinfo=timezone.utc)
        # A previous session's evidence cannot have a negative time-to-first in
        # this session. Compare parsed instants, not differently offset strings.
        if recorded_at < epoch_stamp:
            continue
        if first_dt is None or recorded_at < first_dt:
            first, first_dt = record, recorded_at
    if first is None or first_dt is None:
        return _unavailable(
            f"time_to_first_{target_level.lower()}",
            f"no {target_level} record with a valid created_at in the current session",
        )
    delta_seconds = (first_dt - epoch_stamp).total_seconds()
    return {
        "kpi": f"time_to_first_{target_level.lower()}",
        "value": delta_seconds,
        "unit": "seconds",
        "status": "ok",
        "evidence_id": first.get("evidence_id"),
    }


def _cumulative_evidence_iterations(
    ledger: state.Ledger, events: list[dict[str, Any]]
) -> dict[str, Any]:
    """Total belief-changing iterations across all sessions recorded in
    `research/sessions.jsonl`.

    A "belief-changing iteration" is a record for which
    `derive_counts_as_evidence_iteration` returns True: completed
    execution, a counted outcome, and either differentiated hypotheses
    or a non-`none` belief_delta. New records carry their recording session ID;
    legacy records fall back to `created_at` in the session's time window.
    IDs disambiguate two sessions starting within the same clock second.

    Returns `unavailable` when the log is absent (e.g. a repo that
    pre-dates V1 Block 2 / T5 was rebase-merged) or empty.
    """
    if not events:
        return _unavailable(
            "cumulative_evidence_iterations",
            "no session-event log: cumulative KPI needs research/sessions.jsonl "
            "(re-run `researchlog init --merge` on a pre-T5 repo to seed it)",
        )
    # Build session boundaries. events are chronological by append order.
    bounds: list[tuple[datetime, datetime | None]] = []
    for i, event in enumerate(events):
        try:
            start = datetime.fromisoformat(str(event["started_at"]))
        except (KeyError, ValueError):
            return _unavailable(
                "cumulative_evidence_iterations",
                f"session-event line {i} has a malformed started_at",
            )
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        end: datetime | None = None
        if i + 1 < len(events):
            try:
                end = datetime.fromisoformat(str(events[i + 1]["started_at"]))
            except (KeyError, ValueError):
                return _unavailable(
                    "cumulative_evidence_iterations",
                    f"session-event line {i + 1} has a malformed started_at",
                )
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
        bounds.append((start, end))

    def in_window(start: datetime, end: datetime | None, created_at: datetime) -> bool:
        if created_at < start:
            return False
        if end is not None and created_at >= end:
            return False
        return True

    def parse_when(value: str | None) -> datetime | None:
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    total = 0
    per_session: list[dict[str, Any]] = []
    for session_epoch, (start, end) in zip(
        [e.get("session_epoch") for e in events], bounds
    ):
        session_count = 0
        for record in ledger.records.values():
            if not _is_counted_iteration(record):
                continue
            if record.get("session_epoch") is not None:
                session_count += int(record["session_epoch"] == session_epoch)
                continue
            created_at_raw = record.get("created_at")
            created_at = parse_when(created_at_raw) if created_at_raw else None
            if created_at is None:
                continue
            if not in_window(start, end, created_at):
                continue
            session_count += 1
        per_session.append(
            {
                "session_epoch": session_epoch,
                "started_at": start.isoformat(),
                "iterations": session_count,
            }
        )
        total += session_count

    return {
        "kpi": "cumulative_evidence_iterations",
        "value": total,
        "unit": "iterations",
        "status": "ok",
        "per_session": per_session,
    }


def _is_counted_iteration(record: dict[str, Any]) -> bool:
    """Inline copy of `constraints.derive_counts_as_evidence_iteration` so
    telemetry does not import `commands.constraints` (which would force
    the constraints module to load every records' schema)."""
    if record.get("iteration_kind") == "reproduction":
        return False
    if record.get("execution_status") != "completed":
        return False
    if record.get("research_outcome") not in {"confirmed", "refuted", "inconclusive", "informative_failure", "promising"}:
        return False
    differentiated = record.get("hypotheses_differentiated") or []
    return bool(differentiated) or record.get("belief_delta", "none") != "none"


def _unavailable(kpi: str, reason: str) -> dict[str, Any]:
    return {"kpi": kpi, "value": None, "unit": None, "status": "unavailable", "reason": reason}


def _id_to_epoch(epoch_id: str) -> datetime | None:
    """Best-effort: an id that matches the mint format encodes
    `YYYYMMDDTHHMMSSZ` after the kind prefix.

    Falls back to `None` for hand-written ids; the caller reports
    `unavailable` rather than a wrong zero.
    """
    # The mint format is `<KIND>-YYYYMMDDTHHMMSSZ-<hex>`. Strip the kind
    # prefix and the suffix to land on the timestamp.
    parts = epoch_id.split("-", 2)
    if len(parts) < 3:
        return None
    stamp = parts[1]
    try:
        return datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _human(rows: list[dict[str, Any]]) -> str:
    lines = ["§21 KPI report:"]
    for row in rows:
        if row.get("status") == "ok":
            lines.append(f"- {row['kpi']}: {row['value']} {row['unit']}")
        else:
            lines.append(f"- {row['kpi']}: unavailable ({row.get('reason')})")
    return "\n".join(lines)
