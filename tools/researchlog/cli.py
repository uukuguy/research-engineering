"""Argument parsing, dispatch, and the single place that writes output.

Every command returns a `Result`; nothing else prints. That keeps the JSON envelope
uniform — an agent branches on `exit_code` and reads `findings`, and never has to parse
prose — and it means each command is testable by calling `run()` with a namespace, with
no captured stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from types import ModuleType
from typing import Any

from researchlog import __version__
from researchlog.commands import MODULES
from researchlog.errors import (
    EXIT_OK,
    EXIT_TOOL_INTERNAL,
    Finding,
    ResearchLogError,
    Result,
    SEVERITY_ERROR,
)
from researchlog.schema import schema_versions_in_use

PROG = "researchlog"


def build_parser() -> argparse.ArgumentParser:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--json", action="store_true", help="emit a machine-readable envelope on stdout")
    shared.add_argument("--quiet", action="store_true", help="suppress human-facing output")

    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Deterministic bookkeeping for a research repository.",
        epilog=(
            "This tool never chooses a hypothesis, never decides keep-or-revert, never calls a "
            "model, and never repairs state on its own."
        ),
    )
    parser.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    for module in MODULES:
        subparser = subparsers.add_parser(module.NAME, help=module.HELP, parents=[shared])
        module.configure(subparser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    module = module_for(args.command)

    try:
        result = module.run(args)
    except ResearchLogError as exc:
        result = exc.to_result()
    except KeyboardInterrupt:  # pragma: no cover - interactive
        print(f"{PROG}: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001 - the last line of defence
        import traceback

        traceback.print_exc()
        result = Result(
            exit_code=EXIT_TOOL_INTERNAL,
            findings=[Finding("TOOL_INTERNAL", SEVERITY_ERROR, "-", f"{type(exc).__name__}: {exc}")],
        )

    emit(result, args, command=args.command)
    return result.exit_code


def module_for(name: str) -> ModuleType:
    for module in MODULES:
        if module.NAME == name:
            return module
    raise KeyError(f"unknown command {name!r}")  # pragma: no cover - argparse prevents this


def emit(result: Result, args: argparse.Namespace, *, command: str) -> None:
    as_json = bool(getattr(args, "json", False))
    quiet = bool(getattr(args, "quiet", False))

    if as_json:
        envelope = result.to_dict(
            command=command,
            schema_versions=schema_versions_in_use(),
            tool_version=__version__,
        )
        json.dump(envelope, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    elif not quiet:
        text = result.human or _default_human(result, command)
        if text:
            print(text)
    elif result.exit_code != EXIT_OK and result.findings:
        for finding in result.findings:
            print(f"{finding.severity}: {finding.code} {finding.subject} — {finding.message}", file=sys.stderr)


def _default_human(result: Result, command: str) -> str:
    lines: list[str] = []
    for finding in result.findings:
        lines.append(f"{finding.severity:7} {finding.code:34} {finding.subject}")
        # The message and the fix hint are the actionable half. A bare code sends the reader
        # to the source to find out what the constraint was before they can act on it — and
        # for a write that was refused, that is the only thing they need.
        lines.append(f"        {finding.message}")
        if finding.fix_hint:
            lines.append(f"        → {finding.fix_hint}")
    if result.exit_code == EXIT_OK and not result.findings:
        lines.append(f"{command}: ok")
    if result.payload:
        lines.append(json.dumps(result.payload, ensure_ascii=False, indent=2))
    return "\n".join(lines)


def run_and_capture(argv: Sequence[str]) -> tuple[int, dict[str, Any]]:
    """Convenience for tests: run a command and return its JSON envelope.

    `--json` goes immediately after the command name, never appended. Appending would
    place it past a `--` separator on `run`, where it becomes an argument to the child
    process rather than to this tool — and the failure mode is a silent empty envelope,
    not an error.
    """
    import contextlib
    import io

    args = list(argv)
    if args and not args[0].startswith("-"):
        args.insert(1, "--json")
    else:
        args.append("--json")

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = main(args)
    captured = buffer.getvalue().strip()
    if not captured:
        raise AssertionError(f"no JSON envelope produced for {argv!r} (exit {code})")
    return code, json.loads(captured)
