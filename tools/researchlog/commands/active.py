"""`researchlog active` — one crash-safe read-modify-write of ACTIVE.json.

ACTIVE.json is the execution pointer a new session resumes from, so it is rewritten far
more often than any other canonical file and is the one whose corruption costs the most.
Every mutation here goes through `ioutil.write_json_atomic`, which means a crash leaves
either the old file or the new one and never a truncated pointer.

Two rules shape the rest:

* **Unknown fields survive.** The document is loaded into a `Record` and written back as
  `record.raw`; nothing is reconstructed from typed fields, so a field this version does
  not know about is still there afterwards.
* **A newer schema is never overwritten.** `schema.require_writable` runs before the
  first mutation, so a refusal leaves the file byte-identical rather than half-updated.

Reading and writing are deliberately not combined in one invocation: `--get` with a
mutation would make "what did I just change" and "what is there now" the same answer.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from researchlog import constraints, ids, ioutil, repo, schema, state
from researchlog.errors import (
    Finding,
    RefusedByPolicy,
    Result,
    SEVERITY_ERROR,
    StateInvalid,
)
from researchlog.model import Record

NAME = "active"
HELP = "read or crash-safely update ACTIVE.json"

_MISSING = object()


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--get", metavar="FIELD", default=None, help="read one dotted field; writes nothing"
    )
    parser.add_argument(
        "--get-json", action="store_true", help="read the whole document; writes nothing"
    )
    parser.add_argument("--set-status", metavar="STATUS", default=None)
    parser.add_argument(
        "--set",
        dest="assignments",
        action="append",
        default=[],
        metavar="FIELD=VALUE",
        help="set a dotted field; the value is JSON when it parses, a string otherwise",
    )
    parser.add_argument("--set-next-action", metavar="TEXT", default=None)
    parser.add_argument("--set-observation", metavar="TEXT", default=None)
    parser.add_argument(
        "--close-block", action="store_true", help="close the block; requires --belief-delta"
    )
    parser.add_argument("--belief-delta", choices=sorted(constraints.BELIEF_DELTAS), default=None)
    parser.add_argument(
        "--accept-recovery", action="store_true", help="acknowledge a recovered state"
    )
    parser.add_argument("--rotate-session", action="store_true", help="mint a new session_epoch")
    parser.add_argument("--refresh-counts", action="store_true",
                        help="refresh ledger-derived block counts without closing or changing belief")
    parser.add_argument(
        "--show", action="store_true", help="emit the whole document; writes nothing"
    )


def run(args: argparse.Namespace) -> Result:
    paths = repo.require(args.root)
    record, recovery = state.load_active_with_findings(paths)
    result = Result(payload={"path": str(paths.active)})
    for finding in recovery:
        result.add(finding)

    writing = _is_writing(args)
    if writing and (args.get is not None or args.get_json or args.show):
        raise RefusedByPolicy(
            "ACTIVE_READ_WITH_WRITE",
            "reading and writing ACTIVE.json in one call would make the reported value ambiguous",
            "run the read first, then the write as a separate command",
        )

    if writing:
        schema.require_writable("active", paths.active, record.raw)
        # Closing or explicitly refreshing counts needs the ledger; ordinary writes do not.
        members: list[Mapping[str, Any]] = []
        if args.belief_delta is not None or args.refresh_counts:
            members = constraints.block_members(
                record.get("block.id"), list(state.load_ledger(paths).records.values())
            )
        changed = _apply(paths, record, args, members=members)
        record.set("updated_at", _now())
        ioutil.write_json_atomic(
            paths.active, record.raw, validator=schema.load_validator("active")
        )
        result.payload["changed"] = changed
        result.human = f"ACTIVE.json updated: {', '.join(changed)}"

    return _report(record, args, result)


def _is_writing(args: argparse.Namespace) -> bool:
    return any(
        (
            args.set_status is not None,
            bool(args.assignments),
            args.set_next_action is not None,
            args.set_observation is not None,
            args.close_block,
            args.belief_delta is not None,
            args.accept_recovery,
            args.rotate_session,
            args.refresh_counts,
        )
    )


def _apply(
    paths: repo.ResearchPaths,
    record: Record,
    args: argparse.Namespace,
    *,
    members: Sequence[Mapping[str, Any]] = (),
) -> list[str]:
    from researchlog import delegation
    pending_workers = [w for w in delegation.load(paths) if w['status'] in delegation.OPEN]
    changing_block = any(
        _parse_assignment(expression)[0] in ('block', 'block.id', 'block.belief_delta')
        for expression in args.assignments)
    if pending_workers and (args.close_block or changing_block or args.belief_delta is not None):
        raise StateInvalid('Review/close outstanding worker packets before closing or replacing the research block')
    if args.close_block and args.belief_delta is None:
        raise StateInvalid(
            [
                Finding(
                    "BLOCK_CLOSE_NEEDS_DELTA",
                    SEVERITY_ERROR,
                    str(record.get("block.id") or "block"),
                    "--close-block requires --belief-delta",
                    "belief_delta is written once, at close, as none, refined or overturned; "
                    "a block whose members changed belief cannot close as 'none'",
                )
            ]
        )

    now = _now()
    changed: list[str] = []

    if args.set_status is not None:
        record.set("status", args.set_status)
        changed.append("status")
    for expression in args.assignments:
        field, value = _parse_assignment(expression)
        if field == "hypothesis_ids" and isinstance(value, list):
            # This field is also the validator's project hypothesis registry.
            # Selecting a new question must not unregister IDs used by immutable
            # evidence. chosen_hypothesis identifies the current focus.
            # Leave malformed lists to schema validation rather than normalizing them.
            previous = record.get("hypothesis_ids") or []
            if all(isinstance(item, str) for item in [*previous, *value]):
                value = list(dict.fromkeys([*previous, *value]))
        if field == "block.id" and value != record.get("block.id"):
            # Opening a block resets its summary. `belief_delta` and the derived count
            # describe the block that just ended; carrying them into the next one is how a
            # new block inherits work it did not do — the count would start where the last
            # block finished and the budget it is held to would belong to someone else.
            record.set("block.belief_delta", None)
            record.set("block.completed_evidence_iterations", 0)
            record.set("block.reproduction_iterations", 0)
            changed.extend(
                ["block.belief_delta", "block.completed_evidence_iterations",
                 "block.reproduction_iterations"]
            )
        record.set(field, value)
        changed.append(field)
    if args.set_next_action is not None:
        record.set("next_action", args.set_next_action)
        changed.append("next_action")
    if args.set_observation is not None:
        record.set("current_observation", args.set_observation)
        changed.append("current_observation")
    if args.belief_delta is not None:
        record.set("block.belief_delta", args.belief_delta)
        changed.append("block.belief_delta")
    if args.belief_delta is not None or args.refresh_counts:
        # Refreshing progress must not require inventing a block-level belief decision.
        # V1 P2: a separate reproduction bucket is recomputed the same way; the evidence
        # budget check only reads the first of these two.
        record.set("block.completed_evidence_iterations", constraints.count_evidence_iterations(members))
        record.set("block.reproduction_iterations", constraints.count_reproduction_iterations(members))
        changed.extend(["block.completed_evidence_iterations", "block.reproduction_iterations"])
    if args.close_block:
        record.set("status", "idle")
        changed.append("status")
    if args.accept_recovery:
        changed.extend(_accept_recovery(record, now))
    if args.rotate_session:
        new_epoch = ids.mint("session")
        record.set("session_epoch", new_epoch)
        changed.append("session_epoch")
        # V1 Block 2 / T5: append a "rotated" line to the session-event
        # log so the cumulative telemetry KPI has a record. The import
        # is local because the package's __init__.py imports this
        # module; see init.py for the same dance.
        import importlib
        sessions_module = importlib.import_module("researchlog.commands.sessions")
        sessions_module.append_event(
            paths=paths,
            epoch=new_epoch,
            kind="rotated",
            block_id=record.get("block.id"),
        )
    return changed


def _accept_recovery(record: Record, now: str) -> list[str]:
    record.set("execution.status", "idle")
    record.set("execution.recovery_acknowledged_at", now)
    changed = ["execution.status", "execution.recovery_acknowledged_at"]
    if record.get("status") == "interrupted":
        record.set("status", "idle")
        changed.append("status")
    return changed


def _report(record: Record, args: argparse.Namespace, result: Result) -> Result:
    if args.get is not None:
        value = record.get(args.get, _MISSING)
        if value is _MISSING:
            raise StateInvalid(
                [
                    Finding(
                        "ACTIVE_FIELD_MISSING",
                        SEVERITY_ERROR,
                        args.get,
                        f"ACTIVE.json has no field at {args.get!r}",
                        "run `researchlog active --get-json` to see the fields that do exist",
                    )
                ]
            )
        result.payload["field"] = args.get
        result.payload["value"] = value
        if not result.human:
            result.human = (
                value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            )
        return result

    if args.get_json or args.show or not _is_writing(args):
        result.payload["active"] = record.raw
        if not result.human:
            result.human = json.dumps(record.raw, ensure_ascii=False, indent=2)
    return result


def _parse_assignment(expression: str) -> tuple[str, Any]:
    return state.parse_assignment(expression, code="ACTIVE_SET_MALFORMED")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
