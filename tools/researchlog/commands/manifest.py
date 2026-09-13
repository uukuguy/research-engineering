"""`researchlog manifest` — create or partially update a run manifest.

A manifest is the run's identity. It is what makes "this experiment exists but never
produced a result" a fact the tool can see, rather than a gap someone has to remember.

Only the fields named on the command line are touched, so a manifest created early with
its question and inputs keeps them while `--status` and `--heartbeat` are updated around
it. `--heartbeat` writes exactly one field — the liveness timestamp — because it is the
call a long run makes often, and a frequent call that rewrites anything else is a
frequent chance to lose something.
"""

from __future__ import annotations

import argparse
import shlex
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from researchlog import ioutil, jgit, repo, schema
from researchlog.errors import (
    Finding,
    PreconditionMissing,
    Result,
    SEVERITY_ERROR,
    StateInvalid,
)
from researchlog.model import Record

NAME = "manifest"
HELP = "create or partially update a run manifest"

STATUSES: tuple[str, ...] = (
    "pending",
    "running",
    "completed",
    "interrupted",
    "infra_failed",
    "env_blocked",
    "env_unsupported",
    "resource_exceeded",
    "invalid",
)

HEARTBEAT_FIELD = "execution.heartbeat_or_last_observed_at"


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--show", action="store_true", help="print the manifest; writes nothing")
    parser.add_argument("--status", choices=STATUSES, default=None)
    parser.add_argument("--heartbeat", action="store_true", help="bump the liveness timestamp only")
    parser.add_argument("--input", action="append", default=[], metavar="KEY=VALUE")
    # dest is not `command`: the top-level subparsers action already owns that name.
    parser.add_argument(
        "--command", dest="command_line", default=None, help="the command line, as one string"
    )
    parser.add_argument("--expected-output", action="append", default=[], metavar="PATH")


def run(args: argparse.Namespace) -> Result:
    paths = repo.require(args.root)
    path = paths.manifest(args.experiment_id)

    if args.show or not _is_writing(args):
        return _show(path, args.experiment_id)

    existed = path.is_file()
    record = _load_or_create(paths, args, existed)
    changed = _apply(record, args, existed=existed)
    schema.require_writable("manifest", path, record.raw)
    ioutil.write_json_atomic(path, record.raw, validator=schema.load_validator("manifest"))
    return Result(
        payload={
            "experiment_id": args.experiment_id,
            "path": str(path),
            "created": not existed,
            "changed": changed,
            "status": record.get("status"),
        },
        human=f"manifest {args.experiment_id}: {', '.join(changed)}",
    )


def _is_writing(args: argparse.Namespace) -> bool:
    return any(
        (
            args.status is not None,
            args.heartbeat,
            bool(args.input),
            args.command_line is not None,
            bool(args.expected_output),
        )
    )


def _show(path: Path, experiment_id: str) -> Result:
    if not path.is_file():
        raise PreconditionMissing(
            "MANIFEST_ABSENT",
            f"no manifest for {experiment_id} at {path}",
            "create one with `researchlog manifest --experiment-id "
            f"{experiment_id} --status pending`, or run the experiment with `researchlog run`",
        )
    manifest = ioutil.load_json(path)
    return Result(
        payload={"experiment_id": experiment_id, "path": str(path), "manifest": manifest},
        human=_render(manifest),
    )


def _load_or_create(paths: repo.ResearchPaths, args: argparse.Namespace, existed: bool) -> Record:
    path = paths.manifest(args.experiment_id)
    if not existed:
        return Record(_blank(args.experiment_id, jgit.code_state(paths.root).to_dict()), path)
    outcome = ioutil.load_json_with_recovery(path, validator=schema.load_validator("manifest"))
    return Record(outcome.data, path)


def _blank(experiment_id: str, code_state: dict[str, object]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "experiment_id": experiment_id,
        "created_at": _now(),
        "status": "pending",
        "code_state": code_state,
        "execution": {
            "host": socket.gethostname(),
            "launcher": "local_process",
            "pid_or_job_id": None,
            "pid_started_at": None,
            "started_at": None,
            "heartbeat_or_last_observed_at": None,
            "stdout": None,
            "stderr": None,
            "expected_outputs": [],
        },
    }


def _apply(record: Record, args: argparse.Namespace, *, existed: bool) -> list[str]:
    if args.heartbeat and not existed:
        raise PreconditionMissing(
            "MANIFEST_ABSENT",
            f"no manifest for {args.experiment_id} to heartbeat",
            "start the run first; a heartbeat is a liveness signal, not a way to create a run",
        )
    changed: list[str] = []
    if args.status is not None:
        record.set("status", args.status)
        changed.append("status")
    if args.heartbeat:
        record.set(HEARTBEAT_FIELD, _now())
        changed.append(HEARTBEAT_FIELD)
    if args.input:
        record.set("inputs", _inputs(args.input))
        changed.append("inputs")
    if args.command_line is not None:
        record.set("command", shlex.split(args.command_line))
        changed.append("command")
    if args.expected_output:
        record.set("execution.expected_outputs", list(args.expected_output))
        changed.append("execution.expected_outputs")
    if not changed:
        raise StateInvalid(
            [
                Finding(
                    "MANIFEST_NO_UPDATE",
                    SEVERITY_ERROR,
                    args.experiment_id,
                    "no update was requested",
                    "pass --status, --heartbeat, --input, --command or --expected-output; "
                    "use --show to read the manifest",
                )
            ]
        )
    return changed


def _inputs(pairs: list[str]) -> dict[str, str]:
    inputs: dict[str, str] = {}
    for pair in pairs:
        key, separator, value = pair.partition("=")
        if not separator or not key.strip():
            raise StateInvalid(
                [
                    Finding(
                        "INPUT_MALFORMED",
                        SEVERITY_ERROR,
                        pair,
                        "expected KEY=VALUE",
                        "for example --input replay_suite=data-v3",
                    )
                ]
            )
        inputs[key.strip()] = value.strip()
    return inputs


def _render(manifest: dict[str, Any]) -> str:
    execution = manifest.get("execution") or {}
    return (
        f"{manifest.get('experiment_id')}: status={manifest.get('status')} "
        f"pid={execution.get('pid_or_job_id')} host={execution.get('host')}"
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
