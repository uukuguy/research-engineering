"""Integration paths that unit-level smoke tests miss.

Every test here exists because something passed a smaller test and still failed in
practice:

* Reconciliation and the environment snapshot only behave differently **inside a real
  Git repository**. The git-aware detectors return early when there is no repository, so
  a `TemporaryDirectory()` that was never `git init`-ed exercises a path no user is on,
  and reports success for a scenario the user will never see.
* `init` used to write `dirty_expected: false` into a tree that its own command had just
  made dirty, so the first `reconcile` reported a mismatch against state `init` had
  created seconds earlier.
* `record` used to leave `environment` unset. A `changed` predicate compares the value
  recorded *then* against the value *now*, and reads `then` back from the record — so
  without the snapshot the recommended predicate form could never resolve.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from researchlog import cli

CONTRACT = {
    "target_causal_claim": "residual predicts attack onset",
    "required_causal_features": ["raw lidar frames"],
    "preserved_features": ["raw lidar frames"],
    "missing_or_distorted_features": ["closed-loop dynamics"],
    "allowed_conclusions": ["a residual signal exists"],
    "forbidden_conclusions": ["the detector is deployable"],
    "verdict": "VALID_SURROGATE",
}


class GitRepoCase(unittest.TestCase):
    """A temporary directory that is a real Git repository."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._git("init", "-q", ".")
        self._git("config", "user.email", "test@example.invalid")
        self._git("config", "user.name", "test")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _git(self, *args: str) -> None:
        subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)

    def run_cli(self, *args: str) -> tuple[int, dict]:
        """Run a command with the repository as the working directory.

        `--root` cannot simply be appended: `run -- <cmd>` would pass it to the child
        process instead of the tool, which is exactly the kind of thing a test helper
        should not quietly get wrong.
        """
        previous = Path.cwd()
        os.chdir(self.root)
        try:
            return cli.run_and_capture(list(args))
        finally:
            os.chdir(previous)

    def init_state(self, *extra: str) -> dict:
        # Fixtures keep the legacy `research/` directory name so existing tests
        # can hardcode paths unchanged; the dotted `.research/` form is exercised
        # by the dedicated test suite (`DotResearchDirTests`).
        argv = list(extra)
        if "--legacy" not in argv:
            argv = ["--legacy", *argv]
        code, envelope = self.run_cli("init", *argv)
        self.assertEqual(code, 0, envelope)
        return envelope

    def record(self, *extra: str) -> tuple[int, dict]:
        return self.run_cli("record", *extra)

    def write(self, name: str, payload: object) -> Path:
        path = self.root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path


class InitReconciliationTests(GitRepoCase):
    def test_init_records_the_tree_as_it_actually_is(self) -> None:
        """Untracked research state makes the tree dirty; ACTIVE must not claim otherwise."""
        self.init_state()
        active = json.loads((self.root / "research" / "ACTIVE.json").read_text(encoding="utf-8"))
        self.assertTrue(active["git"]["dirty_expected"])
        self.assertEqual(active["git"]["expected_touched_files"], ["research/"])

    def test_reconcile_is_clean_immediately_after_init(self) -> None:
        """The state `init` creates must not be reported as inconsistent by `init`'s own tool."""
        self.init_state()
        code, envelope = self.run_cli("reconcile")
        self.assertEqual(code, 0, envelope)
        self.assertTrue(envelope["payload"]["clean"])
        self.assertEqual(envelope["findings"], [])


    def test_reconcile_stays_clean_after_the_state_is_committed(self) -> None:
        self.init_state()
        self._git("add", "-A")
        self._git("commit", "-qm", "research state")
        code, envelope = self.run_cli("reconcile")
        self.assertEqual(code, 0, envelope)

    def test_reconcile_catches_genuinely_unexpected_dirty_state(self) -> None:
        """The detector still earns its place: real drift must be reported."""
        self.init_state()
        self._git("add", "-A")
        self._git("commit", "-qm", "research state")
        self.run_cli("active", "--set", "git.dirty_expected=false")
        (self.root / "src_scratch.py").write_text("x = 1\n", encoding="utf-8")

        code, envelope = self.run_cli("reconcile")
        self.assertEqual(code, 2)
        self.assertIn("ACTIVE_GIT_MISMATCH", [f["code"] for f in envelope["findings"]])


class HypothesisRegistryTests(GitRepoCase):
    """`known_hypotheses` is the declared hypotheses, not the evidence IDs.

    `validate` passed `sorted(ledger.records)` — an evidence-ID space — as the hypothesis
    registry, so `UNKNOWN_HYPOTHESIS` fired on every record that named a hypothesis, since
    an H-* is never an EV-*. It reported a fact about the wiring rather than about the
    record, and it fired on the ordinary path of recording evidence about a hypothesis.
    """

    def record_naming(self, hypothesis: str) -> None:
        """An inconclusive record, so the block contract is not what is under test."""
        code, envelope = self.record(
            "--question",
            "Does the residual separate release timing from measurement noise?",
            "--subject-type",
            "harness",
            "--subject-id",
            "HRN-001",
            "--level",
            "E2",
            "--execution-status",
            "completed",
            "--research-outcome",
            "inconclusive",
            "--confidence",
            "low",
            "--hypothesis",
            hypothesis,
            "--belief-delta",
            "none",
            "--observation",
            "obs",
        )
        self.assertEqual(code, 0, envelope)

    def test_a_declared_hypothesis_is_known(self) -> None:
        self.init_state()
        self.run_cli("active", "--set", 'hypothesis_ids=["H-037"]')
        self.record_naming("H-037")

        _, envelope = self.run_cli("validate")
        self.assertNotIn("UNKNOWN_HYPOTHESIS", [f["code"] for f in envelope["findings"]])

    def test_an_undeclared_hypothesis_is_reported(self) -> None:
        self.init_state()
        self.run_cli("active", "--set", 'hypothesis_ids=["H-037"]')
        self.record_naming("H-999")

        _, envelope = self.run_cli("validate")
        self.assertIn("UNKNOWN_HYPOTHESIS", [f["code"] for f in envelope["findings"]])


class BlockCountTests(GitRepoCase):
    """The second defect the acceptance work found on the ordinary path.

    `EVIDENCE_ITERATION_COUNT_DRIFT` compared the stored count against the derived one while
    the block was open, and no command ever wrote the stored count. Every project that
    recorded a belief-changing iteration therefore carried an error it could not clear, with
    a fix hint telling it not to maintain that field by hand either.
    """

    def record_a_counting_iteration(self) -> None:
        code, envelope = self.record(
            "--question",
            "Does the residual separate release timing from measurement noise?",
            "--subject-type",
            "harness",
            "--subject-id",
            "HRN-001",
            "--level",
            "E2",
            "--execution-status",
            "completed",
            "--research-outcome",
            "refuted",
            "--confidence",
            "moderate",
            "--hypothesis",
            "H-037",
            "--belief-delta",
            "refined",
            "--observation",
            "The residual tracked release timing.",
        )
        self.assertEqual(code, 0, envelope)

    def declare_hypothesis(self) -> None:
        self.run_cli("active", "--set", 'hypothesis_ids=["H-037"]')

    def open_block(self, block_id: str = "RB-024") -> None:
        """Open a block before recording, which is what makes the evidence its own.

        With no block open, `record` stamps `block_id: null` and the record belongs to no
        block — correctly, since there is no block for it to be charged to.
        """
        self.run_cli("active", "--set", f"block.id={block_id}")

    def test_an_open_block_is_not_accused_of_drifting(self) -> None:
        self.init_state()
        self.declare_hypothesis()
        self.record_a_counting_iteration()

        _, envelope = self.run_cli("validate")
        self.assertNotIn(
            "EVIDENCE_ITERATION_COUNT_DRIFT", [f["code"] for f in envelope["findings"]]
        )

    def test_closing_the_block_writes_the_derived_count(self) -> None:
        self.init_state()
        self.declare_hypothesis()
        self.open_block()
        self.record_a_counting_iteration()

        code, envelope = self.run_cli("active", "--close-block", "--belief-delta", "refined")
        self.assertEqual(code, 0, envelope)

        _, document = self.run_cli("active", "--get-json")
        self.assertEqual(document["payload"]["active"]["block"]["completed_evidence_iterations"], 1)

        _, envelope = self.run_cli("validate")
        self.assertEqual([f["code"] for f in envelope["findings"]], [])

    def test_a_new_block_does_not_start_where_the_last_one_finished(self) -> None:
        """Opening a block is supposed to reset the bound.

        Membership came from the global hypothesis registry and the stored summary was never
        cleared, so a block opened later on the same hypotheses started at the previous
        block's count and delta — held to a budget for work it had not done.
        """
        self.init_state()
        self.declare_hypothesis()
        self.open_block("RB-030")
        self.record_a_counting_iteration()
        self.record_a_counting_iteration()
        self.run_cli("active", "--close-block", "--belief-delta", "refined")

        self.open_block("RB-031")
        _, document = self.run_cli("active", "--get-json")
        block = document["payload"]["active"]["block"]
        self.assertEqual(block["id"], "RB-031")
        self.assertIsNone(block["belief_delta"], "the previous block's delta carried over")
        self.assertEqual(
            block["completed_evidence_iterations"], 0, "the previous block's count carried over"
        )

        self.run_cli("active", "--set", "block.max_evidence_iterations=1")
        _, envelope = self.run_cli("validate")
        self.assertNotIn(
            "BLOCK_ITERATION_BUDGET_EXCEEDED", [f["code"] for f in envelope["findings"]]
        )

    def test_a_block_that_overspends_its_budget_is_reported_while_it_runs(self) -> None:
        self.init_state()
        self.declare_hypothesis()
        self.open_block()
        self.run_cli("active", "--set", "block.max_evidence_iterations=1")
        self.record_a_counting_iteration()
        self.record_a_counting_iteration()

        _, envelope = self.run_cli("validate")
        self.assertIn(
            "BLOCK_ITERATION_BUDGET_EXCEEDED", [f["code"] for f in envelope["findings"]]
        )

    def test_reproduction_does_not_consume_the_evidence_budget(self) -> None:
        """V1 P2: tagging an iteration `reproduction` keeps it out of the evidence budget.

        Three records land in the ledger: two belief-changing evidence iterations and one
        reproduction. Closing the block must show `completed_evidence_iterations = 2`
        (only the two counted) and `reproduction_iterations = 1`. If the reproduction
        leaked into the evidence count, the count would be 3 and the test would catch it.
        """
        self.init_state()
        self.declare_hypothesis()
        self.open_block()
        self.record_a_counting_iteration()
        self.record_a_counting_iteration()

        # Same shape as `record_a_counting_iteration` but tagged as reproduction.
        code, envelope = self.record(
            "--question", "Re-running the same hypothesis with the new build.",
            "--subject-type", "harness",
            "--subject-id", "HRN-001",
            "--level", "E2",
            "--execution-status", "completed",
            "--research-outcome", "refuted",
            "--confidence", "moderate",
            "--hypothesis", "H-037",
            "--belief-delta", "refined",
            "--observation", "Reproduced the residual tracking on the new build.",
            "--iteration-kind", "reproduction",
        )
        self.assertEqual(code, 0, envelope)

        code, envelope = self.run_cli("active", "--close-block", "--belief-delta", "refined")
        self.assertEqual(code, 0, envelope)

        _, document = self.run_cli("active", "--get-json")
        block = document["payload"]["active"]["block"]
        self.assertEqual(block["completed_evidence_iterations"], 2)
        self.assertEqual(block["reproduction_iterations"], 1)

    def test_reproduction_skips_even_with_no_belief_delta_dropped(self) -> None:
        """A reproduction is excluded from the evidence budget even when its
        scientific fields would otherwise count it (`belief_delta != none`).
        Without the iteration_kind override, this same record would land in the
        evidence bucket; the test pins that the override wins."""
        self.init_state()
        self.declare_hypothesis()
        self.open_block()

        code, envelope = self.record(
            "--question", "Replaying a closed hypothesis to check a tool regression.",
            "--subject-type", "harness",
            "--subject-id", "HRN-001",
            "--level", "E1",
            "--execution-status", "completed",
            "--research-outcome", "inconclusive",
            "--confidence", "low",
            "--hypothesis", "H-037",
            "--belief-delta", "refined",  # would normally count
            "--observation", "Replay only — no new belief.",
            "--iteration-kind", "reproduction",
        )
        self.assertEqual(code, 0, envelope)

        code, envelope = self.run_cli("active", "--close-block", "--belief-delta", "refined")
        self.assertEqual(code, 0, envelope)

        _, document = self.run_cli("active", "--get-json")
        block = document["payload"]["active"]["block"]
        self.assertEqual(block["completed_evidence_iterations"], 0)
        self.assertEqual(block["reproduction_iterations"], 1)


class SchemaVersionVisibilityTests(GitRepoCase):
    """A document from another tool version must be reported when it is read.

    Reading a newer document is allowed and writing it is refused, but neither of those is a
    *report*: `validate` used to exit 0 on a document it could not fully interpret, and the
    refusal only arrived when someone tried to write — by which point a session had already
    acted on its reading of the file.
    """

    def bump_active_version(self, version: str) -> None:
        path = self.root / "research" / "ACTIVE.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["schema_version"] = version
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    def test_a_newer_pointer_is_reported_on_read(self) -> None:
        self.init_state()
        self.bump_active_version("9.0")

        _, envelope = self.run_cli("validate")
        self.assertIn("SCHEMA_NEWER", [f["code"] for f in envelope["findings"]])

    def test_the_resume_path_reports_a_newer_pointer_too(self) -> None:
        self.init_state()
        self.bump_active_version("9.0")

        _, envelope = self.run_cli("reconcile", "--json")
        self.assertFalse(envelope["payload"]["clean"])
        self.assertIn("SCHEMA_NEWER", [f["code"] for f in envelope["findings"]])

    def test_a_newer_pointer_is_still_never_written(self) -> None:
        self.init_state()
        self.bump_active_version("9.0")
        target = self.root / "research" / "ACTIVE.json"
        before = target.read_bytes()

        code, envelope = self.run_cli("active", "--set-status", "idle", "--json")
        self.assertEqual(code, 4, envelope)
        self.assertEqual(target.read_bytes(), before)

    def test_findings_entries_are_not_mistaken_for_foreign_documents(self) -> None:
        """The version lives on the block, not on each entry.

        `findings-entry` entries carry no `schema_version` field — the `research:findings`
        block carries it — so checking each entry reported every finding in the file as a
        document from another tool. Found by running the evaluator-conflict drill, whose
        session created the first two findings any drill had produced.
        """
        self.init_state()
        code, envelope = self.record(
            "--question", "Does the proxy track the behaviour or the trace?",
            "--subject-type", "evaluation_surface", "--subject-id", "EVAL-004",
            "--level", "E2",
            "--execution-status", "completed", "--research-outcome", "inconclusive",
            "--confidence", "low", "--belief-delta", "none",
            "--observation", "obs",
        )
        self.assertEqual(code, 0, envelope)
        evidence_id = envelope["payload"]["evidence_id"]

        code, envelope = self.run_cli(
            "findings", "add",
            "--title", "The proxy tracks the intervention trace, not the behaviour",
            "--status", "Refuted",
            "--confidence", "moderate",
            "--evidence", evidence_id,
        )
        self.assertEqual(code, 0, envelope)

        _, envelope = self.run_cli("validate")
        self.assertEqual([f["code"] for f in envelope["findings"]], [])

    def test_a_manifest_that_violates_its_schema_is_reported(self) -> None:
        """`validate` offers `--print-schema manifest` and never checked a manifest."""
        self.init_state()
        run = self.root / "research" / "runs" / "EXP-9999"
        run.mkdir(parents=True)
        (run / "manifest.json").write_text(
            json.dumps({"schema_version": "1.0", "experiment_id": "EXP-9999", "status": "running"}),
            encoding="utf-8",
        )

        _, envelope = self.run_cli("validate")
        self.assertIn("SCHEMA_VIOLATION", [f["code"] for f in envelope["findings"]])


class ResumePathVisibilityTests(GitRepoCase):
    """The resume entry point must not call a file it could not read `clean`.

    `reconcile` is what the resume protocol actually runs, and every detector reads ACTIVE
    through a loader that catches its own failure. So a corrupt `ACTIVE.json` produced exit
    0, `clean: true` and no findings — the state declared intact at the exact moment the
    file the session resumes from could not be parsed. The Git fallback the design
    specifies was implemented but never wired, so the corruption could not be recovered
    from either.
    """

    CORRUPT = '{"schema_version": "1.0", "stat'

    def commit_valid_state(self) -> None:
        self.init_state()
        self._git("add", "-A")
        self._git("commit", "-qm", "valid state")

    def corrupt_active(self) -> None:
        (self.root / "research" / "ACTIVE.json").write_text(self.CORRUPT, encoding="utf-8")

    def test_a_pointer_recovered_from_the_last_commit_is_reported(self) -> None:
        self.commit_valid_state()
        self.corrupt_active()

        code, envelope = self.run_cli("reconcile", "--json")
        self.assertEqual(code, 3, envelope)
        self.assertFalse(envelope["payload"]["clean"])
        self.assertIn("RECOVERED_FROM_GIT", [f["code"] for f in envelope["findings"]])

    def test_with_no_history_to_fall_back_on_it_is_an_error_not_a_clean(self) -> None:
        self.init_state()  # nothing committed: no revision to recover from
        self.corrupt_active()

        code, envelope = self.run_cli("reconcile", "--json")
        self.assertEqual(code, 2, envelope)
        self.assertFalse(envelope["payload"]["clean"])
        self.assertIn("RECOVERY_REQUIRED", [f["code"] for f in envelope["findings"]])

    def test_a_healthy_pointer_still_reconciles_clean(self) -> None:
        """The recovery report must not turn a working resume into a warning."""
        self.commit_valid_state()

        code, envelope = self.run_cli("reconcile", "--json")
        self.assertEqual(code, 0, envelope)
        self.assertTrue(envelope["payload"]["clean"])


class ComparisonIdentityTests(GitRepoCase):
    """`compare` has to be able to say COMPARABLE, or its blocking verdicts mean nothing.

    `code_state.diff_sha256` hashed the whole working tree, canonical state included.
    Writing an evidence shard changes that tree, so every record's code identity was unique
    and no two records were ever comparable: `ATTRIBUTION_FORBIDDEN` was on permanently.
    The unit tests missed it because they inject a synthetic `code_state`, which is exactly
    the field under test — so they pass while the real path cannot produce two equal ones.
    """

    def record_with(self, *, replay_suite: str, fingerprint: str = "fp-1") -> str:
        document = {
            "schema_version": "1.0",
            "question": "which of A and B?",
            "subject": {"type": "mechanism", "id": "M-001"},
            "evidence_level": "E2",
            "observations": ["ran"],
            "execution_status": "completed",
            "research_outcome": "inconclusive",
            "confidence": "low",
            "counts_as_evidence_iteration": False,
            "environment": {"fingerprint": fingerprint},
            "inputs": {"replay_suite": replay_suite},
        }
        code, envelope = self.run_cli("record", "--from-json", json.dumps(document), "--json")
        self.assertEqual(code, 0, envelope)
        return envelope["payload"]["evidence_id"]

    def test_two_records_of_the_same_identity_are_comparable(self) -> None:
        self.init_state()
        first = self.record_with(replay_suite="replay-v3")
        second = self.record_with(replay_suite="replay-v3")

        code, envelope = self.run_cli("compare", first, second, "--json")
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["payload"]["attribute_verdict"], "COMPARABLE")

    def test_a_moved_key_input_still_forbids_attribution(self) -> None:
        self.init_state()
        first = self.record_with(replay_suite="replay-v3")
        second = self.record_with(replay_suite="replay-v4")

        code, envelope = self.run_cli("compare", first, second, "--json")
        self.assertEqual(code, 3, envelope)
        self.assertEqual(envelope["payload"]["attribute_verdict"], "ATTRIBUTION_FORBIDDEN")

    def test_a_moved_environment_still_demands_a_rebaseline(self) -> None:
        self.init_state()
        first = self.record_with(replay_suite="replay-v3", fingerprint="fp-1")
        second = self.record_with(replay_suite="replay-v3", fingerprint="fp-2")

        code, envelope = self.run_cli("compare", first, second, "--json")
        self.assertEqual(code, 3, envelope)
        self.assertEqual(envelope["payload"]["attribute_verdict"], "REBASELINE_REQUIRED")


class ArchitectSignalTests(GitRepoCase):
    """A boundary signal must not lose the wording it was given.

    Signals carry no schema, so this rule lives in the meaning layer — and it has to fire
    on the path a session actually takes. The resume protocol runs `reconcile` and not
    `validate`, so a rule checked only by `validate` is a rule that never fires.
    """

    def append_signal(self, **signal: object) -> None:
        path = self.root / "research" / "ARCHITECT.md"
        block = (
            "```json research:signal\n"
            + json.dumps(signal, ensure_ascii=False, indent=2)
            + "\n```\n"
        )
        path.write_text(path.read_text(encoding="utf-8") + "\n" + block, encoding="utf-8")

    def commit_state(self) -> None:
        self.init_state()
        self._git("add", "-A")
        self._git("commit", "-qm", "research state")

    def test_a_boundary_that_lost_its_wording_is_reported_on_resume(self) -> None:
        self.commit_state()
        self.append_signal(
            id="C-010",
            type="CONSTRAINT",
            statement="Do not modify the navigation planner.",
            scope="recovery research",
            expiry="recovery checkpoint",
            source_text=None,
            active=True,
        )

        code, envelope = self.run_cli("reconcile")
        self.assertEqual(code, 2)
        self.assertIn("SIGNAL_SOURCE_TEXT_REQUIRED", [f["code"] for f in envelope["findings"]])

    def test_validate_reports_the_same_rule(self) -> None:
        self.commit_state()
        self.append_signal(
            id="C-011", type="VETO", statement="Do not train on the held-out split.", source_text=""
        )

        _, envelope = self.run_cli("validate")
        self.assertIn("SIGNAL_SOURCE_TEXT_REQUIRED", [f["code"] for f in envelope["findings"]])

    def test_an_iso_expiry_is_enforced_at_resume(self) -> None:
        """`expiry` is the field; an ISO timestamp in it is what makes the check fire."""
        self.commit_state()
        self.append_signal(
            id="C-013",
            type="CONSTRAINT",
            statement="Do not modify the navigation planner.",
            scope="recovery research",
            expiry="2020-01-01T00:00:00+00:00",
            source_text="导航 planner 先别改。",
            active=True,
        )

        _, envelope = self.run_cli("reconcile")
        self.assertIn("EXPIRED_ARCHITECT_SIGNAL", [f["code"] for f in envelope["findings"]])

    def test_a_free_text_expiry_is_recorded_but_not_evaluated(self) -> None:
        """A promise a human keeps; the tool says so by not pretending to evaluate it."""
        self.commit_state()
        self.append_signal(
            id="C-014",
            type="CONSTRAINT",
            statement="Do not modify the navigation planner.",
            scope="recovery research",
            expiry="recovery checkpoint",
            source_text="导航 planner 先别改。",
            active=True,
        )

        _, envelope = self.run_cli("reconcile")
        self.assertEqual([f["code"] for f in envelope["findings"]], [])

    def test_a_constraint_without_scope_or_expiry_is_reported(self) -> None:
        self.commit_state()
        self.append_signal(
            id="C-015",
            type="CONSTRAINT",
            statement="Do not modify the navigation planner.",
            source_text="导航 planner 先别改。",
            active=True,
        )

        _, envelope = self.run_cli("validate")
        codes = [f["code"] for f in envelope["findings"]]
        self.assertIn("SIGNAL_SCOPE_REQUIRED", codes)
        self.assertIn("SIGNAL_EXPIRY_REQUIRED", codes)

    def test_a_malformed_signal_block_is_an_error_not_a_silent_pass(self) -> None:
        """The check that reads the signals is the only thing that can notice this."""
        self.commit_state()
        path = self.root / "research" / "ARCHITECT.md"
        path.write_text(
            path.read_text(encoding="utf-8") + '\n```json research:signal\n{"id": "C-012",}\n```\n',
            encoding="utf-8",
        )

        _, envelope = self.run_cli("validate")
        self.assertIn("BLOCK_MALFORMED", [f["code"] for f in envelope["findings"]])

    def test_the_skeleton_ships_no_live_signals(self) -> None:
        """A project built from the template must not start with a constraint nobody issued.

        The example in `ARCHITECT.md` used to be a real `research:signal` block, so every new
        project opened with a `CONSTRAINT` no architect had given — and it was fully
        compliant, so no check could see it. The fence is the only observable difference
        between teaching a shape and asserting a fact, which is why this asserts on the text
        rather than on a finding.
        """
        self.init_state()
        text = (self.root / "research" / "ARCHITECT.md").read_text(encoding="utf-8")
        self.assertNotIn("```json research:signal", text)

        _, envelope = self.run_cli("validate")
        self.assertEqual([f["code"] for f in envelope["findings"]], [])

    def test_the_shipped_template_satisfies_the_rule_it_teaches(self) -> None:
        """A new project bootstraps from the template; it must not start on an error."""
        self.init_state()
        _, envelope = self.run_cli("validate")
        codes = [f["code"] for f in envelope["findings"]]
        self.assertNotIn("SIGNAL_SOURCE_TEXT_REQUIRED", codes)


class EnvironmentSnapshotTests(GitRepoCase):
    def _baseline(self, hz: int = 30) -> None:
        change = self.write(f"chg-{hz}.json", {"capability": "baseline", "changes": {"sim_physics_hz": hz}})
        code, envelope = self.run_cli("env", "record", str(change))
        self.assertEqual(code, 0, envelope)

    def _evidence(self, *predicates: str):
        contract = self.write("contract.json", CONTRACT)
        args = [
            "--question", "does residual predict onset",
            "--subject-type", "mechanism",
            "--subject-id", "lidar-residual",
            "--observation", "residual rose within 2 frames in 3 of 12 cases",
            "--level", "E1",
            "--target-level", "E2",
            "--surrogate-contract", str(contract),
            "--execution-status", "completed",
            "--research-outcome", "inconclusive",
            "--confidence", "low",
            "--hypothesis", "H-001",
            "--hypotheses-differentiated", "H-001",
        ]
        for text in predicates:
            args += ["--invalidated-if", text]
        return self.record(*args)

    def test_record_snapshots_the_current_environment(self) -> None:
        """Without this, a `changed` predicate has no `then` and can never resolve."""
        self.init_state()
        self._baseline(30)
        code, envelope = self._evidence()
        self.assertEqual(code, 0, envelope)

        evidence_id = envelope["payload"]["evidence_id"]
        # V1 Block 2 / T2: shards live under `<YYYY-MM>/`. Look up the
        # partition from the id rather than the wall clock so the test
        # does not drift across a month boundary mid-run.
        from researchlog.repo import _evidence_month
        partition = _evidence_month(evidence_id)
        record = json.loads(
            (self.root / "research" / "ledger" / partition / f"{evidence_id}.json").read_text()
        )
        self.assertEqual(record["environment"]["sim_physics_hz"], 30)

    def test_a_changed_predicate_invalidates_when_the_value_moves(self) -> None:
        """The end-to-end point of the predicate language."""
        self.init_state()
        self._baseline(30)
        self._evidence("env.sim_physics_hz changed")

        change = self.write("chg-60.json", {"capability": "sim rebuilt", "changes": {"sim_physics_hz": 60}})
        code, envelope = self.run_cli("env", "query", str(change))

        self.assertEqual(code, 3, envelope)
        invalidated = envelope["payload"]["invalidated"]
        self.assertEqual(len(invalidated), 1)
        self.assertIn("from 30 to 60", invalidated[0]["reason"])

    def test_a_changed_predicate_is_quiet_when_nothing_moved(self) -> None:
        self.init_state()
        self._baseline(30)
        self._evidence("env.sim_physics_hz changed")

        change = self.write("chg-same.json", {"capability": "no-op", "changes": {"sim_physics_hz": 30}})
        code, envelope = self.run_cli("env", "query", str(change))

        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["payload"]["invalidated"], [])

    def test_env_query_never_rewrites_findings(self) -> None:
        """Invalidation is a fact about comparability; demotion is a belief change."""
        self.init_state()
        self._baseline(30)
        self._evidence("env.sim_physics_hz changed")
        findings_path = self.root / "research" / "FINDINGS.md"
        before = findings_path.read_bytes()

        change = self.write("chg-60.json", {"capability": "sim rebuilt", "changes": {"sim_physics_hz": 60}})
        self.run_cli("env", "query", str(change))

        self.assertEqual(findings_path.read_bytes(), before)

    def test_env_query_is_byte_identical_when_asked_twice(self) -> None:
        self.init_state()
        self._baseline(30)
        self._evidence("env.sim_physics_hz changed")
        change = self.write("chg-60.json", {"capability": "sim rebuilt", "changes": {"sim_physics_hz": 60}})

        _, first = self.run_cli("env", "query", str(change))
        _, second = self.run_cli("env", "query", str(change))

        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))


class OrphanDetectionTests(GitRepoCase):
    def test_a_finished_run_with_no_evidence_is_reported(self) -> None:
        """Detection is what the tool owes; recording the science is what the agent owes."""
        self.init_state()
        code, envelope = self.run_cli(
            "run", "--question", "does the probe fire", "--", "false"
        )
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["payload"]["child_exit_code"], 1)

        code, envelope = self.run_cli("reconcile")
        self.assertEqual(code, 2)
        self.assertIn("ORPHAN_RUN", [f["code"] for f in envelope["findings"]])

    def test_a_command_that_never_started_is_infrastructure_not_science(self) -> None:
        self.init_state()
        code, envelope = self.run_cli(
            "run", "--question", "missing", "--", "/nonexistent/binary-xyz"
        )
        self.assertEqual(code, 5)
        experiment_id = envelope["payload"]["experiment_id"]
        manifest = json.loads(
            (self.root / "research" / "runs" / experiment_id / "manifest.json").read_text()
        )
        self.assertEqual(manifest["status"], "infra_failed")
        self.assertFalse((self.root / "research" / "runs" / experiment_id / "result.json").exists())


class WorktreeMultiWriterTests(GitRepoCase):
    """P9 single-writer enforcement: two worktrees dirtying research/ at once is illegal.

    Multi-writer is structurally unsafe — canonical state has no merge strategy and a
    conflict silently loses one writer's record. The detector reports it loudly so the
    agent has a name to act on, and lets the single-writer case pass cleanly.
    """

    def add_worktree(self, name: str) -> Path:
        """Attach a linked worktree at <root>/.worktrees/<name> on a new branch."""
        wt_path = self.root / ".worktrees" / name
        wt_path.parent.mkdir(parents=True, exist_ok=True)
        self._git("worktree", "add", "-q", "-b", f"wt/{name}", str(wt_path))
        return wt_path

    def test_a_single_worktree_with_dirty_research_passes(self) -> None:
        """The main worktree is the legitimate writer; dirtying research/ there is fine."""
        self.init_state()
        self._git("add", "-A")
        self._git("commit", "-qm", "research state")
        (self.root / "research" / "ACTIVE.json").write_text(
            (self.root / "research" / "ACTIVE.json").read_text(encoding="utf-8")
            + "\n"
        )
        code, envelope = self.run_cli("reconcile")
        self.assertEqual(code, 0, envelope)
        self.assertTrue(envelope["payload"]["clean"])
        self.assertNotIn("WORKTREE_MULTI_WRITER", [f["code"] for f in envelope["findings"]])

    def test_two_worktrees_dirtying_research_at_once_is_reported(self) -> None:
        self.init_state()
        self._git("add", "-A")
        self._git("commit", "-qm", "research state")
        wt = self.add_worktree("sibling")

        (self.root / "research" / "ACTIVE.json").write_text(
            (self.root / "research" / "ACTIVE.json").read_text(encoding="utf-8")
            + "\n"
        )
        (wt / "research" / "ACTIVE.json").write_text(
            (wt / "research" / "ACTIVE.json").read_text(encoding="utf-8")
            + "\n"
        )

        code, envelope = self.run_cli("reconcile")
        self.assertEqual(code, 2, envelope)
        codes = [f["code"] for f in envelope["findings"]]
        self.assertIn("WORKTREE_MULTI_WRITER", codes)
        finding = next(f for f in envelope["findings"] if f["code"] == "WORKTREE_MULTI_WRITER")
        self.assertEqual(finding["severity"], "error")
        self.assertIn(str(self.root), finding["message"])
        self.assertIn(str(wt), finding["message"])
        self.assertTrue(finding.get("fix_hint"))

    def test_only_one_of_two_worktrees_dirty_passes(self) -> None:
        """A second worktree present but clean does not trigger the detector."""
        self.init_state()
        self._git("add", "-A")
        self._git("commit", "-qm", "research state")
        self.add_worktree("idle")
        (self.root / "research" / "ACTIVE.json").write_text(
            (self.root / "research" / "ACTIVE.json").read_text(encoding="utf-8")
            + "\n"
        )

        code, envelope = self.run_cli("reconcile")
        self.assertEqual(code, 0, envelope)
        self.assertNotIn("WORKTREE_MULTI_WRITER", [f["code"] for f in envelope["findings"]])

    def test_two_worktrees_dirty_but_only_one_on_research_passes(self) -> None:
        """Code-only changes on a sibling worktree are not a canonical-state conflict."""
        self.init_state()
        self._git("add", "-A")
        self._git("commit", "-qm", "research state")
        wt = self.add_worktree("code-only")

        (self.root / "research" / "ACTIVE.json").write_text(
            (self.root / "research" / "ACTIVE.json").read_text(encoding="utf-8")
            + "\n"
        )
        (wt / "src_scratch.py").write_text("x = 1\n", encoding="utf-8")

        code, envelope = self.run_cli("reconcile")
        self.assertEqual(code, 0, envelope)
        self.assertNotIn("WORKTREE_MULTI_WRITER", [f["code"] for f in envelope["findings"]])


if __name__ == "__main__":
    unittest.main()
