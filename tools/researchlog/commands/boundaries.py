"""`researchlog boundaries` — read or update the `research:boundaries` block in BOUNDARIES.md.

The tier a constraint sits in decides who may change it, which makes BOUNDARIES.md the file
a session consults before touching anything that looks structural. Until this command
existed, nothing wrote that block but `init`, which writes the empty skeleton — so the file
the protocol tells every session to read, and tells `research-bootstrap` to populate, could
only be filled by hand. Writing says the opposite in two places: the file's own prose calls
the block "the machine-readable source of truth", and AGENTS.md says "Never hand-edit that
JSON — use the tool".

`AGENTS.md` still claimed "Every canonical file has a verb", one sentence after explaining
that the claim had not been true for `CURRENT.md` and the `ENVIRONMENT.md` tables. This is
the file that was missed when those two were fixed. The cost was observable: a bootstrap
asked to identify HARD boundaries had nowhere to put them, and the run that found this spent
its time grepping the tool's source for a verb that did not exist.

`--set` takes the same dotted `FIELD=VALUE` form as `current`, including whole lists as JSON.
`--add` appends one entry document to a tier, because that is how the sessions actually work
— both runs wrote scratch JSON to `/tmp` and fed it to `env declare` rather than typing
arrays on the command line. An entry must carry a non-empty `id`: one that cannot be named
cannot be referenced, and cannot be checked for duplication.

The entry shape beyond `id` is deliberately not constrained. What a boundary entry should
carry is a design decision, not a repair's business — the same call this project made for
`ENVIRONMENT.md`'s `capability_map`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from researchlog import repo, schema, state
from researchlog.errors import SEVERITY_ERROR, Finding, Result, StateInvalid
from researchlog.model import Record

NAME = "boundaries"
HELP = "read or update the research:boundaries block in BOUNDARIES.md"

TIERS = ("hard", "provisional", "free")


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
    parser.add_argument(
        "--add",
        dest="additions",
        action="append",
        default=[],
        metavar="TIER=FILE",
        help=f"append the entry document in FILE to {', '.join(TIERS)}; may be repeated",
    )


def _load_entry(path: Path) -> dict:
    """Read one entry document. Refused states are reported, never guessed around."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise StateInvalid(
            [Finding("BOUNDARIES_ADD_UNREADABLE", SEVERITY_ERROR, str(path), str(exc))]
        ) from exc
    except json.JSONDecodeError as exc:
        raise StateInvalid(
            [
                Finding(
                    "BOUNDARIES_ADD_NOT_JSON",
                    SEVERITY_ERROR,
                    str(path),
                    f"the entry document is not valid JSON: {exc}",
                    "one entry is one JSON object; see env declare for the same shape",
                )
            ]
        ) from exc
    if not isinstance(document, dict):
        raise StateInvalid(
            [
                Finding(
                    "BOUNDARIES_ADD_NOT_OBJECT",
                    SEVERITY_ERROR,
                    str(path),
                    f"the entry document is a {type(document).__name__}, not an object",
                )
            ]
        )
    return document


def run(args: argparse.Namespace) -> Result:
    paths = repo.require(args.root)
    text = paths.boundaries.read_text(encoding="utf-8")
    block = schema.require_block(text, "boundaries", source=paths.boundaries.name)
    record = Record(block, paths.boundaries)

    if not args.assignments and not args.additions:
        # Reading is what a session does before touching something structural, so it must
        # not rewrite the file and dirty the working tree for a session that only looked.
        return Result(payload={"boundaries": block})

    changed: list[str] = []
    for expression in args.assignments:
        field, value = state.parse_assignment(expression, code="BOUNDARIES_SET_MALFORMED")
        record.set(field, value)
        changed.append(field)

    for addition in args.additions:
        tier, separator, raw_path = addition.partition("=")
        tier = tier.strip()
        if not separator or tier not in TIERS:
            raise StateInvalid(
                [
                    Finding(
                        "BOUNDARIES_ADD_MALFORMED",
                        SEVERITY_ERROR,
                        addition,
                        f"expected TIER=FILE with TIER one of {', '.join(TIERS)}",
                        "for example --add hard=/tmp/boundary.json",
                    )
                ]
            )
        document = _load_entry(Path(raw_path.strip()))
        entry_id = document.get("id")
        if not isinstance(entry_id, str) or not entry_id.strip():
            raise StateInvalid(
                [
                    Finding(
                        "BOUNDARIES_ADD_NO_ID",
                        SEVERITY_ERROR,
                        raw_path.strip(),
                        'the entry document has no non-empty "id"',
                        "an entry that cannot be named cannot be referenced, or checked "
                        "for duplication",
                    )
                ]
            )
        existing = [entry for entry in record.raw.get(tier) or [] if isinstance(entry, dict)]
        if any(entry.get("id") == entry_id for entry in existing):
            raise StateInvalid(
                [
                    Finding(
                        "BOUNDARIES_ADD_DUPLICATE",
                        SEVERITY_ERROR,
                        entry_id,
                        f"{tier} already holds an entry with this id",
                    )
                ]
            )
        record.set(tier, [*existing, document])
        changed.append(f"{tier}[{entry_id}]")

    # Schema-checked before the write, so a refused change leaves the file untouched.
    validator = schema.load_validator("boundaries")
    findings = validator.check(record.raw)
    errors = [finding for finding in findings if finding.severity == SEVERITY_ERROR]
    if errors:
        raise StateInvalid(errors)

    paths.boundaries.write_text(
        schema.replace_block(text, "boundaries", record.raw), encoding="utf-8"
    )

    result = Result(payload={"path": str(paths.boundaries), "changed": changed})
    for finding in findings:
        result.add(finding)
    result.human = f"updated {paths.boundaries.name}: {', '.join(changed)}"
    return result
