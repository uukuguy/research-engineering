"""The schema subset validator, version classification, and fenced-block handling."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from researchlog.errors import RefusedByPolicy, StateInvalid
from researchlog.schema import loader, registry, validator


class ValidatorTests(unittest.TestCase):
    def check(self, schema: dict, data: object) -> list[str]:
        return [f.message for f in validator.SchemaValidator(schema).check(data)]

    def test_valid_document_passes(self) -> None:
        schema = {
            "type": "object",
            "required": ["a"],
            "properties": {"a": {"type": "string", "pattern": "^x"}},
        }
        self.assertEqual(self.check(schema, {"a": "xyz"}), [])

    def test_missing_required_field_is_reported_with_its_path(self) -> None:
        schema = {"type": "object", "required": ["a"], "properties": {"a": {"type": "string"}}}
        problems = validator.SchemaValidator(schema, name="s").check({})
        self.assertEqual(problems[0].code, "SCHEMA_VIOLATION")
        self.assertIn("$.a", problems[0].subject)

    def test_type_mismatch_names_both_sides(self) -> None:
        problems = self.check({"type": "object", "properties": {"n": {"type": "integer"}}}, {"n": "3"})
        self.assertEqual(len(problems), 1)
        self.assertIn("expected integer, got string", problems[0])

    def test_booleans_are_not_integers(self) -> None:
        self.assertEqual(
            self.check({"type": "object", "properties": {"n": {"type": "integer"}}}, {"n": True}),
            ["expected integer, got boolean"],
        )

    def test_enum_lists_the_allowed_values(self) -> None:
        problems = self.check({"type": "object", "properties": {"s": {"enum": ["a", "b"]}}}, {"s": "c"})
        self.assertIn("must be one of ['a', 'b']", problems[0])

    def test_nullable_object_skips_its_required_checks_when_null(self) -> None:
        schema = {
            "type": "object",
            "properties": {"s": {"type": ["object", "null"], "required": ["id"], "properties": {"id": {"type": "string"}}}},
        }
        self.assertEqual(self.check(schema, {"s": None}), [])
        self.assertEqual(len(self.check(schema, {"s": {}})), 1)

    def test_enum_accepts_null_when_listed(self) -> None:
        schema = {"type": "object", "properties": {"d": {"enum": ["none", None]}}}
        self.assertEqual(self.check(schema, {"d": None}), [])

    def test_additional_properties_schema_checks_every_unlisted_key(self) -> None:
        """measurements must be a flat scalar map."""
        schema = {
            "type": "object",
            "properties": {"m": {"type": "object", "additionalProperties": {"type": ["string", "number"]}}},
        }
        self.assertEqual(self.check(schema, {"m": {"a": 1, "b": "x"}}), [])
        self.assertEqual(len(self.check(schema, {"m": {"bad": {"nested": 1}}})), 1)

    def test_additional_properties_false_rejects_unknown_keys(self) -> None:
        schema = {"type": "object", "properties": {"a": {"type": "string"}}, "additionalProperties": False}
        self.assertEqual(len(self.check(schema, {"b": 1})), 1)

    def test_unknown_keys_are_allowed_by_default(self) -> None:
        """Forward compatibility: an unlisted field must survive, not be rejected."""
        schema = {"type": "object", "properties": {"a": {"type": "string"}}}
        self.assertEqual(self.check(schema, {"a": "x", "x_future_field": {"anything": 1}}), [])


class KeywordGuardTests(unittest.TestCase):
    def test_unsupported_keyword_is_rejected_loudly(self) -> None:
        """A keyword we do not implement would enforce nothing and say nothing."""
        with self.assertRaises(StateInvalid) as ctx:
            validator.SchemaValidator({"type": "object", "oneOf": [{"type": "string"}]})
        self.assertEqual(ctx.exception.findings[0].code, "SCHEMA_KEYWORD_UNSUPPORTED")

    def test_unsupported_keyword_nested_under_items_is_caught(self) -> None:
        schema = {"type": "array", "items": {"type": "string", "format": "date-time"}}
        with self.assertRaises(StateInvalid):
            validator.SchemaValidator(schema)

    def test_unsupported_keyword_inside_properties_is_caught(self) -> None:
        schema = {"type": "object", "properties": {"a": {"type": "string", "if": {}}}}
        with self.assertRaises(StateInvalid):
            validator.SchemaValidator(schema)

    def test_every_shipped_schema_uses_only_supported_keywords(self) -> None:
        """Guards against a schema silently under-enforcing after an edit."""
        found = sorted(registry.schema_dir().glob("*.schema.json"))
        self.assertEqual(len(found), 4, f"expected four schemas, found {[p.name for p in found]}")
        for path in found:
            with self.subTest(schema=path.name):
                validator.load_schema(path)  # raises if any keyword is unsupported

    def test_shipped_schemas_are_valid_json(self) -> None:
        for path in sorted(registry.schema_dir().glob("*.schema.json")):
            with self.subTest(schema=path.name):
                json.loads(path.read_text(encoding="utf-8"))


class RegistryTests(unittest.TestCase):
    def test_classify_current(self) -> None:
        self.assertEqual(registry.classify("active", {"schema_version": "1.0"})[0], registry.CLASS_CURRENT)

    def test_classify_older_minor_carries_no_migration_burden(self) -> None:
        with mock.patch.dict(registry.CURRENT_VERSIONS, {"active": "1.4"}):
            klass, detail = registry.classify("active", {"schema_version": "1.2"})
        self.assertEqual(klass, registry.CLASS_OLDER)
        self.assertIn("minor", detail)

    def test_classify_older_major_is_flagged_as_such(self) -> None:
        with mock.patch.dict(registry.CURRENT_VERSIONS, {"active": "3.0"}):
            klass, detail = registry.classify("active", {"schema_version": "1.0"})
        self.assertEqual(klass, registry.CLASS_OLDER)
        self.assertIn("older major version", detail)

    def test_classify_newer(self) -> None:
        klass, detail = registry.classify("active", {"schema_version": "2.0"})
        self.assertEqual(klass, registry.CLASS_NEWER)
        self.assertIn("newer than supported", detail)

    def test_classify_invalid(self) -> None:
        self.assertEqual(registry.classify("active", {})[0], registry.CLASS_INVALID)
        self.assertEqual(registry.classify("active", {"schema_version": "banana"})[0], registry.CLASS_INVALID)

    def test_write_to_a_newer_document_is_refused(self) -> None:
        with self.assertRaises(RefusedByPolicy) as ctx:
            registry.require_writable("active", Path("research/ACTIVE.json"), {"schema_version": "2.0"})
        self.assertEqual(ctx.exception.finding.code, "SCHEMA_NEWER_REFUSED")

    def test_write_to_a_current_document_is_allowed(self) -> None:
        registry.require_writable("active", Path("x"), {"schema_version": "1.0"})

    def test_major_downgrade_without_a_migration_is_refused(self) -> None:
        with self.assertRaises(RefusedByPolicy) as ctx:
            registry.require_writable("evidence", Path("x"), {"schema_version": "0.9"})
        self.assertEqual(ctx.exception.finding.code, "SCHEMA_MIGRATION_MISSING")


class BlockTests(unittest.TestCase):
    DOC = """# Findings

Some Chinese prose for the architect.

```json research:findings
{"entries": [{"id": "FND-001"}]}
```

Trailing notes.
"""

    def test_extract_one_block(self) -> None:
        blocks = loader.extract_blocks(self.DOC)
        self.assertEqual(blocks["findings"][0]["entries"][0]["id"], "FND-001")

    def test_repeated_blocks_are_collected_in_order(self) -> None:
        text = (
            "```json research:signal\n{\"n\": 1}\n```\n"
            "prose between\n"
            "```json research:signal\n{\"n\": 2}\n```\n"
        )
        self.assertEqual([b["n"] for b in loader.extract_blocks(text)["signal"]], [1, 2])

    def test_find_block_rejects_a_duplicated_singleton(self) -> None:
        text = "```json research:findings\n{}\n```\n```json research:findings\n{}\n```\n"
        with self.assertRaises(StateInvalid) as ctx:
            loader.find_block(text, "findings")
        self.assertEqual(ctx.exception.findings[0].code, "BLOCK_DUPLICATED")

    def test_unterminated_fence_is_reported(self) -> None:
        with self.assertRaises(StateInvalid) as ctx:
            loader.extract_blocks("```json research:findings\n{\"a\": 1}\n")
        self.assertEqual(ctx.exception.findings[0].code, "BLOCK_UNTERMINATED")

    def test_malformed_json_in_a_block_names_the_line(self) -> None:
        with self.assertRaises(StateInvalid) as ctx:
            loader.extract_blocks("```json research:findings\n{\"a\": }\n```\n")
        self.assertEqual(ctx.exception.findings[0].code, "BLOCK_MALFORMED")

    def test_replace_block_leaves_the_prose_untouched(self) -> None:
        updated = loader.replace_block(self.DOC, "findings", {"entries": [{"id": "FND-002"}]})
        self.assertIn("Some Chinese prose for the architect.", updated)
        self.assertIn("Trailing notes.", updated)
        self.assertIn("FND-002", updated)
        self.assertNotIn("FND-001", updated)

    def test_render_then_extract_round_trips(self) -> None:
        payload = {"entries": [{"id": "FND-003", "note": "不要动 planner"}]}
        text = "# x\n\n" + loader.render_block("findings", payload)
        self.assertEqual(loader.extract_blocks(text)["findings"][0], payload)

    def test_replace_missing_block_is_an_error(self) -> None:
        with self.assertRaises(StateInvalid):
            loader.replace_block(self.DOC, "boundaries", {})


if __name__ == "__main__":
    unittest.main()
