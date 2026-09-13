"""Read-only views over raw documents, with unknown fields preserved.

This module exists to prevent one specific bug. The obvious way to model a record is a
dataclass; the obvious way to write it back is `asdict()`. Together they delete every
field the current version of the tool does not know about — silently, on the first
write, destroying a newer tool's state or another client's annotations.

So a `Record` is a thin wrapper around the dict that was actually loaded. Nothing here
reconstructs the document from typed fields. Writes mutate the original dict, keeping
key order and every unknown key exactly as they were.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any


class Record:
    """A dotted-path view over a raw document. Unknown keys survive every mutation."""

    __slots__ = ("_raw", "_path")

    def __init__(self, raw: dict[str, Any], path: Path) -> None:
        self._raw = raw
        self._path = path

    @property
    def raw(self) -> dict[str, Any]:
        return self._raw

    @property
    def path(self) -> Path:
        return self._path

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self._raw
        for part in dotted.split("."):
            if not isinstance(node, Mapping) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, dotted: str, value: Any) -> None:
        """Set a dotted path, creating intermediate objects. Other keys are untouched."""
        parts = dotted.split(".")
        node: dict[str, Any] = self._raw
        for part in parts[:-1]:
            child = node.get(part)
            if not isinstance(child, dict):
                child = {}
                node[part] = child
            node = child
        node[parts[-1]] = value

    def delete(self, dotted: str) -> bool:
        parts = dotted.split(".")
        node: Any = self._raw
        for part in parts[:-1]:
            if not isinstance(node, Mapping) or part not in node:
                return False
            node = node[part]
        if isinstance(node, dict) and parts[-1] in node:
            del node[parts[-1]]
            return True
        return False

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Record({self._path.name}, keys={sorted(self._raw)})"


def flatten(prefix: str, values: Mapping[str, Any]) -> dict[str, Any]:
    """Turn a nested mapping into dotted keys, so predicates can be flat lookups.

    `{"sim_physics_hz": 30}` under prefix "env" becomes `{"env.sim_physics_hz": 30}`.
    """
    flat: dict[str, Any] = {}
    for key, value in values.items():
        path = f"{prefix}.{key}"
        if isinstance(value, Mapping):
            flat.update(flatten(path, value))
        else:
            flat[path] = value
    return flat
