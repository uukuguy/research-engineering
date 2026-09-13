"""Machine-readable blocks inside human-readable markdown.

`FINDINGS.md`, `BOUNDARIES.md`, `ENVIRONMENT.md`, and `CURRENT.md` each carry one
fenced block:

    ```json research:findings
    { "entries": [ ... ] }
    ```

The JSON is the single source of truth; the prose around it is regenerated from it.
This keeps Chinese reading material for the architect and machine state for the agent in
one file without a YAML dependency and without a second copy of the facts.

`ARCHITECT.md` is the exception: its signals are individual `research:signal` blocks,
because signals are independent entities that are appended and expire separately.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from researchlog.errors import SEVERITY_ERROR, Finding, StateInvalid

_OPEN = re.compile(r"^```json[ \t]+research:([a-z_]+)[ \t]*$")
_CLOSE = re.compile(r"^```[ \t]*$")

BLOCK_NAMES: dict[str, str] = {
    "CURRENT.md": "current",
    "BOUNDARIES.md": "boundaries",
    "ENVIRONMENT.md": "environment",
    "FINDINGS.md": "findings",
}
SIGNAL_BLOCK = "signal"


class _Span:
    __slots__ = ("name", "start", "end")

    def __init__(self, name: str, start: int, end: int) -> None:
        self.name = name
        self.start = start  # index of the opening fence line
        self.end = end  # index of the closing fence line, inclusive


def extract_blocks(text: str) -> dict[str, list[dict[str, Any]]]:
    """Return {block name: [parsed objects]}. A name may repeat (signals do)."""
    lines = text.splitlines()
    blocks: dict[str, list[dict[str, Any]]] = {}
    for span in _spans(lines):
        body = lines[span.start + 1 : span.end]
        blocks.setdefault(span.name, []).append(_parse(body, span.name, span.start + 1))
    return blocks


def find_block(text: str, name: str) -> dict[str, Any] | None:
    """Return the single block with this name, or None. Raises if it appears twice."""
    found = extract_blocks(text).get(name, [])
    if not found:
        return None
    if len(found) > 1:
        raise StateInvalid(
            [
                Finding(
                    "BLOCK_DUPLICATED",
                    SEVERITY_ERROR,
                    name,
                    f"expected exactly one research:{name} block, found {len(found)}",
                )
            ]
        )
    return found[0]


def require_block(text: str, name: str, *, source: str) -> dict[str, Any]:
    block = find_block(text, name)
    if block is None:
        raise StateInvalid(
            [
                Finding(
                    "BLOCK_MISSING",
                    SEVERITY_ERROR,
                    source,
                    f"no ```json research:{name} block found",
                    f"re-run `researchlog init --merge` or add the block back by hand",
                )
            ]
        )
    return block


def replace_block(text: str, name: str, payload: Mapping[str, Any]) -> str:
    """Replace the named block in place, leaving all surrounding prose untouched."""
    lines = text.splitlines()
    rendered = render_block_lines(name, payload)
    for span in _spans(lines):
        if span.name == name:
            return "\n".join(lines[: span.start] + rendered + lines[span.end + 1 :]) + "\n"
    raise StateInvalid(
        [Finding("BLOCK_MISSING", SEVERITY_ERROR, name, f"cannot replace absent research:{name} block")]
    )


def render_block(name: str, payload: Mapping[str, Any]) -> str:
    return "\n".join(render_block_lines(name, payload)) + "\n"


def render_block_lines(name: str, payload: Mapping[str, Any]) -> list[str]:
    body = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False)
    return [f"```json research:{name}", *body.splitlines(), "```"]


def _spans(lines: list[str]) -> list[_Span]:
    spans: list[_Span] = []
    index = 0
    while index < len(lines):
        match = _OPEN.match(lines[index])
        if match is None:
            index += 1
            continue
        end = index + 1
        while end < len(lines) and not _CLOSE.match(lines[end]):
            end += 1
        if end >= len(lines):
            raise StateInvalid(
                [
                    Finding(
                        "BLOCK_UNTERMINATED",
                        SEVERITY_ERROR,
                        match.group(1),
                        f"fence opened at line {index + 1} is never closed",
                    )
                ]
            )
        spans.append(_Span(match.group(1), index, end))
        index = end + 1
    return spans


def _parse(body: list[str], name: str, line_number: int) -> dict[str, Any]:
    raw = "\n".join(body)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StateInvalid(
            [
                Finding(
                    "BLOCK_MALFORMED",
                    SEVERITY_ERROR,
                    name,
                    f"JSON in research:{name} block is invalid at line {line_number + exc.lineno}: {exc.msg}",
                )
            ]
        ) from exc
    if not isinstance(parsed, dict):
        raise StateInvalid(
            [Finding("BLOCK_NOT_OBJECT", SEVERITY_ERROR, name, "block JSON must be an object")]
        )
    return parsed
