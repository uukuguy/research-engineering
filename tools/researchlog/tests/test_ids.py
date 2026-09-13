"""ID minting: pure generation, and exclusive-create as the only lock."""

from __future__ import annotations

import re
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from researchlog import ids
from researchlog.errors import IdSpaceExhausted

FIXED = datetime(2026, 9, 11, 10, 15, 30, tzinfo=timezone.utc)
ID_RE = re.compile(r"^EV-\d{8}T\d{6}Z-[0-9a-f]+$")


def _rand(value: str):
    return lambda _nbytes: value


class MintTests(unittest.TestCase):
    def test_format_is_kind_stamp_suffix(self) -> None:
        got = ids.mint("evidence", now=lambda: FIXED, rand=_rand("a7f3"))
        self.assertEqual(got, "EV-20260911T101530Z-a7f3")
        self.assertRegex(got, ID_RE)

    def test_every_kind_has_a_prefix(self) -> None:
        for kind in ("evidence", "experiment", "hypothesis", "finding", "block", "session", "environment"):
            self.assertTrue(ids.mint(kind, now=lambda: FIXED, rand=_rand("0000")))

    def test_unknown_kind_lists_the_options(self) -> None:
        with self.assertRaises(KeyError) as ctx:
            ids.mint("sandwich", now=lambda: FIXED, rand=_rand("0000"))
        self.assertIn("evidence", str(ctx.exception))

    def test_odd_hexlen_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ids.mint("evidence", hexlen=3, now=lambda: FIXED, rand=_rand("00"))

    def test_mint_never_touches_the_filesystem(self) -> None:
        """The executable encoding of 'no read-then-increment anywhere'."""
        boom = AssertionError("mint consulted the filesystem; IDs must not be counted")
        with mock.patch.object(Path, "exists", side_effect=boom):
            with mock.patch.object(Path, "glob", side_effect=boom):
                with mock.patch.object(Path, "iterdir", side_effect=boom):
                    got = ids.mint("evidence", now=lambda: FIXED, rand=_rand("a7f3"))
        self.assertEqual(got, "EV-20260911T101530Z-a7f3")

    def test_clock_rewind_still_yields_a_distinct_id(self) -> None:
        later = ids.mint("evidence", now=lambda: FIXED, rand=_rand("aaaa"))
        earlier = ids.mint("evidence", now=lambda: FIXED - timedelta(hours=1), rand=_rand("bbbb"))
        self.assertNotEqual(later, earlier)


class ClaimTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.ledger = Path(self._tmp.name) / "ledger"
        self.path_for = lambda eid: self.ledger / f"{eid}.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_claim_creates_an_empty_reservation(self) -> None:
        eid, path = ids.claim_new("evidence", self.path_for, now=lambda: FIXED, rand=_rand("aaaa"))
        self.assertEqual(eid, "EV-20260911T101530Z-aaaa")
        self.assertTrue(path.exists())
        self.assertEqual(path.read_text(encoding="utf-8"), "")

    def test_collision_retries_and_preserves_the_existing_file(self) -> None:
        """A taken ID must never be overwritten, and the retry must find a new one."""
        taken = self.path_for("EV-20260911T101530Z-aaaa")
        taken.parent.mkdir(parents=True, exist_ok=True)
        taken.write_text("existing evidence\n", encoding="utf-8")

        suffixes = iter(["aaaa", "aaaa", "bbbb"])
        eid, path = ids.claim_new(
            "evidence", self.path_for, now=lambda: FIXED, rand=lambda _n: next(suffixes)
        )

        self.assertEqual(eid, "EV-20260911T101530Z-bbbb")
        self.assertEqual(taken.read_text(encoding="utf-8"), "existing evidence\n")
        self.assertNotEqual(path, taken)

    def test_suffix_grows_before_giving_up(self) -> None:
        """A degenerate RNG must still terminate, by widening rather than spinning."""
        seen: list[int] = []

        def always_colliding(nbytes: int) -> str:
            seen.append(nbytes)
            return "ab" * nbytes

        lying = lambda eid: self.path_for(eid)  # noqa: E731 - every path "exists"
        with mock.patch.object(Path, "mkdir"):
            with mock.patch("researchlog.ids.os.open", side_effect=FileExistsError):
                with self.assertRaises(IdSpaceExhausted):
                    ids.claim_new("evidence", lying, attempts=2, now=lambda: FIXED, rand=always_colliding)
        self.assertIn(3, seen, "expected the suffix to grow to 6 hex chars before giving up")

    def test_input_id_validation_is_lenient(self) -> None:
        self.assertTrue(ids.is_valid_id("EXP-0142"))  # hand-written, still legal
        self.assertTrue(ids.is_valid_id("EV-20260911T101530Z-a7f3"))
        self.assertFalse(ids.is_valid_id("exp-0142"))  # lowercase prefix
        self.assertFalse(ids.is_valid_id("EXP0142"))  # no separator


if __name__ == "__main__":
    unittest.main()
