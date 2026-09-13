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
        code, envelope = self.run_cli("init", *extra)
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
        record = json.loads((self.root / "research" / "ledger" / f"{evidence_id}.json").read_text())
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


if __name__ == "__main__":
    unittest.main()
