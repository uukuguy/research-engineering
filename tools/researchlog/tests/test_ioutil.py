"""Crash-safe writes and honest recovery.

These tests exist because a half-written ACTIVE.json is precisely the failure the
whole system is built to prevent.
"""

from __future__ import annotations

import json
import os
import unittest
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest import mock

from researchlog import ioutil
from researchlog.errors import SEVERITY_ERROR, Finding, StateInvalid

CANONICAL = {"schema_version": "1.0", "status": "idle", "z_last": 1, "a_first": 2}


class _Rejecting:
    def check(self, data: Mapping[str, Any]) -> list[Finding]:
        return [Finding("NOPE", SEVERITY_ERROR, "test", "rejected by test validator")]


class _Accepting:
    def check(self, data: Mapping[str, Any]) -> list[Finding]:
        return []


class WriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "ACTIVE.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_round_trip_preserves_key_order_and_unicode(self) -> None:
        """Key order is state, and Chinese must stay readable rather than \\uXXXX."""
        payload = {"z_last": 1, "a_first": 2, "note": "不要动 planner 的 recovery 分支"}
        ioutil.write_json_atomic(self.path, payload)

        text = self.path.read_text(encoding="utf-8")
        self.assertIn("不要动", text, "Chinese was escaped; source_text loses its purpose")
        self.assertNotIn("\\u", text)
        self.assertEqual(list(json.loads(text)), ["z_last", "a_first", "note"])

    def test_validation_failure_leaves_canonical_untouched_and_no_residue(self) -> None:
        ioutil.write_json_atomic(self.path, CANONICAL)
        before = self.path.read_bytes()

        with self.assertRaises(StateInvalid):
            ioutil.write_json_atomic(self.path, {"schema_version": "1.0"}, validator=_Rejecting())

        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(self.path.with_name(self.path.name + ioutil.TMP_SUFFIX).exists())

    def test_uses_os_replace_not_shutil_move(self) -> None:
        """shutil.move degrades to copy+unlink across filesystems, which is not atomic."""
        calls: list[tuple[str, str]] = []
        real_replace = os.replace

        def recording_replace(src: str, dst: str) -> None:
            calls.append((str(src), str(dst)))
            real_replace(src, dst)

        with mock.patch("os.replace", side_effect=recording_replace):
            with mock.patch("shutil.move", side_effect=AssertionError("used shutil.move")):
                ioutil.write_json_atomic(self.path, CANONICAL)

        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0][0].endswith(ioutil.TMP_SUFFIX))

    def test_tmp_is_fsynced_before_the_rename(self) -> None:
        """fsync must precede the rename; the directory fsync after it is expected."""
        order: list[str] = []
        with mock.patch("os.fsync", side_effect=lambda _fd: order.append("fsync")):
            with mock.patch("os.replace", side_effect=lambda _s, _d: order.append("replace")):
                ioutil.write_json_atomic(self.path, CANONICAL)
        self.assertEqual(order[:2], ["fsync", "replace"])

    def test_canonical_wins_while_usable_then_tmp_takes_over(self) -> None:
        """`.tmp` is uncommitted, so it is a fallback — not a competitor."""
        ioutil.write_json_atomic(self.path, CANONICAL)
        before = self.path.read_bytes()

        with mock.patch("os.replace", side_effect=OSError("power lost")):
            with self.assertRaises(OSError):
                ioutil.write_json_atomic(self.path, {"schema_version": "1.0", "status": "running"})

        self.assertEqual(self.path.read_bytes(), before, "canonical must be untouched")
        tmp = self.path.with_name(self.path.name + ioutil.TMP_SUFFIX)
        self.assertTrue(tmp.exists(), "the interrupted write left its content behind")

        committed = ioutil.load_json_with_recovery(self.path, validator=_Accepting())
        self.assertEqual(committed.source, ioutil.SOURCE_CANONICAL)
        self.assertFalse(committed.recovered)

        self.path.unlink()
        recovered = ioutil.load_json_with_recovery(self.path, validator=_Accepting())
        self.assertEqual(recovered.source, ioutil.SOURCE_TMP)
        self.assertEqual(recovered.data["status"], "running")
        self.assertTrue(recovered.recovered)
        self.assertEqual([f.code for f in recovered.findings], ["RECOVERED_FROM_TMP"])


class ReadTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "ACTIVE.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_canonical_load_reports_no_recovery(self) -> None:
        ioutil.write_json_atomic(self.path, CANONICAL)
        outcome = ioutil.load_json_with_recovery(self.path, validator=_Accepting())
        self.assertEqual(outcome.source, ioutil.SOURCE_CANONICAL)
        self.assertFalse(outcome.recovered)
        self.assertEqual(outcome.data, CANONICAL)

    def test_truncated_json_becomes_a_finding_not_a_traceback(self) -> None:
        self.path.write_text('{"schema_version": "1.0", "stat', encoding="utf-8")
        with self.assertRaises(StateInvalid) as ctx:
            ioutil.load_json_with_recovery(self.path, validator=_Accepting())
        finding = ctx.exception.findings[0]
        self.assertEqual(finding.code, "RECOVERY_REQUIRED")
        self.assertIn("canonical: malformed JSON", finding.message)

    def test_missing_file_reports_every_candidate_tried(self) -> None:
        with self.assertRaises(StateInvalid) as ctx:
            ioutil.load_json_with_recovery(
                self.path, validator=_Accepting(), git_recover=lambda: None
            )
        message = ctx.exception.findings[0].message
        self.assertIn("canonical: not present", message)
        self.assertIn("tmp: not present", message)
        self.assertIn("git: not present", message)

    def test_git_recovery_is_used_last_and_reported(self) -> None:
        self.path.write_text("{ broken", encoding="utf-8")
        outcome = ioutil.load_json_with_recovery(
            self.path,
            validator=_Accepting(),
            git_recover=lambda: json.dumps({"schema_version": "1.0", "status": "idle"}),
        )
        self.assertEqual(outcome.source, ioutil.SOURCE_GIT)
        self.assertEqual([f.code for f in outcome.findings], ["RECOVERED_FROM_GIT"])

    def test_strict_load_raises_state_invalid(self) -> None:
        self.path.write_text("[1, 2, 3]", encoding="utf-8")
        with self.assertRaises(StateInvalid) as ctx:
            ioutil.load_json(self.path)
        self.assertEqual(ctx.exception.findings[0].code, "JSON_NOT_OBJECT")


if __name__ == "__main__":
    unittest.main()
