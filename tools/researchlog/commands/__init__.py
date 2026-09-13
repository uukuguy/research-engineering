"""Command modules.

Each module exposes NAME, HELP, configure(parser) and run(args) -> Result. The CLI owns
argument parsing, serialization and exit codes, so every command is testable by calling
`run` with a namespace in a temporary directory.
"""

from __future__ import annotations

from types import ModuleType

from researchlog.commands import (
    active,
    checkpoint,
    compare,
    env,
    findings,
    init,
    job,
    manifest,
    reconcile,
    record,
    run as run_cmd,
    snapshot,
    validate,
)

MODULES: tuple[ModuleType, ...] = (
    init,
    validate,
    reconcile,
    active,
    record,
    run_cmd,
    manifest,
    findings,
    env,
    compare,
    snapshot,
    job,
    checkpoint,
)

__all__ = ["MODULES"]
