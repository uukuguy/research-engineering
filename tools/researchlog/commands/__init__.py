"""Command modules.

Each module exposes NAME, HELP, configure(parser) and run(args) -> Result. The CLI owns
argument parsing, serialization and exit codes, so every command is testable by calling
`run` with a namespace in a temporary directory.
"""

from __future__ import annotations

from types import ModuleType

from researchlog.commands import (
    active,
    boundaries,
    checkpoint,
    compare,
    current,
    env,
    findings,
    init,
    job,
    manifest,
    references,
    reconcile,
    record,
    run as run_cmd,
    snapshot,
    status,
    synthesize,
    telemetry,
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
    status,
    synthesize,
    telemetry,
    job,
    checkpoint,
    current,
    boundaries,
    references,
)

# `sessions` is NOT in MODULES — it is a helper module that other commands
# (`init`, `active`) call into, not a top-level CLI verb. Exposing it as a
# subcommand would require NAME/HELP/configure/run exports; it has none.

__all__ = ["MODULES"]

__all__ = ["MODULES"]
