"""Real Git/CLI regressions motivated by the esa-study deployment.

These exercise recovery and evidence provenance at the user boundary; no model or
competition simulator is needed to reproduce these failures.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from researchlog import jgit, state
from researchlog.commands import telemetry


ENTRY = Path(__file__).resolve().parents[2] / "re"


class ProductionBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="re-production-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.git("init", "-q", "--initial-branch=main")
        self.git("config", "user.name", "RE regression")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.state = self.root / ".research"

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.root, check=True, capture_output=True, text=True
        ).stdout

    def cli(self, verb: str, *args: str) -> tuple[int, dict]:
        result = subprocess.run(
            [sys.executable, str(ENTRY), verb, "--json", *args],
            cwd=self.root, capture_output=True, text=True, timeout=20,
        )
        return result.returncode, json.loads(result.stdout)

    def init(self, *, legacy: bool = False) -> None:
        code, result = self.cli("init", *(["--legacy"] if legacy else []))
        self.assertEqual(code, 0, result)
        self.state = self.root / ("research" if legacy else ".research")

    def commit_all(self) -> None:
        self.git("add", ".")
        self.git("commit", "-qm", "fixture state")

    def record(self, *, counted: bool = False) -> tuple[int, dict]:
        return self.cli(
            "record", "--question", "Is the supplied dataset structurally usable?",
            "--subject-type", "dataset", "--subject-id", "esa-input",
            "--level", "E0", "--execution-status", "completed",
            "--research-outcome", "inconclusive", "--confidence", "low",
            "--observation", "Source inspection completed.", "--no-experiment",
            *(["--belief-delta", "refined"] if counted else []),
        )

    def test_switching_hypotheses_preserves_registered_history(self) -> None:
        self.init()
        code, result = self.cli("active", "--set", 'hypothesis_ids=["H-OLD"]')
        self.assertEqual(code, 0, result)
        code, result = self.cli("active", "--set", 'hypothesis_ids=["H-NEW"]',
                                "--set", 'chosen_hypothesis="H-NEW"')
        self.assertEqual(code, 0, result)
        active = json.loads((self.state / "ACTIVE.json").read_text())
        self.assertEqual(active["hypothesis_ids"], ["H-OLD", "H-NEW"])
        self.assertEqual(active["chosen_hypothesis"], "H-NEW")
        code, result = self.cli("active", "--set", 'hypothesis_ids=[]')
        self.assertEqual(code, 0, result)
        self.assertEqual(json.loads((self.state / "ACTIVE.json").read_text())["hypothesis_ids"],
                         ["H-OLD", "H-NEW"])

    def test_switching_hypotheses_rejects_invalid_registry_without_writing(self) -> None:
        self.init()
        before = (self.state / "ACTIVE.json").read_bytes()
        code, result = self.cli("active", "--set", 'hypothesis_ids=[123]')
        self.assertNotEqual(code, 0, result)
        self.assertEqual((self.state / "ACTIVE.json").read_bytes(), before)

    def test_dashboard_is_read_only_and_does_not_infer_liveness(self) -> None:
        self.init()
        self.commit_all()
        before = {str(p): p.read_bytes() for p in self.state.rglob('*') if p.is_file()}
        code, result = self.cli("dashboard")
        self.assertEqual(code, 0, result)
        self.assertEqual(result['payload']['liveness'], 'unknown')
        self.assertEqual(result['payload']['heartbeat'], 'unavailable')
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.state.rglob('*') if p.is_file()})
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_dashboard_surfaces_corrupt_evidence(self) -> None:
        self.init()
        (self.state / 'ledger/EV-broken.json').write_text('{')
        code, result = self.cli('dashboard')
        self.assertNotEqual(code, 0)
        self.assertTrue(result['findings'])

    def test_init_epoch_matches_session_log(self) -> None:
        self.init()
        active = json.loads((self.state / "ACTIVE.json").read_text())
        event = json.loads((self.state / "sessions.jsonl").read_text().splitlines()[0])
        self.assertIsNotNone(active["session_epoch"])
        self.assertEqual(active["session_epoch"], event["session_epoch"])

    def test_evidence_records_the_session_that_wrote_it(self) -> None:
        self.init()
        self.commit_all()
        code, result = self.record()
        self.assertEqual(code, 0, result)
        evidence = json.loads(Path(result["payload"]["path"]).read_text())
        active = json.loads((self.state / "ACTIVE.json").read_text())
        self.assertEqual(evidence.get("session_epoch"), active["session_epoch"])

    def test_same_second_rotation_keeps_evidence_in_its_own_session(self) -> None:
        stamp = "2026-09-21T00:00:00+00:00"
        events = [{"session_epoch": epoch, "started_at": stamp}
                  for epoch in ("SE-before", "SE-after")]
        ledger = state.Ledger(records={"EV-before": {
            "session_epoch": "SE-before", "created_at": stamp,
            "execution_status": "completed", "research_outcome": "inconclusive",
            "belief_delta": "refined",
        }})
        report = telemetry._cumulative_evidence_iterations(ledger, events)
        self.assertEqual([row["iterations"] for row in report["per_session"]], [1, 0])

    def test_real_rotation_counts_both_sessions_without_rewriting_history(self) -> None:
        self.init()
        self.commit_all()
        for session in range(2):
            if session:
                code, result = self.cli("active", "--rotate-session")
                self.assertEqual(code, 0, result)
            for _ in range(2):
                code, result = self.record(counted=True)
                self.assertEqual(code, 0, result)
        _, report = self.cli("telemetry")
        row = next(row for row in report["payload"]["kpis"]
                   if row["kpi"] == "cumulative_evidence_iterations")
        self.assertEqual(row["value"], 4)
        self.assertEqual([s["iterations"] for s in row["per_session"]], [2, 2])

    def test_merge_preserves_active_and_does_not_invent_a_session(self) -> None:
        self.init()
        code, result = self.cli(
            "active", "--set", 'git.expected_touched_files=["probe.py"]',
            "--set", 'git.checkpoint_commit="retained-checkpoint"',
        )
        self.assertEqual(code, 0, result)
        before = {name: (self.state / name).read_bytes()
                  for name in ("ACTIVE.json", "sessions.jsonl")}
        code, result = self.cli("init", "--merge")
        self.assertEqual(code, 0, result)
        for name, original in before.items():
            self.assertEqual((self.state / name).read_bytes(), original, name)

    def test_merge_reuses_legacy_state_instead_of_shadowing_it(self) -> None:
        self.init(legacy=True)
        code, result = self.cli("init", "--merge")
        self.assertEqual(code, 0, result)
        self.assertFalse((self.root / ".research").exists())
        self.assertEqual(Path(result["payload"]["research_dir"]), self.state)

    def test_merge_refuses_newer_schema_before_writing(self) -> None:
        self.init()
        path = self.state / "ACTIVE.json"
        active = json.loads(path.read_text())
        active["schema_version"] = "99.0"
        path.write_text(json.dumps(active))
        before = {p.name: p.read_bytes() for p in self.state.iterdir() if p.is_file()}
        code, result = self.cli("init", "--merge")
        self.assertEqual(code, 4, result)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.state.iterdir() if p.is_file()})

    def test_record_commits_only_evidence_and_preserves_staged_user_work(self) -> None:
        self.init()
        self.commit_all()
        path = self.root / "unfinished.txt"
        path.write_text("staged work belongs to the user\n")
        self.git("add", path.name)
        before = self.git("diff", "--cached", "--binary")
        code, result = self.record()
        self.assertEqual(code, 0, result)
        self.assertEqual(self.git("diff", "--cached", "--binary"), before)
        committed = self.git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines()
        self.assertEqual(committed, [str(Path(result["payload"]["path"]).relative_to(self.root))])

    def test_untracked_code_contents_change_provenance(self) -> None:
        self.init()
        self.commit_all()
        path = self.root / "probe.py"
        path.write_text("print(1)\n")
        first = jgit.code_state(self.root)
        path.write_text("print(2)\n")
        second = jgit.code_state(self.root)
        self.assertTrue(first.dirty and second.dirty)
        self.assertNotEqual(first.diff_sha256, second.diff_sha256)

    def test_checkpoint_preserves_unrelated_staged_work(self) -> None:
        self.init()
        self.commit_all()
        (self.root / "unfinished.txt").write_text("user work\n")
        self.git("add", "unfinished.txt")
        before = self.git("diff", "--cached", "--binary")
        code, result = self.cli("active", "--set-observation", "Ready to checkpoint.")
        self.assertEqual(code, 0, result)
        code, result = self.cli("checkpoint", "--paths", ".research/ACTIVE.json")
        self.assertEqual(code, 0, result)
        self.assertEqual(self.git("diff", "--cached", "--binary"), before)
        self.assertEqual(self.git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines(),
                         [".research/ACTIVE.json"])

    def test_checkpoint_unchanged_path_does_not_commit_unrelated_staged_work(self) -> None:
        self.init()
        self.commit_all()
        (self.root / "unfinished.txt").write_text("user work\n")
        self.git("add", "unfinished.txt")
        before = self.git("diff", "--cached", "--binary")
        previous_head = self.git("rev-parse", "HEAD")
        code, result = self.cli("checkpoint", "--paths", ".research/ACTIVE.json")
        self.assertEqual(code, 0, result)
        self.assertEqual(self.git("rev-parse", "HEAD"), previous_head)
        self.assertEqual(self.git("diff", "--cached", "--binary"), before)

    def test_compare_rejects_changed_committed_code(self) -> None:
        self.init()
        path = self.root / "probe.py"
        path.write_text("print(1)\n")
        self.commit_all()
        code, first = self.record()
        self.assertEqual(code, 0, first)
        path.write_text("print(2)\n")
        self.commit_all()
        code, second = self.record()
        self.assertEqual(code, 0, second)
        code, result = self.cli("compare", first["payload"]["evidence_id"], second["payload"]["evidence_id"])
        self.assertEqual(result["payload"]["attribute_verdict"], "ATTRIBUTION_FORBIDDEN")

    def test_compare_accepts_evidence_only_commits(self) -> None:
        self.init()
        self.commit_all()
        code, first = self.record()
        self.assertEqual(code, 0, first)
        code, second = self.record()
        self.assertEqual(code, 0, second)
        code, result = self.cli("compare", first["payload"]["evidence_id"], second["payload"]["evidence_id"])
        self.assertEqual(result["payload"]["attribute_verdict"], "COMPARABLE")

    def test_rotated_session_timing_uses_its_own_first_evidence(self) -> None:
        self.init()
        self.commit_all()
        code, result = self.cli("active", "--set", 'session_epoch="SE-20260921T000000Z-0000"')
        self.assertEqual(code, 0, result)
        document = {
            "schema_version": "1.0", "question": "Does the audit run?",
            "subject": {"type": "harness", "id": "esa-audit"}, "evidence_level": "E1",
            "execution_status": "completed", "research_outcome": "inconclusive",
            "confidence": "low", "observations": ["Probe completed."],
            "created_at": "2026-09-20T23:59:00+00:00",
        }
        code, result = self.cli("record", "--from-json", json.dumps(document))
        self.assertEqual(code, 0, result)
        _, report = self.cli("telemetry")
        row = next(row for row in report["payload"]["kpis"] if row["kpi"] == "time_to_first_e1")
        self.assertEqual(row["status"], "unavailable")
        document["created_at"] = "2026-09-21T00:00:07+00:00"
        code, result = self.cli("record", "--from-json", json.dumps(document))
        self.assertEqual(code, 0, result)
        _, report = self.cli("telemetry")
        row = next(row for row in report["payload"]["kpis"] if row["kpi"] == "time_to_first_e1")
        self.assertEqual(row["value"], 7.0)
        self.assertEqual(row["evidence_id"], result["payload"]["evidence_id"])

    def test_legacy_state_updates_do_not_change_code_identity(self) -> None:
        self.init(legacy=True)
        self.commit_all()
        code, result = self.cli("active", "--set-observation", "Waiting for real data.")
        self.assertEqual(code, 0, result)
        self.assertFalse(jgit.code_state(self.root).dirty)

    def test_dotted_state_updates_do_not_change_code_identity(self) -> None:
        self.init()
        self.commit_all()
        code, result = self.cli("active", "--set-observation", "Waiting for real data.")
        self.assertEqual(code, 0, result)
        self.assertFalse(jgit.code_state(self.root).dirty)

    def test_reconcile_reports_unexpected_paths_even_when_dirty_is_expected(self) -> None:
        self.init()
        self.commit_all()
        (self.root / "unplanned.py").write_text("print('unexpected')\n")
        code, result = self.cli("reconcile")
        self.assertNotEqual(code, 0, result)
        self.assertIn("ACTIVE_UNEXPECTED_PATHS", [f["code"] for f in result["findings"]])

    def test_reconcile_reports_branch_mismatch(self) -> None:
        self.init()
        self.commit_all()
        self.git("switch", "-qc", "different-work")
        code, result = self.cli("reconcile")
        self.assertNotEqual(code, 0, result)
        self.assertIn("ACTIVE_BRANCH_MISMATCH", [f["code"] for f in result["findings"]])

    def test_reconcile_reports_evidence_removed_from_index(self) -> None:
        self.init()
        self.commit_all()
        code, result = self.record()
        self.assertEqual(code, 0, result)
        path = Path(result["payload"]["path"])
        self.git("rm", "--cached", str(path.relative_to(self.root)))
        code, result = self.cli("reconcile")
        self.assertNotEqual(code, 0, result)
        self.assertIn("EVIDENCE_REMOVED_FROM_GIT", [f["code"] for f in result["findings"]])


if __name__ == "__main__":
    unittest.main()
