"""Research portfolio inside CURRENT; no second evidence or execution store."""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from researchlog.errors import Finding, SEVERITY_ERROR, StateInvalid

STATUSES = ("queued", "active", "parked", "blocked", "completed", "rejected")
TEXT_FIELDS = ("id", "title", "question", "value", "next_probe", "resume_point",
               "status", "reason", "wake_when", "updated_at")
LIST_FIELDS = ("evidence", "depends_on", "alternatives")


def check(block, evidence_ids=None):
    findings = []

    def error(message):
        findings.append(Finding("ROUTES_INVALID", SEVERITY_ERROR, "CURRENT.md", message))

    rows = block.get("research_routes", [])
    if not isinstance(rows, list):
        error("research_routes must be an array")
        return findings
    ids = set()
    for row in rows:
        if not isinstance(row, dict):
            error("route must be an object")
            continue
        if any(not isinstance(row.get(key), str) for key in TEXT_FIELDS):
            error("route text fields missing or malformed")
            continue
        if not re.fullmatch(r"R-[A-Za-z0-9][A-Za-z0-9_-]*", row['id']):
            error("route ID must be R- followed by letters, digits, dash or underscore")
        if row['id'] in ids:
            error("duplicate route ID: " + row['id'])
        ids.add(row['id'])
        if row['status'] not in STATUSES:
            error("unknown route status: " + row['id'])
        if type(row.get('priority')) is not int or row['priority'] < 1:
            error(row['id'] + ': priority must be a positive integer (agent recommendation)')
        for key in ("title", "question", "value", "next_probe", "resume_point", "reason"):
            if not row[key].strip():
                error(f"{row['id']}: {key} must not be empty")
        if row['status'] in ("parked", "blocked") and not row['wake_when'].strip():
            error(row['id'] + ": parked/blocked routes need a wake condition")
        for key in LIST_FIELDS:
            values = row.get(key)
            if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
                error(f"{row['id']}: {key} must be a string array")
        if not isinstance(row.get('history'), list) or not row['history']:
            error(row['id'] + ": missing transition history")
        else:
            for event in row['history']:
                if (not isinstance(event, dict) or
                    any(not isinstance(event.get(k), str) for k in
                        ('at', 'action', 'from', 'to', 'reason', 'next_probe', 'resume_point', 'wake_when')) or
                    not isinstance(event.get('evidence'), list) or
                    any(not isinstance(v, str) for v in event['evidence'])):
                    error(row['id'] + ': malformed transition history')
                    break
            else:
                if row['history'][-1]['to'] != row['status']:
                    error(row['id'] + ': latest transition and status disagree')
    # Stop before traversing malformed entries.
    if findings:
        return findings
    if sum(r['status'] == 'active' for r in rows) > 1:
        error("only one portfolio focus may be active")
    by_id = {r['id']: r for r in rows}
    for row in rows:
        for key in ('depends_on', 'alternatives'):
            for ref in row[key]:
                if ref not in ids or ref == row['id']:
                    error(f"{row['id']}: invalid {key} reference {ref}")
        if set(row['depends_on']) & set(row['alternatives']):
            error(row['id'] + ": a dependency cannot also be an alternative")
        if evidence_ids is not None:
            for ref in row['evidence'] + [ev for h in row['history'] for ev in h['evidence']]:
                if ref not in evidence_ids:
                    error(f"{row['id']}: missing evidence {ref}")
        if row['status'] == 'active':
            for ref in row['depends_on']:
                if ref in by_id and by_id[ref]['status'] != 'completed':
                    error(f"{row['id']}: dependency {ref} not completed")
    visited, stack = set(), set()

    def visit(key):
        if key in stack:
            error("dependency cycle at " + key)
            return
        if key in visited or key not in by_id:
            return
        stack.add(key)
        for ref in by_id[key]['depends_on']:
            visit(ref)
        stack.remove(key)
        visited.add(key)

    for key in ids:
        visit(key)
    return findings


def write_current(path: Path, previous: str, updated: str):
    """Single-writer atomic replacement; detect edits observed since the read.

    This is not a multi-writer transaction or a distributed lock.
    """
    if path.is_symlink():
        raise StateInvalid("Refuse to replace symlinked CURRENT.md")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.current-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(path.stat().st_mode & 0o777)
        if path.read_text(encoding='utf-8') != previous:
            raise StateInvalid("CURRENT changed during update; reread before retry")
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
