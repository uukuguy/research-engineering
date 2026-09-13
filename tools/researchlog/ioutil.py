"""Crash-safe canonical writes, and recovery when one did not finish.

A half-written `ACTIVE.json` makes the next session unable to resume, which is the
one failure this whole system exists to prevent. So the write path is strict:

    write .tmp → flush → fsync → parse back → validate → os.replace → fsync(dir)

Three details are easy to get wrong and each has a test:

* **`fsync` before the rename.** Without it some filesystems commit the rename
  before the data, and a crash leaves a canonical file that exists but is truncated.
* **`os.replace`, never `shutil.move`.** `shutil.move` degrades to copy-then-unlink
  across filesystems, which is not atomic.
* **`ensure_ascii=False` with UTF-8.** Otherwise architect `source_text` in Chinese
  is written as `\\uXXXX` escapes — still valid JSON, but no longer human-readable,
  which defeats the reason for keeping it.

Reads never silently pick a source. Every non-canonical recovery is reported.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from researchlog.errors import (
    Finding,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    StateInvalid,
)

TMP_SUFFIX = ".tmp"
SOURCE_CANONICAL = "canonical"
SOURCE_TMP = "tmp"
SOURCE_GIT = "git"


class Validator(Protocol):
    """Structural check applied to the round-tripped document before it is committed."""

    def check(self, data: Mapping[str, Any]) -> list[Finding]: ...


@dataclass(slots=True)
class LoadOutcome:
    """A loaded document plus where it actually came from."""

    data: dict[str, Any]
    source: str
    path: Path
    findings: list[Finding] = field(default_factory=list)

    @property
    def recovered(self) -> bool:
        return self.source != SOURCE_CANONICAL


def write_json_atomic(
    path: Path,
    obj: Mapping[str, Any],
    *,
    validator: Validator | None = None,
) -> Path:
    """Write JSON so that readers see either the old file or the new one, never a mix.

    A validation failure leaves the canonical file byte-identical and removes the
    temporary file, so a rejected write leaves no residue.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + TMP_SUFFIX)
    text = json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False) + "\n"

    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())

    try:
        reparsed = json.loads(tmp.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - guards a serializer bug
        tmp.unlink(missing_ok=True)
        raise StateInvalid(f"serialized document failed to re-parse: {exc}") from exc

    if validator is not None:
        findings = validator.check(reparsed)
        errors = [f for f in findings if f.severity == SEVERITY_ERROR]
        if errors:
            tmp.unlink(missing_ok=True)
            raise StateInvalid(errors)

    os.replace(tmp, path)
    _fsync_dir(path.parent)
    return path


def load_json(path: Path) -> dict[str, Any]:
    """Strict read. Raises StateInvalid rather than leaking JSONDecodeError."""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise StateInvalid([Finding("FILE_MISSING", SEVERITY_ERROR, str(path), "file does not exist")]) from exc
    except OSError as exc:
        raise StateInvalid([Finding("FILE_UNREADABLE", SEVERITY_ERROR, str(path), str(exc))]) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StateInvalid(
            [
                Finding(
                    "JSON_MALFORMED",
                    SEVERITY_ERROR,
                    str(path),
                    f"line {exc.lineno} column {exc.colno}: {exc.msg}",
                    "run `researchlog reconcile` to inspect recovery candidates",
                )
            ]
        ) from exc
    if not isinstance(data, dict):
        raise StateInvalid([Finding("JSON_NOT_OBJECT", SEVERITY_ERROR, str(path), "top level is not an object")])
    return data


def load_json_with_recovery(
    path: Path,
    *,
    validator: Validator | None = None,
    git_recover: Callable[[], str | None] | None = None,
) -> LoadOutcome:
    """Load a canonical document, falling back to `.tmp` and then to Git.

    The search order is canonical → `.tmp` → Git. The chosen source is always
    reported, and a recovery that used anything but the canonical file raises the
    caller's exit code, because a recovered-from-elsewhere state deserves attention
    even when it parses.
    """
    candidates: list[tuple[str, Callable[[], str]]] = [
        (SOURCE_CANONICAL, lambda: path.read_text(encoding="utf-8")),
        (SOURCE_TMP, lambda: path.with_name(path.name + TMP_SUFFIX).read_text(encoding="utf-8")),
    ]
    if git_recover is not None:
        candidates.append((SOURCE_GIT, lambda: _require(git_recover())))

    problems: list[str] = []
    for source, reader in candidates:
        try:
            raw = reader()
        except FileNotFoundError:
            problems.append(f"{source}: not present")
            continue
        except OSError as exc:
            problems.append(f"{source}: {exc}")
            continue

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            problems.append(f"{source}: malformed JSON (line {exc.lineno}: {exc.msg})")
            continue

        if not isinstance(data, dict):
            problems.append(f"{source}: top level is not an object")
            continue

        findings: list[Finding] = []
        if source != SOURCE_CANONICAL:
            findings.append(
                Finding(
                    "RECOVERED_FROM_" + source.upper(),
                    SEVERITY_WARNING,
                    str(path),
                    f"canonical file was unusable; state recovered from {source}",
                    "verify the recovered state, then re-write it canonically",
                )
            )

        if validator is not None:
            check = validator.check(data)
            if any(f.severity == SEVERITY_ERROR for f in check):
                problems.append(f"{source}: failed validation")
                continue
            findings.extend(check)

        return LoadOutcome(data=data, source=source, path=path, findings=findings)

    detail = "; ".join(problems) if problems else "no candidates"
    raise StateInvalid(
        [
            Finding(
                "RECOVERY_REQUIRED",
                SEVERITY_ERROR,
                str(path),
                f"no usable source for canonical state ({detail})",
                "restore the file from a checkpoint commit, or re-run `researchlog init --merge`",
            )
        ]
    )


def _require(text: str | None) -> str:
    if text is None:
        raise FileNotFoundError("git recovery unavailable")
    return text


def _fsync_dir(directory: Path) -> None:
    """Best-effort persistence of the rename itself. Opening a directory fails on Windows."""
    try:
        handle = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(handle)
    except OSError:
        pass
    finally:
        os.close(handle)
