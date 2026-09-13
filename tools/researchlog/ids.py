"""Collision-resistant identifier minting.

The design forbids allocating IDs by reading the last one and incrementing: two
parallel worktrees doing that both produce `EV-142`, and the collision is silent
until a merge. Two things replace the counter here.

1. **A time-plus-random suffix** makes collisions improbable.
2. **`O_CREAT | O_EXCL`** makes the remaining ones impossible. The exclusive create
   is atomic on POSIX and on local Windows filesystems, it blocks nobody, and it is
   the only lock this tool is allowed to take.

`mint` is pure — it never touches the filesystem — so tests can freeze the clock and
force the RNG to collide. `claim_new` is the only function here that writes, and all
it writes is an empty reservation file.

Input IDs are *not* required to match this format. A hand-written `EXP-0142` keeps
working; the tool simply never mints counter-style IDs itself.
"""

from __future__ import annotations

import os
import re
import secrets
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from researchlog.errors import IdSpaceExhausted

_PREFIX: dict[str, str] = {
    "evidence": "EV",
    "experiment": "EXP",
    "hypothesis": "H",
    "finding": "FND",
    "block": "RB",
    "session": "SE",
    "environment": "ENV",
}

# Deliberately lenient: uppercase kind prefix, then anything identifier-ish.
# Used to validate IDs supplied by callers, not IDs this module generates.
_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*-[A-Za-z0-9TZ:._-]+$")

ClockFn = Callable[[], datetime]
RandFn = Callable[[int], str]

_BASE_HEXLEN = 4
_GROWTH = (0, 2, 4)


def prefix_for(kind: str) -> str:
    """Return the ID prefix for a record kind, or raise KeyError with the options."""
    try:
        return _PREFIX[kind]
    except KeyError:
        known = ", ".join(sorted(_PREFIX))
        raise KeyError(f"unknown record kind {kind!r}; expected one of: {known}") from None


def mint(
    kind: str,
    *,
    now: ClockFn | None = None,
    rand: RandFn | None = None,
    hexlen: int = _BASE_HEXLEN,
) -> str:
    """Build a fresh ID. Pure: reads no files, consults no counter.

    `now` and `rand` are injectable so tests can freeze time and force collisions.
    """
    if hexlen < 2 or hexlen % 2:
        raise ValueError(f"hexlen must be an even number >= 2, got {hexlen}")
    prefix = prefix_for(kind)
    stamp = (now or _utcnow)().strftime("%Y%m%dT%H%M%SZ")
    suffix = (rand or secrets.token_hex)(hexlen // 2)
    return f"{prefix}-{stamp}-{suffix}"


def claim_new(
    kind: str,
    path_for: Callable[[str], Path],
    *,
    attempts: int = 8,
    now: ClockFn | None = None,
    rand: RandFn | None = None,
) -> tuple[str, Path]:
    """Atomically reserve a fresh ID and return it with its path.

    The returned path exists and is empty. The caller overwrites it with
    `ioutil.write_json_atomic`, which uses `os.replace` and so is safe against the
    reservation.

    On collision the suffix grows before retrying, so a pathological RNG still
    terminates rather than spinning.
    """
    for extra in _GROWTH:
        for _ in range(attempts):
            candidate = mint(kind, now=now, rand=rand, hexlen=_BASE_HEXLEN + extra)
            path = path_for(candidate)
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            except FileExistsError:
                continue
            os.close(handle)
            return candidate, path
    raise IdSpaceExhausted(
        f"no free {kind} id after {attempts * len(_GROWTH)} attempts "
        f"(is the clock stuck and the RNG degenerate?)"
    )


def is_valid_id(value: str) -> bool:
    """Lenient format check for caller-supplied IDs."""
    return bool(_ID_RE.match(value))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
