"""The invalidated_if mini-language: parsing, evaluation, and failure posture."""

from __future__ import annotations

import unittest

from researchlog import predicate
from researchlog.errors import PredicateSyntaxError

NOW = {
    "env.sim_physics_hz": 60,
    "env.evaluator.version": "eval-v3",
    "inputs.replay_suite": "recovery-12@sha256:abcd",
    "code.commit": "83ab21",
    "code.diff_sha256": None,
}
THEN = {
    "env.sim_physics_hz": 30,
    "env.evaluator.version": "eval-v3",
    "inputs.replay_suite": "recovery-12@sha256:abcd",
    "code.commit": "83ab21",
    "code.diff_sha256": None,
}


class ParseTests(unittest.TestCase):
    def test_equality_predicate(self) -> None:
        got = predicate.parse("env.sim_physics_hz != 30")
        self.assertEqual((got.path, got.op, got.literal), ("env.sim_physics_hz", "!=", 30))

    def test_changed_predicate_has_no_operator(self) -> None:
        got = predicate.parse("inputs.replay_suite changed")
        self.assertEqual((got.path, got.op, got.literal), ("inputs.replay_suite", None, None))

    def test_nested_key_path(self) -> None:
        got = predicate.parse("env.evaluator.version == eval-v3")
        self.assertEqual(got.path, "env.evaluator.version")
        self.assertEqual(got.literal, "eval-v3")

    def test_list_literal(self) -> None:
        got = predicate.parse("env.mode in [fast, safe]")
        self.assertEqual(got.literal, ["fast", "safe"])

    def test_rejects_missing_namespace(self) -> None:
        with self.assertRaises(PredicateSyntaxError) as ctx:
            predicate.parse("sim_physics_hz != 30")
        self.assertIn("no namespace", str(ctx.exception))

    def test_rejects_unknown_namespace(self) -> None:
        with self.assertRaises(PredicateSyntaxError) as ctx:
            predicate.parse("evaluator.version != eval-v3")
        self.assertIn("unknown namespace", str(ctx.exception))

    def test_rejects_compound_expression_with_a_usable_hint(self) -> None:
        """No `and`, no parentheses. Two conditions means two predicates."""
        with self.assertRaises(PredicateSyntaxError) as ctx:
            predicate.parse("env.a != 1 and env.b != 2")
        message = str(ctx.exception)
        self.assertIn("no and/or", message)
        self.assertIn("write two entries", message)

    def test_rejects_a_parenthesised_expression(self) -> None:
        with self.assertRaises(PredicateSyntaxError) as ctx:
            predicate.parse("env.a != (1)")
        self.assertIn("compound", str(ctx.exception))

    def test_rejects_unquoted_value_with_spaces(self) -> None:
        with self.assertRaises(PredicateSyntaxError) as ctx:
            predicate.parse("env.label != two words")
        self.assertIn("double quotes", str(ctx.exception))

    def test_quoted_value_with_spaces_is_accepted(self) -> None:
        self.assertEqual(predicate.parse('env.label != "two words"').literal, "two words")

    def test_rejects_operator_without_a_value(self) -> None:
        with self.assertRaises(PredicateSyntaxError):
            predicate.parse("env.a !=")

    def test_rejects_empty_input(self) -> None:
        with self.assertRaises(PredicateSyntaxError):
            predicate.parse("   ")


class EvaluateTests(unittest.TestCase):
    """The convention throughout: a predicate being TRUE means the evidence is invalid."""

    def verdict(self, text: str, *, now=None, then=None) -> str:
        return predicate.evaluate(predicate.parse(text), now=now or NOW, then=then or THEN).verdict

    def test_inequality_fires_when_values_differ(self) -> None:
        self.assertEqual(self.verdict("env.sim_physics_hz != 30"), predicate.VERDICT_INVALIDATED)

    def test_inequality_holds_when_values_match(self) -> None:
        self.assertEqual(self.verdict("env.sim_physics_hz != 60"), predicate.VERDICT_VALID)

    def test_equality_fires_when_values_match(self) -> None:
        self.assertEqual(self.verdict("env.sim_physics_hz == 60"), predicate.VERDICT_INVALIDATED)

    def test_changed_fires_in_the_forward_direction(self) -> None:
        self.assertEqual(self.verdict("env.sim_physics_hz changed"), predicate.VERDICT_INVALIDATED)

    def test_changed_is_quiet_when_nothing_moved(self) -> None:
        self.assertEqual(self.verdict("code.commit changed"), predicate.VERDICT_VALID)

    def test_numeric_string_matches_a_number(self) -> None:
        """A probe writing "30" must not silently fail to invalidate."""
        now = dict(NOW, **{"env.sim_physics_hz": "30"})
        self.assertEqual(self.verdict("env.sim_physics_hz != 30", now=now), predicate.VERDICT_VALID)

    def test_number_matches_a_numeric_string_literal(self) -> None:
        self.assertEqual(self.verdict('env.sim_physics_hz != "60"'), predicate.VERDICT_VALID)

    def test_coercion_does_not_mask_a_real_difference(self) -> None:
        now = dict(NOW, **{"env.sim_physics_hz": "60"})
        self.assertEqual(self.verdict("env.sim_physics_hz != 30", now=now), predicate.VERDICT_INVALIDATED)

    def test_absent_path_is_unresolved_and_does_not_invalidate(self) -> None:
        """Failing open: 'could not check' must not be reported as 'invalid'."""
        result = predicate.evaluate(
            predicate.parse("env.never_recorded != 1"), now=NOW, then=THEN
        )
        self.assertEqual(result.verdict, predicate.VERDICT_UNRESOLVED)
        self.assertFalse(result.invalidates)
        self.assertIn("absent from the current fingerprint", result.reason)

    def test_changed_with_no_recorded_value_is_unresolved(self) -> None:
        result = predicate.evaluate(
            predicate.parse("env.fresh_key changed"),
            now=dict(NOW, **{"env.fresh_key": 1}),
            then=THEN,
        )
        self.assertEqual(result.verdict, predicate.VERDICT_UNRESOLVED)

    def test_incomparable_types_are_unresolved_not_invalidated(self) -> None:
        now = dict(NOW, **{"env.sim_physics_hz": {"nested": 1}})
        result = predicate.evaluate(predicate.parse("env.sim_physics_hz != 30"), now=now, then=THEN)
        self.assertEqual(result.verdict, predicate.VERDICT_UNRESOLVED)
        self.assertFalse(result.invalidates)

    def test_in_operator_matches_a_list_member(self) -> None:
        self.assertEqual(self.verdict("env.sim_physics_hz in [30, 60, 120]"), predicate.VERDICT_INVALIDATED)

    def test_in_operator_coerces_numeric_members(self) -> None:
        now = dict(NOW, **{"env.sim_physics_hz": "60"})
        self.assertEqual(self.verdict("env.sim_physics_hz in [30, 60]", now=now), predicate.VERDICT_INVALIDATED)

    def test_in_operator_is_quiet_when_absent_from_the_list(self) -> None:
        self.assertEqual(self.verdict("env.sim_physics_hz in [30, 120]"), predicate.VERDICT_VALID)

    def test_not_in_operator(self) -> None:
        self.assertEqual(self.verdict("env.sim_physics_hz not_in [30]"), predicate.VERDICT_INVALIDATED)
        self.assertEqual(self.verdict("env.sim_physics_hz not_in [60]"), predicate.VERDICT_VALID)

    def test_in_with_a_non_list_right_side_is_unresolved(self) -> None:
        result = predicate.evaluate(predicate.parse("env.sim_physics_hz in 60"), now=NOW, then=THEN)
        self.assertEqual(result.verdict, predicate.VERDICT_UNRESOLVED)

    def test_ordered_comparison(self) -> None:
        self.assertEqual(self.verdict("env.sim_physics_hz > 30"), predicate.VERDICT_INVALIDATED)
        self.assertEqual(self.verdict("env.sim_physics_hz > 120"), predicate.VERDICT_VALID)

    def test_ordered_comparison_on_incomparable_types_is_unresolved(self) -> None:
        now = dict(NOW, **{"env.label": "abc"})
        self.assertEqual(self.verdict("env.label > 3", now=now), predicate.VERDICT_UNRESOLVED)

    def test_evaluate_is_pure(self) -> None:
        """No hidden dependence on module or filesystem state."""
        before_now, before_then = dict(NOW), dict(THEN)
        first = predicate.evaluate(predicate.parse("env.sim_physics_hz changed"), now=NOW, then=THEN)
        second = predicate.evaluate(predicate.parse("env.sim_physics_hz changed"), now=NOW, then=THEN)
        self.assertEqual(first, second)
        self.assertEqual(NOW, before_now)
        self.assertEqual(THEN, before_then)


class ListTests(unittest.TestCase):
    def test_a_list_is_a_conjunction(self) -> None:
        results = predicate.evaluate_all(
            ["env.sim_physics_hz changed", "code.commit changed"], now=NOW, then=THEN
        )
        self.assertEqual([r.verdict for r in results], [predicate.VERDICT_INVALIDATED, predicate.VERDICT_VALID])

    def test_invalidated_is_true_when_any_predicate_fires(self) -> None:
        self.assertTrue(
            predicate.invalidated(
                ["env.sim_physics_hz changed", "code.commit changed"], now=NOW, then=THEN
            )
        )

    def test_invalidated_is_false_when_none_fire(self) -> None:
        self.assertFalse(predicate.invalidated(["code.commit changed"], now=NOW, then=THEN))

    def test_empty_list_never_invalidates(self) -> None:
        self.assertFalse(predicate.invalidated([], now=NOW, then=THEN))

    def test_without_a_then_map_changed_compares_against_now(self) -> None:
        """A record with no stored fingerprint can still be checked for self-consistency."""
        self.assertFalse(predicate.invalidated(["env.sim_physics_hz changed"], now=NOW))


if __name__ == "__main__":
    unittest.main()
