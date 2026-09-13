"""Schema loading, version classification, and fenced-block extraction."""

from __future__ import annotations

from researchlog.schema.loader import (
    extract_blocks,
    find_block,
    render_block,
    replace_block,
    require_block,
)
from researchlog.schema.registry import (
    CLASS_CURRENT,
    CLASS_INVALID,
    CLASS_NEWER,
    CLASS_OLDER,
    CURRENT_VERSIONS,
    classify,
    load_validator,
    require_writable,
    schema_dir,
    schema_versions_in_use,
)
from researchlog.schema.validator import SUPPORTED_KEYWORDS, SchemaValidator, load_schema

__all__ = [
    "CLASS_CURRENT",
    "CLASS_INVALID",
    "CLASS_NEWER",
    "CLASS_OLDER",
    "CURRENT_VERSIONS",
    "SUPPORTED_KEYWORDS",
    "SchemaValidator",
    "classify",
    "extract_blocks",
    "find_block",
    "load_schema",
    "load_validator",
    "render_block",
    "replace_block",
    "require_block",
    "require_writable",
    "schema_dir",
    "schema_versions_in_use",
]
