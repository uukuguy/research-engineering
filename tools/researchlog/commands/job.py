"""`researchlog job` — is that long-running experiment still alive?

**This command never kills anything, and there will never be a `--kill` flag.** A pid on
disk is a number, not a process: between the run and the question, the machine may have
rebooted and handed that number to something innocent. A tool that sends a signal to a
recorded pid is a tool that can kill a stranger's job — or, on a shared machine, a
stranger's work. So `job` reports and hands back a `suggested_command` for a human or an
agent to run deliberately.

The guard against pid reuse is the process start time. `ps -o lstart=` for a live pid is
compared against the `pid_started_at` recorded when the run began; a mismatch means the
number now belongs to a different process, and the recorded run is gone.

When the answer is not knowable from here — a different host, or a launcher this tool
cannot inspect — it says so and exits 5. Guessing "probably still running" is how a dead
run gets waited on for six hours.
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from researchlog import ioutil, repo
from researchlog.errors import (
    Finding,
    PreconditionMissing,
    Result,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
)
from researchlog.model import Record

NAME = "job"
HELP = "report the liveness of a long-running experiment; never kills anything"

ALIVE = "alive"
ALIVE_STALE = "alive_stale"
DEAD_UNFINALIZED = "dead_unfinalized"
COMPLETED = "completed"
NEVER_STARTED = "never_started"
UNKNOWN_REMOTE_HOST = "unknown_remote_host"
UNSUPPORTED_LAUNCHER = "unsupported_launcher"
PID_REUSED = "pid_reused"

DEFAULT_STALE_SECONDS = 7200
INSPECTABLE_LAUNCHER = "local_process"
TERMINAL_STATUSES: frozenset[str] = frozenset(
    {
        "completed",
        "interrupted",
        "infra_failed",
        "env_blocked",
        "env_unsupported",
        "resource_exceeded",
        "invalid",
    }
)


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--stale-after", type=int, default=DEFAULT_STALE_SECONDS, metavar="SECONDS")


def run(args: argparse.Namespace) -> Result:
    paths = repo.require(args.root)
    path = paths.manifest(args.experiment_id)
    if not path.is_file():
        raise PreconditionMissing(
            "MANIFEST_ABSENT",
            f"no manifest for {args.experiment_id} at {path}",
            "there is no run identity to inspect; check the experiment id",
        )
    record = Record(ioutil.load_json(path), path)
    execution = record.get("execution") or {}
    liveness, reason = _liveness(record, execution, args)

    result = Result(
        payload={
            "experiment_id": args.experiment_id,
            "liveness": liveness,
            "reason": reason,
            "manifest_status": record.get("status"),
            "host": execution.get("host"),
            "launcher": execution.get("launcher"),
            "pid_or_job_id": execution.get("pid_or_job_id"),
            "pid_started_at": execution.get("pid_started_at"),
            "heartbeat_age_seconds": _age_seconds(execution.get("heartbeat_or_last_observed_at")),
            "result_present": paths.result(args.experiment_id).is_file(),
            "suggested_command": _suggest(record, paths, liveness),
        },
        human=f"{args.experiment_id}: {liveness} — {reason}",
    )
    return _verdict_result(result, liveness, args.experiment_id, reason)


def _verdict_result(result: Result, liveness: str, experiment_id: str, reason: str) -> Result:
    if liveness in (UNKNOWN_REMOTE_HOST, UNSUPPORTED_LAUNCHER):
        result.exit_code = 5
        result.add(
            Finding(
                "JOB_LIVENESS_UNKNOWN",
                SEVERITY_ERROR,
                experiment_id,
                reason,
                "liveness cannot be established from this machine; check it where the run lives",
            )
        )
        return result
    if liveness in (ALIVE_STALE, DEAD_UNFINALIZED, PID_REUSED):
        result.add(
            Finding(
                f"JOB_{liveness.upper()}",
                SEVERITY_WARNING,
                experiment_id,
                reason,
                "reconcile this run before starting new work; do not restart it blindly",
            )
        )
        return result
    if liveness == NEVER_STARTED and result.payload.get("manifest_status") not in ("pending", None):
        result.add(
            Finding(
                "JOB_NEVER_STARTED",
                SEVERITY_WARNING,
                experiment_id,
                reason,
                "the manifest claims a run that left no process behind",
            )
        )
    return result


def _liveness(
    record: Record, execution: dict[str, Any], args: argparse.Namespace
) -> tuple[str, str]:
    launcher = execution.get("launcher")
    if launcher != INSPECTABLE_LAUNCHER:
        return UNSUPPORTED_LAUNCHER, f"launcher {launcher!r} cannot be inspected from this machine"
    host = execution.get("host")
    if host is not None and host != socket.gethostname():
        return (
            UNKNOWN_REMOTE_HOST,
            f"the run was recorded on host {host!r}, not {socket.gethostname()!r}",
        )

    status = record.get("status")
    if status in TERMINAL_STATUSES:
        return COMPLETED, f"the manifest is finalised as {status!r}"
    if status == "pending":
        return NEVER_STARTED, "the manifest is still pending; no child was ever launched"

    pid = _pid(execution.get("pid_or_job_id"))
    if pid is None:
        return NEVER_STARTED, "the manifest says running but records no process id"
    alive, started_at = _probe(pid)
    if not alive:
        return DEAD_UNFINALIZED, f"process {pid} is gone but the manifest still says {status!r}"
    recorded = execution.get("pid_started_at")
    if recorded and started_at and recorded.strip() != started_at.strip():
        return (
            PID_REUSED,
            f"pid {pid} belongs to a different process (started {started_at.strip()})",
        )
    age = _age_seconds(execution.get("heartbeat_or_last_observed_at"))
    if age is not None and age > args.stale_after:
        return ALIVE_STALE, f"process {pid} is alive but the last heartbeat was {age:.0f}s ago"
    return ALIVE, f"process {pid} is alive"


def _probe(pid: int) -> tuple[bool, str | None]:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False, None
    except PermissionError:
        pass  # alive, owned by someone else
    except OSError:
        return False, None
    return True, _pid_started_at(pid)


def _pid(value: Any) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _pid_started_at(pid: int) -> str | None:
    completed = subprocess.run(
        ["ps", "-o", "lstart=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip() or None


def _suggest(record: Record, paths: repo.ResearchPaths, liveness: str) -> str | None:
    """A command for a human to run. Never a signal — see the module docstring."""
    experiment_id = record.get("experiment_id")
    if liveness in (ALIVE, ALIVE_STALE):
        return f"researchlog manifest --experiment-id {experiment_id} --heartbeat"
    if liveness in (DEAD_UNFINALIZED, PID_REUSED):
        if paths.result(str(experiment_id)).is_file():
            return f"researchlog record --from-orphan {experiment_id}"
        return f"researchlog manifest --experiment-id {experiment_id} --status interrupted"
    if liveness == NEVER_STARTED and record.get("status") == "running":
        return f"researchlog manifest --experiment-id {experiment_id} --status interrupted"
    return None


def _age_seconds(timestamp: Any) -> float | None:
    if not isinstance(timestamp, str):
        return None
    try:
        moment = datetime.fromisoformat(timestamp)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return round((datetime.now(timezone.utc) - moment).total_seconds(), 3)
