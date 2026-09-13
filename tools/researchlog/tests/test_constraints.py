"""The invariant layer.

The single most important rule in the design lives in this file: an environment or
infrastructure failure must never be recorded as evidence about a hypothesis.
"""

from __future__ import annotations

import unittest

from researchlog import constraints

FULL_CONTRACT = {
    "target_causal_claim": "discrete release is too slow",
    "required_causal_features": ["recovery state machine"],
    "preserved_features": ["recovery state machine"],
    "missing_or_distorted_features": ["actuator dynamics"],
    "allowed_conclusions": ["release timing is slow"],
    "forbidden_conclusions": ["physical oscillation is absent"],
    "verdict": "VALID_SURROGATE",
}


def codes(findings: list) -> list[str]:
    return [f.code for f in findings]


def evidence(**overrides) -> dict:
    base = {
        "evidence_id": "EV-20260911T101530Z-a7f3",
        "evidence_level": "E2",
        "execution_status": "completed",
        "research_outcome": "refuted",
        "confidence": "moderate",
        "hypotheses_differentiated": ["H-037"],
        "belief_delta": "refined",
    }
    base.update(overrides)
    return base


class CountingTests(unittest.TestCase):
    def test_a_belief_changing_completed_run_counts(self) -> None:
        self.assertTrue(constraints.derive_counts_as_evidence_iteration(evidence()))

    def test_decoys_do_not_count(self) -> None:
        cases = {
            "infra failure, however conclusively phrased": evidence(
                execution_status="infra_failed", research_outcome="refuted"
            ),
            "completed but nothing moved": evidence(
                research_outcome="inconclusive", hypotheses_differentiated=[], belief_delta="none"
            ),
            "outcome carries no information": evidence(research_outcome="failed"),
            "no outcome recorded at all": evidence(research_outcome="none"),
            "interrupted by a session boundary": evidence(execution_status="interrupted"),
            "env blocked": evidence(
                execution_status="env_unsupported", research_outcome="informative_failure"
            ),
        }
        for label, record in cases.items():
            with self.subTest(case=label):
                self.assertFalse(constraints.derive_counts_as_evidence_iteration(record))

    def test_a_hypothesis_elimination_without_a_delta_still_counts(self) -> None:
        self.assertTrue(
            constraints.derive_counts_as_evidence_iteration(
                evidence(hypotheses_differentiated=["H-037", "H-039"], belief_delta="none")
            )
        )

    def test_a_supplied_count_that_disagrees_is_rejected(self) -> None:
        findings = constraints.check_evidence(evidence(), declared_count=False)
        self.assertIn("EVIDENCE_ITERATION_COUNT_FALSE", codes(findings))

    def test_a_supplied_count_that_agrees_is_accepted(self) -> None:
        self.assertEqual(constraints.check_evidence(evidence(), declared_count=True), [])

    def test_a_stored_count_that_disagrees_is_rejected(self) -> None:
        findings = constraints.check_evidence(evidence(counts_as_evidence_iteration=False))
        self.assertIn("EVIDENCE_ITERATION_COUNT_FALSE", codes(findings))


class ExecutionVersusOutcomeTests(unittest.TestCase):
    def test_every_non_scientific_status_cannot_refute(self) -> None:
        """The rule the whole execution_status/research_outcome split exists for."""
        for status in sorted(constraints.NON_SCIENTIFIC_EXECUTION):
            for outcome in ("confirmed", "refuted"):
                with self.subTest(status=status, outcome=outcome):
                    findings = constraints.check_evidence(
                        evidence(execution_status=status, research_outcome=outcome)
                    )
                    self.assertIn("NON_SCIENTIFIC_REFUTATION", codes(findings))

    def test_non_scientific_status_may_be_inconclusive(self) -> None:
        findings = constraints.check_evidence(
            evidence(execution_status="env_unsupported", research_outcome="inconclusive")
        )
        self.assertNotIn("NON_SCIENTIFIC_REFUTATION", codes(findings))

    def test_completed_may_refute(self) -> None:
        findings = constraints.check_evidence(evidence(execution_status="completed"))
        self.assertNotIn("NON_SCIENTIFIC_REFUTATION", codes(findings))


class SurrogateTests(unittest.TestCase):
    def test_evidence_below_the_target_level_needs_a_contract(self) -> None:
        findings = constraints.check_evidence(evidence(evidence_level="E2", target_evidence_level="E4"))
        self.assertIn("SURROGATE_CONTRACT_REQUIRED", codes(findings))

    def test_evidence_at_the_target_level_needs_no_contract(self) -> None:
        findings = constraints.check_evidence(evidence(evidence_level="E4", target_evidence_level="E4"))
        self.assertNotIn("SURROGATE_CONTRACT_REQUIRED", codes(findings))

    def test_an_explicit_surrogate_flag_needs_a_contract(self) -> None:
        findings = constraints.check_evidence(evidence(surrogate=True))
        self.assertIn("SURROGATE_CONTRACT_REQUIRED", codes(findings))

    def test_a_complete_contract_satisfies_the_requirement(self) -> None:
        findings = constraints.check_evidence(
            evidence(evidence_level="E2", target_evidence_level="E4", surrogate_contract=FULL_CONTRACT)
        )
        self.assertNotIn("SURROGATE_CONTRACT_REQUIRED", codes(findings))
        self.assertNotIn("SURROGATE_CONTRACT_INCOMPLETE", codes(findings))

    def test_an_incomplete_contract_names_what_is_missing(self) -> None:
        partial = dict(FULL_CONTRACT)
        del partial["forbidden_conclusions"]
        findings = constraints.check_evidence(
            evidence(evidence_level="E2", target_evidence_level="E4", surrogate_contract=partial)
        )
        self.assertIn("SURROGATE_CONTRACT_INCOMPLETE", codes(findings))
        self.assertIn("forbidden_conclusions", findings[0].message)

    def test_an_invalid_surrogate_cannot_confirm_or_refute(self) -> None:
        contract = dict(FULL_CONTRACT, verdict="EVIDENCE_INVALID")
        findings = constraints.check_evidence(
            evidence(evidence_level="E2", target_evidence_level="E4", surrogate_contract=contract)
        )
        self.assertIn("INVALID_SURROGATE_ASSERTS_CONCLUSION", codes(findings))

    def test_an_invalid_surrogate_may_be_inconclusive(self) -> None:
        contract = dict(FULL_CONTRACT, verdict="EVIDENCE_INVALID")
        findings = constraints.check_evidence(
            evidence(
                evidence_level="E2",
                target_evidence_level="E4",
                surrogate_contract=contract,
                research_outcome="inconclusive",
            )
        )
        self.assertNotIn("INVALID_SURROGATE_ASSERTS_CONCLUSION", codes(findings))


class HypothesisTests(unittest.TestCase):
    def test_unknown_hypothesis_is_rejected(self) -> None:
        findings = constraints.check_evidence(evidence(), known_hypotheses=["H-001"])
        self.assertIn("UNKNOWN_HYPOTHESIS", codes(findings))

    def test_known_hypotheses_pass(self) -> None:
        findings = constraints.check_evidence(evidence(), known_hypotheses=["H-037", "H-039"])
        self.assertEqual(findings, [])

    def test_differentiating_outside_the_block_is_a_warning(self) -> None:
        findings = constraints.check_evidence(evidence(), allowed_hypotheses=["H-001"])
        self.assertIn("HYPOTHESIS_OUTSIDE_BLOCK", codes(findings))
        self.assertEqual(findings[0].severity, "warning")


class PredicateCheckTests(unittest.TestCase):
    def test_a_malformed_predicate_is_rejected_on_write(self) -> None:
        findings = constraints.check_evidence(evidence(invalidated_if=["env.a and env.b"]))
        self.assertIn("PREDICATE_SYNTAX", codes(findings))

    def test_well_formed_predicates_pass(self) -> None:
        findings = constraints.check_evidence(
            evidence(invalidated_if=["env.sim_physics_hz != 30", "inputs.replay_suite changed"])
        )
        self.assertEqual(findings, [])


class FindingTests(unittest.TestCase):
    LEVELS = {"EV-1": "E2", "EV-2": "E4", "EV-3": "E1"}

    def test_a_clean_entry_passes(self) -> None:
        entry = {
            "id": "FND-007",
            "status": "Provisional",
            "confidence": "moderate",
            "max_evidence_level": "E4",
            "evidence": ["EV-1", "EV-2"],
        }
        self.assertEqual(constraints.check_finding(entry, evidence_levels=self.LEVELS), [])

    def test_citing_missing_evidence_is_a_warning(self) -> None:
        entry = {"id": "FND-1", "status": "Provisional", "evidence": ["EV-404"]}
        findings = constraints.check_finding(entry, evidence_levels=self.LEVELS)
        self.assertIn("DANGLING_FINDING_REF", codes(findings))

    def test_an_established_finding_needs_evidence(self) -> None:
        entry = {"id": "FND-1", "status": "Established", "evidence": []}
        findings = constraints.check_finding(entry, evidence_levels=self.LEVELS)
        self.assertIn("FINDING_ESTABLISHED_WITHOUT_EVIDENCE", codes(findings))

    def test_the_level_is_derived_not_asserted(self) -> None:
        entry = {"id": "FND-1", "status": "Provisional", "max_evidence_level": "E1", "evidence": ["EV-2"]}
        findings = constraints.check_finding(entry, evidence_levels=self.LEVELS)
        self.assertIn("FINDING_LEVEL_MISMATCH", codes(findings))
        self.assertIn("E4", findings[0].message)

    def test_superseded_requires_a_replacement_and_a_reason(self) -> None:
        entry = {"id": "FND-1", "status": "Superseded", "evidence": []}
        findings = codes(constraints.check_finding(entry, evidence_levels=self.LEVELS))
        self.assertIn("FINDING_SUPERSEDED_WITHOUT_REPLACEMENT", findings)
        self.assertIn("FINDING_SUPERSEDED_WITHOUT_REASON", findings)

    def test_superseded_with_both_is_accepted(self) -> None:
        entry = {
            "id": "FND-1",
            "status": "Superseded",
            "evidence": [],
            "superseded_by": "FND-011",
            "reason": "supporting evidence invalidated by ENV-CHG-003",
        }
        self.assertEqual(constraints.check_finding(entry, evidence_levels=self.LEVELS), [])

    def test_highest_level_helper(self) -> None:
        self.assertEqual(constraints.highest_level(["EV-1", "EV-2"], self.LEVELS), "E4")
        self.assertIsNone(constraints.highest_level([], self.LEVELS))
        self.assertIsNone(constraints.highest_level(["EV-404"], self.LEVELS))


class BlockContractTests(unittest.TestCase):
    def test_a_drifted_iteration_count_is_rejected(self) -> None:
        block = {"id": "RB-024", "completed_evidence_iterations": 5, "belief_delta": None}
        findings = constraints.check_block_contract(block, member_records=[evidence()])
        self.assertIn("EVIDENCE_ITERATION_COUNT_DRIFT", codes(findings))

    def test_an_accurate_iteration_count_passes(self) -> None:
        block = {"id": "RB-024", "completed_evidence_iterations": 1, "belief_delta": None}
        self.assertEqual(constraints.check_block_contract(block, member_records=[evidence()]), [])

    def test_a_block_changed_belief_but_closing_as_none_is_rejected(self) -> None:
        block = {"id": "RB-024", "completed_evidence_iterations": 1, "belief_delta": "none"}
        findings = constraints.check_block_contract(block, member_records=[evidence()])
        self.assertIn("BLOCK_BELIEF_DELTA_INCONSISTENT", codes(findings))

    def test_an_open_block_may_leave_the_delta_unset(self) -> None:
        block = {"id": "RB-024", "completed_evidence_iterations": 1, "belief_delta": None}
        self.assertEqual(constraints.check_block_contract(block, member_records=[evidence()]), [])

    def test_an_invalid_delta_value_is_rejected(self) -> None:
        block = {"id": "RB-024", "completed_evidence_iterations": 0, "belief_delta": "maybe"}
        findings = constraints.check_block_contract(block, member_records=[])
        self.assertIn("BLOCK_BELIEF_DELTA_INVALID", codes(findings))


class SignalTests(unittest.TestCase):
    """A boundary keeps the wording it was given.

    The phrasing of a constraint carries its scope, so rendering it into English and
    dropping the original is a quiet change to what was forbidden, not a translation.
    """

    def signal(self, **overrides) -> dict:
        base = {
            "id": "C-009",
            "type": "CONSTRAINT",
            "statement": "Do not modify the navigation planner.",
            "scope": "recovery research",
            "expiry": "recovery checkpoint",
            "source_text": "导航 planner 先别改，等复盘完再评估。",
        }
        base.update(overrides)
        return base

    def test_every_boundary_type_requires_the_original_wording(self) -> None:
        for signal_type in sorted(constraints.SIGNAL_TYPES_REQUIRING_SOURCE_TEXT):
            with self.subTest(type=signal_type):
                findings = constraints.check_signal(self.signal(type=signal_type, source_text=None))
                self.assertIn("SIGNAL_SOURCE_TEXT_REQUIRED", codes(findings))

    def test_a_boundary_that_keeps_its_wording_passes(self) -> None:
        self.assertEqual(constraints.check_signal(self.signal()), [])

    def test_a_blank_source_text_does_not_count_as_keeping_it(self) -> None:
        findings = constraints.check_signal(self.signal(source_text="   \n"))
        self.assertIn("SIGNAL_SOURCE_TEXT_REQUIRED", codes(findings))

    def test_the_type_cannot_be_lower_cased_to_escape_the_rule(self) -> None:
        findings = constraints.check_signal(self.signal(type="constraint", source_text=None))
        self.assertIn("SIGNAL_SOURCE_TEXT_REQUIRED", codes(findings))

    def test_signals_that_are_the_agents_to_reformulate_are_exempt(self) -> None:
        """A SUSPECT or a DIRECTION is meant to be reformulated; a boundary is not."""
        for signal_type in ("OBSERVE", "SUSPECT", "DIRECTION", "CHALLENGE", "IMPLEMENT"):
            with self.subTest(type=signal_type):
                self.assertEqual(
                    constraints.check_signal(self.signal(type=signal_type, source_text=None)), []
                )

    def test_every_known_type_is_recognised(self) -> None:
        for signal_type in constraints.SIGNAL_TYPES:
            with self.subTest(type=signal_type):
                codes_ = codes(constraints.check_signal(self.signal(type=signal_type)))
                self.assertNotIn("SIGNAL_TYPE_UNKNOWN", codes_)

    def test_an_unknown_type_is_rejected_rather_than_skipped(self) -> None:
        """A mistyped type would otherwise skip every requirement below it."""
        findings = constraints.check_signal(self.signal(type="CONSTRAINTS"))
        self.assertIn("SIGNAL_TYPE_UNKNOWN", codes(findings))

    def test_decision_final_is_a_modifier_not_a_type(self) -> None:
        findings = constraints.check_signal(self.signal(type="DECISION FINAL", source_text=None))
        self.assertIn("SIGNAL_TYPE_UNKNOWN", codes(findings))

    def test_a_constraint_must_say_what_it_bounds_and_until_when(self) -> None:
        findings = codes(constraints.check_signal(self.signal(scope=None, expiry=None)))
        self.assertIn("SIGNAL_SCOPE_REQUIRED", findings)
        self.assertIn("SIGNAL_EXPIRY_REQUIRED", findings)

    def test_only_a_constraint_needs_scope_and_expiry(self) -> None:
        """A VETO is permanent until repealed; it has no window to declare."""
        findings = constraints.check_signal(self.signal(type="VETO", scope=None, expiry=None))
        self.assertEqual(findings, [])

    def test_a_decision_is_covered_whether_or_not_it_is_final(self) -> None:
        for extra in ({}, {"final": True}):
            with self.subTest(final=extra.get("final")):
                findings = constraints.check_signal(
                    self.signal(type="DECISION", source_text=None, **extra)
                )
                self.assertIn("SIGNAL_SOURCE_TEXT_REQUIRED", codes(findings))


if __name__ == "__main__":
    unittest.main()
