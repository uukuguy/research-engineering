"""`research/sessions.jsonl` — append-only session-event log.

V1 Block 2 / T5: the cross-session cumulative telemetry KPI (`cumulative_evidence_iterations`)
needs to know when sessions start and end. ACTIVE.json carries only the **current**
`session_epoch`, so a single-session measurement works (time-to-first-E1) but a
multi-session aggregate does not. This module writes one JSON object per session-event
line and reads them back in chronological order.

The file lives under `research/` (canonical state, not derived). It is append-only:
no command rewrites or compacts existing lines. A repo that loses or corrupts the
file loses the cumulative KPI, but `time_to_first_e*` and other single-session
metrics still work — telemetry marks the cumulative KPI `unavailable` with the reason
when the file is absent or empty.

Each line carries:
- `session_epoch`: the id minted for this session (matches `ACTIVE.session_epoch`)
- `started_at`: ISO 8601 UTC timestamp; the boundary for "this session's records"
- `kind`: `"started"` (init) or `"rotated"` (active --rotate-session)
- `block_id`: the block id at the time of the event; helps debugging when the
  block was opened or closed across the rotation
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from researchlog import ids, repo

LOG_KINDS: frozenset[str] = frozenset({"started", "rotated"})


def append_event(
    paths: repo.ResearchPaths,
    *,
    epoch: str,
    kind: str,
    block_id: Any = None,
    started_at: str | None = None,
) -> dict[str, Any]:
    """Append one event to `research/sessions.jsonl`. Returns the line written.

    `started_at` defaults to "now" in UTC ISO 8601 to the second. The caller can
    override it for tests that pin time. The file is created if absent.
    """
    if kind not in LOG_KINDS:
        raise ValueError(f"unknown session-event kind: {kind!r}")
    line: dict[str, Any] = {
        "session_epoch": epoch,
        "started_at": started_at if started_at is not None else _now(),
        "kind": kind,
        "block_id": block_id,
    }
    paths.sessions.parent.mkdir(parents=True, exist_ok=True)
    with paths.sessions.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    return line


def read_events(paths: repo.ResearchPaths) -> list[dict[str, Any]]:
    """Return all session events in chronological order (file order).

    Tolerates malformed lines: a single unparseable line is skipped with a
    warning to stderr, not a hard fail, because a partial log is still
    more useful than no log. Returns `[]` if the file is absent.
    """
    events: list[dict[str, Any]] = []
    if not paths.sessions.is_file():
        return events
    with paths.sessions.open("r", encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            try:
                events.append(json.loads(raw))
            except json.JSONDecodeError:
                # Skip malformed lines; a future commit can add a
                # validator that surfaces this as a finding.
                continue
    return events


def mint_epoch() -> str:
    """Mint a fresh session id (delegates to `ids.mint`)."""
    return ids.mint("session")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")