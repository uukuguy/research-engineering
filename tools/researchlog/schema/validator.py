"""A deliberately small JSON Schema subset, with no third-party dependency.

`jsonschema` is not available — the tool must be copyable into any repository with no
install step — so this module implements only the keywords the four canonical schemas
actually use.

The important property is not completeness, it is **loudness**. A schema file that
reaches for an unimplemented keyword would otherwise enforce nothing and say nothing,
which is exactly the class of silent failure this system is built to eliminate. So
schema documents are checked against `SUPPORTED_KEYWORDS` at load time and rejected if
they use anything else.

Conditional requirements (for example "`surrogate_contract` is mandatory when the
evidence level falls short of the target") are deliberately **not** expressed here.
Structure lives in the schema; invariants live in `constraints.py`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from researchlog.errors import SEVERITY_ERROR, Finding, StateInvalid

SUPPORTED_KEYWORDS = frozenset(
    {
        # annotations, ignored during checking
        "title",
        "description",
        # assertions
        "type",
        "required",
        "properties",
        "enum",
        "const",
        "items",
        "minItems",
        "pattern",
        "minimum",
        "maximum",
        "additionalProperties",
    }
)

_TYPE_CHECKS: dict[str, Any] = {
    "object": lambda v: isinstance(v, Mapping),
    "array": lambda v: isinstance(v, Sequence) and not isinstance(v, (str, bytes)),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


class SchemaValidator:
    """Structural checker for one schema document."""

    def __init__(self, schema: Mapping[str, Any], *, name: str = "schema") -> None:
        assert_supported_keywords(schema, name=name)
        self.schema = schema
        self.name = name

    def check(self, data: Mapping[str, Any]) -> list[Finding]:
        findings: list[Finding] = []
        _check_node(data, self.schema, path="$", schema_name=self.name, out=findings)
        return findings


def load_schema(path: Path) -> SchemaValidator:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StateInvalid([Finding("SCHEMA_UNREADABLE", SEVERITY_ERROR, str(path), str(exc))]) from exc
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StateInvalid(
            [Finding("SCHEMA_MALFORMED", SEVERITY_ERROR, str(path), f"line {exc.lineno}: {exc.msg}")]
        ) from exc
    return SchemaValidator(document, name=path.name)


def assert_supported_keywords(node: Any, *, name: str, path: str = "$") -> None:
    """Walk a schema document and refuse any keyword this validator would ignore."""
    if isinstance(node, Mapping):
        for key, value in node.items():
            if key in ("properties",):
                for prop_name, prop_schema in value.items():
                    assert_supported_keywords(prop_schema, name=name, path=f"{path}.properties.{prop_name}")
                continue
            if key not in SUPPORTED_KEYWORDS:
                raise StateInvalid(
                    [
                        Finding(
                            "SCHEMA_KEYWORD_UNSUPPORTED",
                            SEVERITY_ERROR,
                            f"{name}{path}",
                            f"keyword {key!r} is not implemented by this validator, "
                            f"so it would enforce nothing silently",
                            f"supported: {', '.join(sorted(SUPPORTED_KEYWORDS))}",
                        )
                    ]
                )
            if key == "items":
                assert_supported_keywords(value, name=name, path=f"{path}.items")
    elif isinstance(node, Sequence) and not isinstance(node, (str, bytes)):
        for index, item in enumerate(node):
            assert_supported_keywords(item, name=name, path=f"{path}[{index}]")


def _check_node(
    value: Any,
    schema: Mapping[str, Any],
    *,
    path: str,
    schema_name: str,
    out: list[Finding],
) -> None:
    if "const" in schema and value != schema["const"]:
        out.append(_fail(path, schema_name, f"must equal {schema['const']!r}, got {value!r}"))
        return

    if "enum" in schema and value not in schema["enum"]:
        allowed = ", ".join(repr(option) for option in schema["enum"])
        out.append(_fail(path, schema_name, f"must be one of [{allowed}], got {value!r}"))
        return

    if "type" in schema and not _type_matches(value, schema["type"]):
        out.append(_fail(path, schema_name, f"expected {_type_label(schema['type'])}, got {_type_of(value)}"))
        return

    if isinstance(value, Mapping):
        _check_object(value, schema, path=path, schema_name=schema_name, out=out)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        _check_array(value, schema, path=path, schema_name=schema_name, out=out)
    elif isinstance(value, str):
        _check_string(value, schema, path=path, schema_name=schema_name, out=out)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        _check_number(value, schema, path=path, schema_name=schema_name, out=out)


def _check_object(
    value: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    path: str,
    schema_name: str,
    out: list[Finding],
) -> None:
    for key in schema.get("required", []):
        if key not in value:
            out.append(_fail(f"{path}.{key}", schema_name, "required field is missing"))

    properties = schema.get("properties", {})
    for key, sub_schema in properties.items():
        if key in value:
            _check_node(value[key], sub_schema, path=f"{path}.{key}", schema_name=schema_name, out=out)

    extra = schema.get("additionalProperties")
    if extra is False:
        for key in value:
            if key not in properties:
                out.append(
                    _fail(
                        f"{path}.{key}",
                        schema_name,
                        "unexpected field (additionalProperties is false)",
                    )
                )
    elif isinstance(extra, Mapping):
        for key, item in value.items():
            if key not in properties:
                _check_node(item, extra, path=f"{path}.{key}", schema_name=schema_name, out=out)


def _check_array(
    value: Sequence[Any],
    schema: Mapping[str, Any],
    *,
    path: str,
    schema_name: str,
    out: list[Finding],
) -> None:
    if "minItems" in schema and len(value) < schema["minItems"]:
        out.append(_fail(path, schema_name, f"needs at least {schema['minItems']} items, has {len(value)}"))
    item_schema = schema.get("items")
    if isinstance(item_schema, Mapping):
        for index, item in enumerate(value):
            _check_node(item, item_schema, path=f"{path}[{index}]", schema_name=schema_name, out=out)


def _check_string(
    value: str,
    schema: Mapping[str, Any],
    *,
    path: str,
    schema_name: str,
    out: list[Finding],
) -> None:
    if "pattern" in schema and not re.search(schema["pattern"], value):
        out.append(_fail(path, schema_name, f"{value!r} does not match pattern {schema['pattern']!r}"))


def _check_number(
    value: float,
    schema: Mapping[str, Any],
    *,
    path: str,
    schema_name: str,
    out: list[Finding],
) -> None:
    if "minimum" in schema and value < schema["minimum"]:
        out.append(_fail(path, schema_name, f"{value} is below minimum {schema['minimum']}"))
    if "maximum" in schema and value > schema["maximum"]:
        out.append(_fail(path, schema_name, f"{value} is above maximum {schema['maximum']}"))


def _type_matches(value: Any, declared: Any) -> bool:
    names = declared if isinstance(declared, list) else [declared]
    return any(_TYPE_CHECKS.get(name, _accept_anything)(value) for name in names)


def _accept_anything(value: Any) -> bool:
    return True


def _type_label(declared: Any) -> str:
    return " or ".join(declared) if isinstance(declared, list) else str(declared)


def _type_of(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, str):
        return "string"
    if isinstance(value, Sequence):
        return "array"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return type(value).__name__


def _fail(path: str, schema_name: str, message: str) -> Finding:
    return Finding("SCHEMA_VIOLATION", SEVERITY_ERROR, f"{schema_name}{path}", message)
