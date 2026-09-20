"""Schema versions, compatibility classification, and the write guard.

The rule that matters most here is asymmetric: a document written by a **newer**
version of the tool may be read, but must never be overwritten. Silently rewriting a
format you do not understand is how a state system eats its own history.

    CURRENT  → read and write normally
    OLDER    → read and write; unknown fields are preserved verbatim
    NEWER    → read (with a warning); any write is refused and the file is untouched
    INVALID  → neither
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

from researchlog.errors import (
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    Finding,
    RefusedByPolicy,
    StateInvalid,
)
from researchlog.schema.validator import SchemaValidator, load_schema

CLASS_CURRENT = "CURRENT"
CLASS_OLDER = "OLDER"
CLASS_NEWER = "NEWER"
CLASS_INVALID = "INVALID"

CURRENT_VERSIONS: dict[str, str] = {
    "active": "1.0",
    "evidence": "1.0",
    "manifest": "1.0",
    "findings-entry": "1.0",
    "current": "1.0",
    "environment": "1.0",
    "boundaries": "1.0",
    "references": "1.0",
}

# Major-version migrations, keyed by (kind, from_major, to_major). A downgrade across
# a major version without an entry here is refused rather than guessed at.
MIGRATIONS: dict[tuple[str, int, int], Any] = {}


def schema_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "schemas"


@lru_cache(maxsize=None)
def load_validator(kind: str) -> SchemaValidator:
    if kind not in CURRENT_VERSIONS:
        raise KeyError(f"unknown schema kind {kind!r}; expected one of {sorted(CURRENT_VERSIONS)}")
    return load_schema(schema_dir() / f"{kind}.schema.json")


def classify(kind: str, raw: Mapping[str, Any]) -> tuple[str, str]:
    """Return (class, detail) for a document of the given kind."""
    version = raw.get("schema_version")
    if not isinstance(version, str):
        return CLASS_INVALID, "schema_version is missing or not a string"

    parsed = _parse(version)
    if parsed is None:
        return CLASS_INVALID, f"schema_version {version!r} is not major.minor"

    current = _parse(CURRENT_VERSIONS[kind])
    assert current is not None
    if parsed == current:
        return CLASS_CURRENT, version
    if parsed > current:
        return CLASS_NEWER, f"{version} is newer than supported {CURRENT_VERSIONS[kind]}"
    if parsed[0] == current[0]:
        return CLASS_OLDER, f"{version} differs from {CURRENT_VERSIONS[kind]} in minor version only"
    return CLASS_OLDER, f"{version} is an older major version than {CURRENT_VERSIONS[kind]}"


def require_writable(kind: str, path: Path, raw: Mapping[str, Any]) -> None:
    """Refuse any write to a document this tool may not safely rewrite."""
    klass, detail = classify(kind, raw)
    if klass == CLASS_NEWER:
        raise RefusedByPolicy(
            "SCHEMA_NEWER_REFUSED",
            f"{path} declares {detail}; refusing to overwrite it",
            "upgrade the tool, or move the file aside deliberately — this tool will not "
            "guess at fields it does not understand",
        )
    if klass == CLASS_INVALID:
        raise StateInvalid([Finding("SCHEMA_VERSION_INVALID", SEVERITY_ERROR, str(path), detail)])
    if klass == CLASS_OLDER:
        major_now = _parse(CURRENT_VERSIONS[kind])
        major_then = _parse(str(raw["schema_version"]))
        assert major_now is not None and major_then is not None
        if major_then[0] < major_now[0] and (kind, major_then[0], major_now[0]) not in MIGRATIONS:
            raise RefusedByPolicy(
                "SCHEMA_MIGRATION_MISSING",
                f"{path} is major version {major_then[0]} and no migration to "
                f"{major_now[0]} is registered",
                "register a migration that only adds or renames keys, preserving everything else",
            )


def version_findings(kind: str, document: Mapping[str, Any], *, where: str) -> list[Finding]:
    """Report a canonical document written by a different version of this tool.

    Reading a newer document is allowed and writing it is refused — but neither of those is
    a *report*. `validate` used to exit 0 on a document it could not fully interpret, which
    is the same silence the rest of this tool exists to remove: the refusal only arrives
    when someone tries to write, by which point a session has already acted on its reading.
    """
    klass, detail = classify(kind, document)
    if klass == CLASS_CURRENT:
        return []
    if klass == CLASS_INVALID:
        return [
            Finding(
                "SCHEMA_VERSION_INVALID",
                SEVERITY_ERROR,
                where,
                detail,
                "a canonical document must declare a major.minor schema_version",
            )
        ]
    if klass == CLASS_NEWER:
        return [
            Finding(
                "SCHEMA_NEWER",
                SEVERITY_WARNING,
                where,
                f"{detail}; this tool may not understand all of it",
                "writes to it are refused; upgrade the tool, or move the file aside deliberately",
            )
        ]
    return [
        Finding(
            "SCHEMA_OLDER",
            SEVERITY_WARNING,
            where,
            f"{detail}; read and written conservatively, unknown fields preserved",
        )
    ]


def schema_versions_in_use() -> dict[str, str]:
    return dict(CURRENT_VERSIONS)


def _parse(version: str) -> tuple[int, int] | None:
    parts = version.split(".")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None
