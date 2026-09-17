"""`researchlog telemetry` — report §21 productivity KPIs.

V1 Block 2 / T5 expands the `max_tokens` self-report into a small KPI
table. The four KPIs the V1 plan names are:

* `time_to_first_e1` — wall-clock from session start to the first E1
  evidence record.
* `time_to_first_e3` — same, at E3.
* `session_recovery_accuracy` — fraction of session rotations that
  re-established a coherent ACTIVE without reconciler findings.
* `discriminating_experiment_without_architect_correction` — ratio
  of records whose `hypotheses_differentiated` advanced belief to
  records that landed an ARCHITECT `CHALLENGE` signal in the same
  window.

The first two are computable today from the ledger and the ACTIVE
`session_epoch`. The latter two need infrastructure the lab has not
yet installed — a session-event log, and a reader of ARCHITECT.md
signals. The report marks them `unavailable` with the reason, so the
gap is visible rather than silently zero.
"""

from __future__ import annotations

import argparse
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

    rows = [
        _time_to_first(ledger, active_record, target_level="E1"),
        _time_to_first(ledger, active_record, target_level="E3"),
        _unavailable(
            "session_recovery_accuracy",
            "no session-event log: rotations are not currently tracked on disk",
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
    first: dict[str, Any] | None = None
    for record in ledger.records.values():
        if record.get("evidence_level") != target_level:
            continue
        created_at = record.get("created_at")
        if not created_at:
            continue
        if first is None or str(created_at) < str(first.get("created_at", "")):
            first = record
    if first is None or epoch_stamp is None:
        return _unavailable(
            f"time_to_first_{target_level.lower()}",
            f"no {target_level} record yet, or no `created_at` on the first match",
        )
    try:
        first_dt = datetime.fromisoformat(str(first["created_at"]))
    except ValueError:
        return _unavailable(
            f"time_to_first_{target_level.lower()}",
            f"first {target_level} record has a non-ISO created_at",
        )
    delta_seconds = (first_dt - epoch_stamp).total_seconds()
    return {
        "kpi": f"time_to_first_{target_level.lower()}",
        "value": delta_seconds,
        "unit": "seconds",
        "status": "ok",
        "evidence_id": first.get("evidence_id"),
    }


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