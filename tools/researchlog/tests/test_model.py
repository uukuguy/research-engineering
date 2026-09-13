"""Field preservation: a read-modify-write must not delete what it does not know."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from researchlog import ioutil
from researchlog.model import Record, flatten


class RecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw: dict = {
            "schema_version": "1.0",
            "block": {"id": "RB-024", "max_tokens": None},
            "x_architect_note": {"added_by": "a newer tool", "keep": [1, 2, 3]},
        }
        self.record = Record(self.raw, Path("research/ACTIVE.json"))

    def test_get_walks_dotted_paths(self) -> None:
        self.assertEqual(self.record.get("block.id"), "RB-024")
        self.assertIsNone(self.record.get("block.max_tokens"))
        self.assertEqual(self.record.get("nope.deep.path", "fallback"), "fallback")

    def test_set_creates_intermediate_objects(self) -> None:
        self.record.set("a.b.c", 7)
        self.assertEqual(self.raw["a"]["b"]["c"], 7)

    def test_set_preserves_unknown_fields(self) -> None:
        self.record.set("block.id", "RB-025")
        self.assertEqual(self.raw["x_architect_note"], {"added_by": "a newer tool", "keep": [1, 2, 3]})

    def test_delete_preserves_unknown_fields(self) -> None:
        self.assertTrue(self.record.delete("block.max_tokens"))
        self.assertNotIn("max_tokens", self.raw["block"])
        self.assertIn("x_architect_note", self.raw)

    def test_delete_of_absent_path_reports_false(self) -> None:
        self.assertFalse(self.record.delete("block.nope"))
        self.assertFalse(self.record.delete("nope.deep.path"))

    def test_unknown_fields_survive_a_full_write_cycle(self) -> None:
        """The bug this module exists to prevent, exercised end to end."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ACTIVE.json"
            ioutil.write_json_atomic(path, self.raw)

            reloaded = Record(ioutil.load_json(path), path)
            reloaded.set("block.id", "RB-099")
            ioutil.write_json_atomic(path, reloaded.raw)

            final = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(final["block"]["id"], "RB-099")
            self.assertEqual(
                final["x_architect_note"],
                {"added_by": "a newer tool", "keep": [1, 2, 3]},
                "an unknown field was deleted by a read-modify-write cycle",
            )

    def test_key_order_is_preserved_across_a_cycle(self) -> None:
        self.record.set("schema_version", "1.0")
        self.assertEqual(list(self.raw), ["schema_version", "block", "x_architect_note"])


class FlattenTests(unittest.TestCase):
    def test_flat_map_gets_the_prefix(self) -> None:
        self.assertEqual(flatten("env", {"sim_physics_hz": 30}), {"env.sim_physics_hz": 30})

    def test_nested_maps_become_dotted_keys(self) -> None:
        got = flatten("env", {"evaluator": {"version": "eval-v3"}, "mode": "fast"})
        self.assertEqual(got, {"env.evaluator.version": "eval-v3", "env.mode": "fast"})

    def test_lists_and_nulls_stay_whole(self) -> None:
        got = flatten("code", {"diff_sha256": None, "tags": ["a", "b"]})
        self.assertEqual(got, {"code.diff_sha256": None, "code.tags": ["a", "b"]})


if __name__ == "__main__":
    unittest.main()
