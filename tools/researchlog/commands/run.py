"""`researchlog run` — execute an experiment and capture its provenance.

The rule this file exists to encode: **a non-zero exit from the child is scientific
data, not a tool failure.** A run whose command returns 1 has answered its question
negatively, and that answer is worth exactly as much as a positive one. So the default
exit is 0 whenever the run was captured successfully, the child's own code travels in
`payload.child_exit_code`, and `result.json` is written. Treating a failed experiment as
a failed tool is how a research loop learns to avoid running experiments.

The three cases that are *not* the experiment's result:

* **the command could not start** — `infra_failed`, no `result.json`, exit 5. Nothing was
  measured, so there is nothing to record.
* **the run was killed or timed out** — `interrupted`, partial output kept, exit 3.
  Metadata about the session, never a conclusion about a hypothesis.
* **the manifest is still in flight** (`pending` or `running`) — refused unconditionally.
  This is what stops an expensive run from being restarted by an agent that lost its
  context. Finalised manifests (`completed` / `interrupted` / `infra_failed` /
  `env_blocked` / `env_unsupported` / `resource_exceeded` / `invalid`) are always
  allowed; the previous run is read for context, not for ownership.

The manifest is written before the child exists, so an interrupted run still has an
identity to reconcile against.
"""

from __future__ import annotations

import argparse
import math
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from researchlog import ids, ioutil, jgit, repo, schema
from researchlog.errors import (
    EXIT_TOOL_INTERNAL,
    Finding,
    PreconditionMissing,
    RefusedByPolicy,
    Result,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    StateInvalid,
)
from researchlog.model import Record

NAME = "run"
HELP = "execute an experiment and capture its provenance"

CHILD_CODE_MAX = 255
NOT_EXECUTABLE = 126
NOT_FOUND = 127
SHELL_FAILURE = 125


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--experiment-id", default=None, help="reuse an existing experiment identity"
    )
    parser.add_argument("--question", default=None)
    parser.add_argument("--hypothesis", action="append", default=[], metavar="H-ID")
    parser.add_argument("--subject-type", default=None)
    parser.add_argument("--subject-id", default=None)
    parser.add_argument("--input", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--expected-output", action="append", default=[], metavar="PATH")
    parser.add_argument("--timeout", type=float, default=None, metavar="SECONDS")
    # V1 P7: every long-running experiment must leave a live heartbeat on disk,
    # so a session that has lost the run can still tell whether the process is
    # actually working or has gone dark. Default 30s; pass 0 to disable.
    parser.add_argument(
        "--heartbeat-interval", type=float, default=30.0, metavar="SECONDS"
    )
    # V1 P6: stale overwrite is forbidden. To rerun a finalised experiment, just
    # re-invoke `run` with the same `--experiment-id`; the previous manifest is read
    # for context, not for ownership. `--replace-existing` no longer exists.
    parser.add_argument(
        "--propagate-exit", action="store_true", help="exit with the child's own code"
    )
    # Not named `command`: the top-level subparsers action already owns that dest.
    parser.add_argument("child_command", nargs=argparse.REMAINDER, metavar="COMMAND")


def run(args: argparse.Namespace) -> Result:
    paths = repo.require(args.root)
    if args.timeout is not None and (not math.isfinite(args.timeout) or args.timeout <= 0):
        raise StateInvalid('--timeout must be a finite positive number of seconds')
    command = _strip_separator(args.child_command)
    if not command:
        raise PreconditionMissing(
            "RUN_COMMAND_MISSING",
            "no command given to run",
            "usage: researchlog run -- <command> [args...]",
        )

    experiment_id = args.experiment_id or ids.mint("experiment")
    manifest_path = paths.manifest(experiment_id)
    existing = _load_existing(manifest_path)
    _refuse_running(existing, experiment_id)

    started_at = _now()
    stdout_path = paths.stdout(experiment_id)
    stderr_path = paths.stderr(experiment_id)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    record = _manifest(
        paths, experiment_id, command, args, existing, started_at, stdout_path, stderr_path
    )
    _write_manifest(manifest_path, record)

    try:
        process = _spawn(command, paths.root)
    except OSError as exc:
        return _not_started(manifest_path, record, experiment_id, args, exc)

    return _supervise(
        paths,
        record,
        manifest_path,
        process,
        experiment_id,
        command,
        args,
        started_at,
        stdout_path,
        stderr_path,
    )


def _supervise(
    paths: repo.ResearchPaths,
    record: Record,
    manifest_path: Path,
    process: subprocess.Popen[str],
    experiment_id: str,
    command: list[str],
    args: argparse.Namespace,
    started_at: str,
    stdout_path: Path,
    stderr_path: Path,
) -> Result:
    began = time.monotonic()
    record.set("execution.pid_or_job_id", str(process.pid))
    record.set("execution.pid_started_at", _pid_started_at(process.pid))
    record.set("execution.process_group_id", str(process.pid) if os.name == 'posix' else None)
    _write_manifest(manifest_path, record)

    sinks = _sinks(args)
    threads = [
        _pump(process.stdout, sinks["stdout"], stdout_path),
        _pump(process.stderr, sinks["stderr"], stderr_path),
    ]
    # V1 P7: the supervisor bumps the heartbeat field while the child runs.
    # `0` is the explicit opt-out; negative intervals are nonsense and raise
    # at argparse. The thread is daemon, so it cannot wedge a session after
    # the child has exited even if our join below is interrupted.
    heartbeat_thread = _start_heartbeat(
        record,
        manifest_path,
        interval=args.heartbeat_interval,
        stop=lambda: process.poll() is not None,
    )
    deadline = began + args.timeout if args.timeout is not None else None
    timed_out = False
    interrupted_by_user = False
    try:
        child_code = process.wait(timeout=max(0, deadline - time.monotonic())
                                  if deadline is not None else None)
        # A launcher can exit while its descendants still own the output pipes.
        # The timeout bounds the complete capture, not just the launcher's wait().
        _join_relays(threads, deadline if deadline is not None else time.monotonic() + 5)
        if deadline is not None and any(thread.is_alive() for thread in threads):
            raise subprocess.TimeoutExpired(command, args.timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate_owned(process)
        child_code = process.wait()
    except KeyboardInterrupt:
        interrupted_by_user = True
        _terminate_owned(process)
        child_code = process.wait()
    if timed_out or interrupted_by_user:
        _join_relays(threads, time.monotonic() + 1)
    if heartbeat_thread is not None:
        heartbeat_thread.join(timeout=5.0)
    capture_incomplete = any(thread.is_alive() for thread in threads)
    _close_pipes(process, threads)
    duration = round(time.monotonic() - began, 3)

    status, reason = _classify(child_code, timed_out)
    if interrupted_by_user:
        status, reason = 'interrupted', 'process_signal'
    elif capture_incomplete and not timed_out:
        status, reason = 'interrupted', 'unknown'
    record.set('execution.output_capture_complete', not capture_incomplete)
    finished_at = _now()
    record.set("status", status)
    record.set("child_exit_code", child_code)
    record.set("execution.heartbeat_or_last_observed_at", finished_at)
    if reason is not None:
        record.set("interruption_reason", reason)
    _write_manifest(manifest_path, record)

    result_path = None
    if status == "completed":
        result_path = _write_result(
            paths,
            experiment_id,
            command,
            child_code,
            started_at,
            finished_at,
            duration,
            stdout_path,
            stderr_path,
        )

    result = Result(
        payload={
            "experiment_id": experiment_id,
            "status": status,
            "child_exit_code": child_code,
            "duration_seconds": duration,
            "manifest": str(manifest_path),
            "result": str(result_path) if result_path else None,
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
        }
    )
    if status == "interrupted":
        result.add(
            Finding(
                "RUN_INTERRUPTED",
                SEVERITY_WARNING,
                experiment_id,
                f"the run was {reason}; partial output is in {stdout_path.name}",
                "this is session or infrastructure metadata, not a result about the hypothesis",
            )
        )
    if capture_incomplete:
        result.add(Finding(
            'RUN_OUTPUT_CAPTURE_INCOMPLETE', SEVERITY_WARNING, experiment_id,
            'a process still holds output pipes; capture and descendant liveness are unresolved',
            'inspect surviving jobs before handoff; detached processes are outside process-group containment',
        ))
    result.human = _human(result.payload)
    if args.propagate_exit and status == "completed":
        result.exit_code = child_code if 0 <= child_code <= CHILD_CODE_MAX else EXIT_TOOL_INTERNAL
    return result


def _strip_separator(command: list[str]) -> list[str]:
    """`run -- cmd` reaches REMAINDER with the separator attached; the child does not want it."""
    return command[1:] if command[:1] == ["--"] else command


def _classify(child_code: int, timed_out: bool) -> tuple[str, str | None]:
    if timed_out:
        return "interrupted", "timeout"
    if child_code < 0:
        return "interrupted", "process_signal"
    return "completed", None


def _spawn(command: list[str], root: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
        command,
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        start_new_session=os.name == 'posix',
    )


def _terminate_owned(process: subprocess.Popen[str]) -> None:
    """Signal only the new group created by _spawn, never the caller's group.

    Ordinary descendants (including uv's Python child) inherit this group. Daemons
    that deliberately create another session need an external job supervisor.
    """
    try:
        if os.name == 'posix':
            os.killpg(process.pid, signal.SIGKILL)
        elif process.poll() is None:
            process.kill()
    except ProcessLookupError:
        pass


def _join_relays(threads: list[threading.Thread], deadline: float) -> None:
    for thread in threads:
        thread.join(timeout=max(0, deadline - time.monotonic()))


def _sinks(args: argparse.Namespace) -> dict[str, TextIO]:
    """Under --json, stdout stays pure JSON, so child stdout is relayed to stderr."""
    if getattr(args, "json", False):
        return {"stdout": sys.stderr, "stderr": sys.stderr}
    return {"stdout": sys.stdout, "stderr": sys.stderr}


def _close_pipes(process: subprocess.Popen[str], threads: list[threading.Thread]) -> None:
    """Release the child's read ends.

    Relays normally close their own streams. Close any stopped relay's remaining
    handle, but leave a still-reading relay ownership of its handle until it exits.
    """
    for stream, thread in zip((process.stdout, process.stderr), threads):
        # TextIO.close() waits for the reader lock. Never close under a blocked
        # relay: that is the unbounded wait this timeout is intended to prevent.
        if not thread.is_alive() and stream is not None and not stream.closed:
            stream.close()


def _pump(stream: Iterable[str] | None, sink: TextIO, path: Path) -> threading.Thread:
    def relay() -> None:
        with open(path, "w", encoding="utf-8") as handle:
            if stream is None:  # pragma: no cover - PIPE always yields a stream
                return
            try:
                for line in stream:
                    handle.write(line)
                    handle.flush()
                    sink.write(line)
                    sink.flush()
            except ValueError:
                # The pipe was closed underneath us at shutdown, after a join timed out.
                # Whatever was read is already on disk; that is the contract.
                return
            finally:
                if hasattr(stream, 'close'):
                    stream.close()

    thread = threading.Thread(target=relay, name=f"relay-{path.name}", daemon=True)
    thread.start()
    return thread


# V1 P7: while a child process runs, a daemon thread bumps the manifest's
# heartbeat field on the disk every `--heartbeat-interval` seconds. The
# thread is daemon so it cannot block session teardown; the caller still
# joins it after `process.wait` returns so the final bump is observed
# before the manifest is closed out. `stop` is a callable rather than a
# flag so a stuck `time.sleep` cannot delay shutdown by more than the
# remaining interval — the loop checks both the wall clock and the child
# status.
def _start_heartbeat(
    record: Record,
    manifest_path: Path,
    *,
    interval: float,
    stop: Callable[[], bool],
) -> threading.Thread | None:
    if interval <= 0:
        return None

    def relay() -> None:
        next_at = time.monotonic() + interval
        while True:
            # Sleep in small slices so a session interrupt (Ctrl+C / stop)
            # tears the loop down within a second, not after a full interval.
            now = time.monotonic()
            slice_end = min(next_at, now + 1.0)
            while now < slice_end:
                time.sleep(min(0.2, slice_end - now))
                if stop():
                    return
                now = time.monotonic()
            if stop():
                return
            try:
                record.set("execution.heartbeat_or_last_observed_at", _now())
                _write_manifest(manifest_path, record)
            except Exception:  # pragma: no cover - heartbeat is best-effort
                # A heartbeat that fails to write must not crash the run.
                # The next bump or the final closeout will publish state.
                return
            next_at = time.monotonic() + interval

    thread = threading.Thread(
        target=relay, name=f"heartbeat-{manifest_path.parent.name}", daemon=True
    )
    thread.start()
    return thread


def _manifest(
    paths: repo.ResearchPaths,
    experiment_id: str,
    command: list[str],
    args: argparse.Namespace,
    existing: Record | None,
    started_at: str,
    stdout_path: Path,
    stderr_path: Path,
) -> Record:
    raw = existing.raw if existing is not None else _blank(experiment_id, started_at)
    record = Record(raw, paths.manifest(experiment_id))
    record.set("code_state", jgit.code_state(paths.root).to_dict())
    record.set("command", command)
    record.set("status", "running")
    record.set("execution.host", socket.gethostname())
    record.set("execution.launcher", "local_process")
    record.set("execution.started_at", started_at)
    record.set("execution.heartbeat_or_last_observed_at", started_at)
    record.set("execution.stdout", _relative(stdout_path, paths.root))
    record.set("execution.stderr", _relative(stderr_path, paths.root))
    record.set("execution.timeout_seconds", args.timeout)
    record.set("execution.process_group_id", None)
    record.set("execution.output_capture_complete", None)
    record.set("child_exit_code", None)
    record.delete("interruption_reason")
    _apply_manifest_flags(record, args)
    return record


def _blank(experiment_id: str, started_at: str) -> dict[str, Any]:
    """The minimum a manifest must carry before a child process exists."""
    return {
        "schema_version": "1.0",
        "experiment_id": experiment_id,
        "created_at": started_at,
        "status": "pending",
        "code_state": {},
        "execution": {
            "host": None,
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


def _apply_manifest_flags(record: Record, args: argparse.Namespace) -> None:
    if args.hypothesis:
        record.set("hypothesis_ids", list(args.hypothesis))
    if args.question is not None:
        record.set("question", args.question)
    if args.expected_output:
        record.set("execution.expected_outputs", list(args.expected_output))
    if args.input:
        record.set("inputs", _inputs(args.input))
    if args.subject_type is not None or args.subject_id is not None:
        if not (args.subject_type and args.subject_id):
            raise StateInvalid("a subject needs both --subject-type and --subject-id")
        record.set("subject", {"type": args.subject_type, "id": args.subject_id})


def _inputs(pairs: list[str]) -> dict[str, str]:
    inputs: dict[str, str] = {}
    for pair in pairs:
        key, separator, value = pair.partition("=")
        if not separator or not key.strip():
            raise StateInvalid(f"--input expects KEY=VALUE, got {pair!r}")
        inputs[key.strip()] = value.strip()
    return inputs


def _not_started(
    manifest_path: Path,
    record: Record,
    experiment_id: str,
    args: argparse.Namespace,
    exc: OSError,
) -> Result:
    record.set("status", "infra_failed")
    record.set("execution.pid_or_job_id", None)
    record.set("execution.heartbeat_or_last_observed_at", _now())
    _write_manifest(manifest_path, record)

    code = _spawn_code(exc)
    finding = Finding(
        "RUN_NOT_STARTED",
        SEVERITY_ERROR,
        experiment_id,
        f"the command never started: {exc}",
        "nothing was measured, so no result.json was written; fix the command and re-run",
    )
    if args.propagate_exit:
        return Result(
            exit_code=code,
            payload=_not_started_payload(experiment_id, manifest_path),
            findings=[finding],
        )
    raise PreconditionMissing(
        "RUN_NOT_STARTED",
        finding.message,
        finding.fix_hint,
        payload=_not_started_payload(experiment_id, manifest_path),
    )


def _not_started_payload(experiment_id: str, manifest_path: Path) -> dict[str, Any]:
    return {
        "experiment_id": experiment_id,
        "status": "infra_failed",
        "child_exit_code": None,
        "manifest": str(manifest_path),
        "result": None,
    }


def _spawn_code(exc: OSError) -> int:
    if isinstance(exc, FileNotFoundError):
        return NOT_FOUND
    if isinstance(exc, PermissionError):
        return NOT_EXECUTABLE
    return SHELL_FAILURE


# An experiment is "in flight" while its manifest is not yet finalised. V0 only
# guarded `running`; V1 (P6) also guards `pending`, because a crash between
# `_write_manifest` and `_apply_manifest_flags` could otherwise leave a half-written
# record open to overwrite. Finalised statuses — completed / interrupted /
# infra_failed / env_blocked / env_unsupported / resource_exceeded / invalid — are
# always allowed: the previous manifest is consulted for context, not for ownership.
_IN_FLIGHT_STATUSES = frozenset({"pending", "running"})


def _refuse_running(existing: Record | None, experiment_id: str) -> None:
    if existing is None:
        return
    if existing.get("status") not in _IN_FLIGHT_STATUSES:
        return
    raise RefusedByPolicy(
        "EXPERIMENT_ALREADY_RUNNING",
        f"{experiment_id} already has a manifest with status {existing.get('status')}",
        "inspect it with `researchlog job --experiment-id "
        f"{experiment_id}`; if the process is gone, finalise that run first. "
        "V1 (P6) forbids `--replace-existing`: re-invoke `run` with the same "
        "`--experiment-id` only after the previous run is finalised.",
    )


def _load_existing(path: Path) -> Record | None:
    """The previous manifest, if any. A missing one is the normal case, not a recovery."""
    if not path.is_file():
        return None
    outcome = ioutil.load_json_with_recovery(path, validator=schema.load_validator("manifest"))
    return Record(outcome.data, path)


def _write_manifest(path: Path, record: Record) -> Path:
    schema.require_writable("manifest", path, record.raw)
    return ioutil.write_json_atomic(path, record.raw, validator=schema.load_validator("manifest"))


def _write_result(
    paths: repo.ResearchPaths,
    experiment_id: str,
    command: list[str],
    child_code: int,
    started_at: str,
    finished_at: str,
    duration: float,
    stdout_path: Path,
    stderr_path: Path,
) -> Path:
    return ioutil.write_json_atomic(
        paths.result(experiment_id),
        {
            "schema_version": "1.0",
            "experiment_id": experiment_id,
            "command": command,
            "child_exit_code": child_code,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": duration,
            "stdout": _relative(stdout_path, paths.root),
            "stderr": _relative(stderr_path, paths.root),
        },
    )


def _pid_started_at(pid: int) -> str | None:
    """Recorded so `job` can tell this process from an unrelated one that reused the pid."""
    completed = subprocess.run(
        ["ps", "-o", "lstart=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip() or None


def _human(payload: dict[str, Any]) -> str:
    return (
        f"{payload['experiment_id']}: {payload['status']} "
        f"(child exit {payload['child_exit_code']}, {payload['duration_seconds']}s)"
    )


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root.resolve()).as_posix()
    except ValueError:  # pragma: no cover - run paths always live under the root
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
