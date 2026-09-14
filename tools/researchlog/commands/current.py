"""`researchlog current` — read or update the `research:current` block in CURRENT.md.

CURRENT.md is research-level working memory: where the research has got to, as against
ACTIVE.json's what is happening right now. The block is its machine-readable half.

Until this command existed nothing read or wrote that block. `schema/loader.py` knew the
name, `repo.py` built the path object, and no verb touched either — so a file the protocol
tells every session to read on resume, and to update as the working model changes, could
only be edited by hand. Its own prose says the opposite ("Edit it through `researchlog`,
never by hand"), and so does AGENTS.md ("Never hand-edit that JSON — use the tool"). State
that no verb can reach is also state no check can reach: the block was never validated, so
it could drift arbitrarily while every other canonical file was checked.

The prose around the block is left untouched. It explains how to read the file rather than
restating it, so the two cannot drift apart.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from researchlog import repo, schema, state
from researchlog.errors import SEVERITY_ERROR, Result, StateInvalid
from researchlog.model import Record

NAME = "current"
HELP = "read or update the research:current block in CURRENT.md"


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--set",
        dest="assignments",
        action="append",
        default=[],
        metavar="FIELD=VALUE",
        help="set a dotted field (JSON value, or a plain string); may be repeated",
    )


def run(args: argparse.Namespace) -> Result:
    paths = repo.require(args.root)
    text = paths.current.read_text(encoding="utf-8")
    block = schema.require_block(text, "current", source=paths.current.name)
    record = Record(block, paths.current)

    if not args.assignments:
        # Reading is the common case on resume, so it must not rewrite the file and dirty
        # the working tree for a session that only wanted to look.
        return Result(payload={"current": block})

    changed: list[str] = []
    for expression in args.assignments:
        field, value = state.parse_assignment(expression, code="CURRENT_SET_MALFORMED")
        record.set(field, value)
        changed.append(field)

    validator = schema.load_validator("current")
    findings = validator.check(record.raw)
    errors = [finding for finding in findings if finding.severity == SEVERITY_ERROR]
    if errors:
        raise StateInvalid(errors)

    paths.current.write_text(
        schema.replace_block(text, "current", record.raw), encoding="utf-8"
    )

    result = Result(payload={"path": str(paths.current), "changed": changed})
    for finding in findings:
        result.add(finding)
    result.human = f"updated {paths.current.name}: {', '.join(changed)}"
    return result
