"""End-to-end smoke tests for the command layer.

Each test drives the real CLI in a temporary repository and asserts on the JSON
envelope, because the envelope is the contract an agent branches on. The cases chosen are
the ones where getting the behaviour wrong is expensive rather than merely wrong:

* a failed experiment must not be reported as a failed tool;
* a command that never started must not leave a `result.json` behind;
* an expensive run must not be restarted by a session that lost its context;
* a status query must not dirty the working tree;
* `job` must never emit anything that kills a process.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path

from researchlog import cli

MISSING_BINARY = "researchlog-definitely-not-a-real-binary"


class CommandTestCase(unittest.TestCase):
    """A temporary repository with the canonical skeleton already in place."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        code, _ = self.invoke(["init"])
        self.assertEqual(code, 0, "init must succeed before any other command")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def invoke_raw(self, argv: list[str]) -> tuple[int, str]:
        """Run the CLI with --json and return (exit code, raw stdout).

        `--root` is a per-command flag, so it goes after the command name and before any
        sub-action or `--` separator.
        """
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(_with_json([argv[0], "--root", str(self.root), *argv[1:]]))
        return code, buffer.getvalue()

    def invoke(self, argv: list[str]) -> tuple[int, dict]:
        code, text = self.invoke_raw(argv)
        return code, (json.loads(text) if text.strip() else {})

    def research(self, *parts: str) -> Path:
        return self.root.joinpath("research", *parts)

    def run_dir(self, experiment_id: str) -> Path:
        return self.research("runs", experiment_id)

    def tree(self) -> dict[str, str]:
        """Every working-tree file under the root, content-hashed, so 'unchanged' is checkable.

        `.git/` is excluded: it is repository metadata, not the working tree, and Git may
        refresh the index as a side effect of a read-only query.
        """
        return {
            path.relative_to(self.root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(self.root.rglob("*"))
            if path.is_file() and ".git" not in path.relative_to(self.root).parts
        }

    def record_evidence(self, **overrides: str) -> str:
        argv = [
            "record",
            "--question",
            "does the mechanism hold?",
            "--subject-type",
            "mechanism",
            "--subject-id",
            "M-001",
            "--level",
            "E1",
            "--execution-status",
            "completed",
            "--research-outcome",
            "inconclusive",
            "--confidence",
            "low",
            "--observation",
            "the probe ran",
            "--no-experiment",
        ]
        for key, value in overrides.items():
            argv.extend([f"--{key.replace('_', '-')}", value])
        code, envelope = self.invoke(argv)
        self.assertEqual(code, 0, envelope)
        return str(envelope["payload"]["evidence_id"])


def _with_json(argv: list[str]) -> list[str]:
    """--json must precede a `--` separator, or it becomes part of the child command."""
    if "--" in argv:
        index = argv.index("--")
        return [*argv[:index], "--json", *argv[index:]]
    return [*argv, "--json"]


class GitCommandTestCase(CommandTestCase):
    """A checkpoint is a commit, so these tests need a repository to commit into."""

    def setUp(self) -> None:
        super().setUp()
        self.git("init", "-q")
        self.git("config", "user.email", "researchlog@example.invalid")
        self.git("config", "user.name", "researchlog tests")

    def git(self, *args: str) -> None:
        completed = subprocess.run(
            ["git", *args], cwd=str(self.root), capture_output=True, text=True, check=False
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


class RunCommandTests(CommandTestCase):
    def test_failed_child_is_scientific_data_not_a_tool_failure(self) -> None:
        code, envelope = self.invoke(["run", "--experiment-id", "EXP-smoke-false", "--", "false"])

        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["payload"]["child_exit_code"], 1)
        manifest = json.loads((self.run_dir("EXP-smoke-false") / "manifest.json").read_text())
        self.assertEqual(manifest["status"], "completed")
        self.assertTrue((self.run_dir("EXP-smoke-false") / "result.json").is_file())

    def test_command_that_cannot_start_writes_no_result(self) -> None:
        code, envelope = self.invoke(
            ["run", "--experiment-id", "EXP-smoke-missing", "--", MISSING_BINARY]
        )

        self.assertEqual(code, 5)
        self.assertEqual(envelope["findings"][0]["code"], "RUN_NOT_STARTED")
        manifest = json.loads((self.run_dir("EXP-smoke-missing") / "manifest.json").read_text())
        self.assertEqual(manifest["status"], "infra_failed")
        self.assertFalse((self.run_dir("EXP-smoke-missing") / "result.json").exists())

    def test_refuses_to_restart_an_experiment_whose_manifest_says_running(self) -> None:
        code, _ = self.invoke(
            ["manifest", "--experiment-id", "EXP-smoke-guard", "--status", "running"]
        )
        self.assertEqual(code, 0)

        code, envelope = self.invoke(["run", "--experiment-id", "EXP-smoke-guard", "--", "true"])

        self.assertEqual(code, 4)
        self.assertEqual(envelope["findings"][0]["code"], "EXPERIMENT_ALREADY_RUNNING")
        manifest = json.loads((self.run_dir("EXP-smoke-guard") / "manifest.json").read_text())
        self.assertEqual(manifest["status"], "running")

    def test_replace_existing_is_an_explicit_opt_in(self) -> None:
        self.invoke(["manifest", "--experiment-id", "EXP-smoke-replace", "--status", "running"])

        code, envelope = self.invoke(
            ["run", "--experiment-id", "EXP-smoke-replace", "--replace-existing", "--", "true"]
        )

        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["payload"]["child_exit_code"], 0)


class FindingsCommandTests(CommandTestCase):
    def test_add_then_render_check_reports_no_drift(self) -> None:
        evidence_id = self.record_evidence()

        code, envelope = self.invoke(
            [
                "findings",
                "add",
                "--title",
                "the probe is measurable",
                "--status",
                "Provisional",
                "--confidence",
                "low",
                "--evidence",
                evidence_id,
            ]
        )
        self.assertEqual(code, 0, envelope)

        code, envelope = self.invoke(["findings", "render", "--check"])
        self.assertEqual(code, 0, envelope)
        self.assertFalse(envelope["payload"]["drift"])

    def test_render_check_detects_a_hand_edited_block(self) -> None:
        """Editing the JSON by hand leaves the prose describing the old belief."""
        evidence_id = self.record_evidence()
        self.invoke(
            [
                "findings",
                "add",
                "--title",
                "T",
                "--status",
                "Provisional",
                "--confidence",
                "low",
                "--evidence",
                evidence_id,
            ]
        )
        findings_path = self.research("FINDINGS.md")
        findings_path.write_text(
            findings_path.read_text().replace('"title": "T"', '"title": "edited"')
        )
        before = findings_path.read_text()

        code, envelope = self.invoke(["findings", "render", "--check"])

        self.assertEqual(code, 3, envelope)
        self.assertTrue(envelope["payload"]["drift"])
        self.assertEqual(findings_path.read_text(), before, "--check must write nothing")

    def test_prose_outside_the_generated_region_survives(self) -> None:
        evidence_id = self.record_evidence()
        self.invoke(
            [
                "findings",
                "add",
                "--title",
                "T",
                "--status",
                "Provisional",
                "--confidence",
                "low",
                "--evidence",
                evidence_id,
            ]
        )
        findings_path = self.research("FINDINGS.md")
        findings_path.write_text(findings_path.read_text() + "\nhand written note\n")

        code, envelope = self.invoke(["findings", "render", "--check"])

        self.assertEqual(code, 0, envelope)
        self.assertFalse(envelope["payload"]["drift"])
        self.assertTrue(findings_path.read_text().endswith("hand written note\n"))

    def test_max_evidence_level_is_derived_not_asserted(self) -> None:
        evidence_id = self.record_evidence()

        code, envelope = self.invoke(
            [
                "findings",
                "add",
                "--title",
                "T",
                "--status",
                "Provisional",
                "--confidence",
                "low",
                "--evidence",
                evidence_id,
                "--max-evidence-level",
                "E4",
            ]
        )

        self.assertEqual(code, 2)
        self.assertEqual(envelope["findings"][0]["code"], "FINDING_LEVEL_MISMATCH")


class EnvCommandTests(CommandTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.change = self.root / "change.json"
        self.change.write_text(json.dumps({"changes": {"sim_physics_hz": 60}}), encoding="utf-8")

    def test_query_is_byte_identical_when_run_twice(self) -> None:
        _, first = self.invoke_raw(["env", "query", str(self.change)])
        _, second = self.invoke_raw(["env", "query", str(self.change)])

        self.assertEqual(first, second)
        self.assertTrue(first.strip())

    def test_query_does_not_touch_findings(self) -> None:
        before = self.tree()

        self.invoke(["env", "query", str(self.change)])

        self.assertEqual(before, self.tree())

    def test_record_appends_an_evidence_record_and_reports_the_closure(self) -> None:
        code, envelope = self.invoke(["env", "record", str(self.change)])

        self.assertEqual(code, 0, envelope)
        evidence_id = envelope["payload"]["recorded"]
        self.assertTrue(self.research("ledger", f"{evidence_id}.json").is_file())

        from researchlog import schema

        block = schema.require_block(
            self.research("ENVIRONMENT.md").read_text(), "environment", source="ENVIRONMENT.md"
        )
        history = block["history"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["type"], "environment_change")
        self.assertEqual(history[0]["evidence_id"], evidence_id)
        self.assertEqual(block["comparability"]["fingerprint"], envelope["payload"]["fingerprint"])

    def test_bare_positional_names_both_verbs(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            with contextlib.redirect_stderr(io.StringIO()):
                cli.main(["env", str(self.change), "--json"])

        self.assertEqual(caught.exception.code, 2)


class ActiveCommandTests(CommandTestCase):
    def test_set_preserves_an_unknown_field(self) -> None:
        active_path = self.research("ACTIVE.json")
        document = json.loads(active_path.read_text())
        document["x_annotations"] = {"owner": "architect", "keep": True}
        active_path.write_text(json.dumps(document, indent=2), encoding="utf-8")

        code, envelope = self.invoke(["active", "--set", "next_action=write the probe"])
        self.assertEqual(code, 0, envelope)

        updated = json.loads(active_path.read_text())
        self.assertEqual(updated["x_annotations"], {"owner": "architect", "keep": True})
        self.assertEqual(updated["next_action"], "write the probe")

    def test_close_block_requires_a_belief_delta(self) -> None:
        code, envelope = self.invoke(["active", "--close-block"])

        self.assertEqual(code, 2)
        self.assertEqual(envelope["findings"][0]["code"], "BLOCK_CLOSE_NEEDS_DELTA")

    def test_a_newer_schema_is_never_overwritten(self) -> None:
        active_path = self.research("ACTIVE.json")
        document = json.loads(active_path.read_text())
        document["schema_version"] = "9.0"
        active_path.write_text(json.dumps(document, indent=2), encoding="utf-8")
        before = active_path.read_text()

        code, envelope = self.invoke(["active", "--set", "next_action=should not land"])

        self.assertEqual(code, 4)
        self.assertEqual(envelope["findings"][0]["code"], "SCHEMA_NEWER_REFUSED")
        self.assertEqual(active_path.read_text(), before)


class SnapshotCommandTests(CommandTestCase):
    def test_a_snapshot_without_write_changes_nothing(self) -> None:
        before = self.tree()

        code, envelope = self.invoke(["snapshot"])

        self.assertEqual(code, 0, envelope)
        self.assertEqual(before, self.tree())
        self.assertNotIn("written", envelope["payload"])

    def test_write_must_stay_under_derived(self) -> None:
        code, envelope = self.invoke(["snapshot", "--write", str(self.root / "escape.json")])

        self.assertEqual(code, 4)
        self.assertEqual(envelope["findings"][0]["code"], "SNAPSHOT_PATH_OUTSIDE_DERIVED")

    def test_write_lands_in_derived(self) -> None:
        code, envelope = self.invoke(["snapshot", "--write", "fp.json"])

        self.assertEqual(code, 0, envelope)
        self.assertTrue((self.research(".derived", "fp.json")).is_file())


class JobCommandTests(CommandTestCase):
    def test_a_finalised_run_reports_completed(self) -> None:
        self.invoke(["run", "--experiment-id", "EXP-smoke-job", "--", "true"])

        code, envelope = self.invoke(["job", "--experiment-id", "EXP-smoke-job"])

        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["payload"]["liveness"], "completed")

    def test_a_dead_process_is_reported_never_killed(self) -> None:
        manifest_path = self.run_dir("EXP-smoke-dead") / "manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "experiment_id": "EXP-smoke-dead",
                    "status": "running",
                    "code_state": {},
                    "execution": {
                        "host": socket.gethostname(),
                        "launcher": "local_process",
                        "pid_or_job_id": "4194303",
                        "pid_started_at": "Mon Jan  1 00:00:00 2024",
                        "heartbeat_or_last_observed_at": None,
                        "stdout": None,
                        "stderr": None,
                        "expected_outputs": [],
                    },
                }
            ),
            encoding="utf-8",
        )

        code, envelope = self.invoke(["job", "--experiment-id", "EXP-smoke-dead"])

        self.assertEqual(code, 3, envelope)
        self.assertEqual(envelope["payload"]["liveness"], "dead_unfinalized")
        self.assertNotIn("kill", json.dumps(envelope["payload"]).lower())

    def test_an_unknown_launcher_is_not_guessed_at(self) -> None:
        manifest_path = self.run_dir("EXP-smoke-slurm") / "manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "experiment_id": "EXP-smoke-slurm",
                    "status": "running",
                    "code_state": {},
                    "execution": {
                        "host": None,
                        "launcher": "slurm",
                        "pid_or_job_id": "998877",
                        "started_at": None,
                        "heartbeat_or_last_observed_at": None,
                        "stdout": None,
                        "stderr": None,
                        "expected_outputs": [],
                    },
                }
            ),
            encoding="utf-8",
        )

        code, envelope = self.invoke(["job", "--experiment-id", "EXP-smoke-slurm"])

        self.assertEqual(code, 5)
        self.assertEqual(envelope["payload"]["liveness"], "unsupported_launcher")


class ReconcileCommandTests(CommandTestCase):
    def test_an_empty_research_directory_reconciles_clean(self) -> None:
        code, envelope = self.invoke(["reconcile"])

        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["findings"], [])
        self.assertTrue(envelope["payload"]["clean"])

    def test_the_closure_of_a_change_is_reported(self) -> None:
        evidence_id = self.record_evidence(**{"invalidated-if": "env.sim_physics_hz != 30"})
        change = self.root / "change.json"
        change.write_text(json.dumps({"changes": {"sim_physics_hz": 60}}), encoding="utf-8")

        code, envelope = self.invoke(["env", "query", str(change)])

        self.assertEqual(code, 3, envelope)
        self.assertEqual(
            [entry["evidence"] for entry in envelope["payload"]["invalidated"]], [evidence_id]
        )
        self.assertEqual(envelope["payload"]["counts"]["affected_findings"], 0)


class CompareCommandTests(CommandTestCase):
    def test_two_identical_records_are_comparable(self) -> None:
        document = {
            "question": "which of A and B?",
            "subject": {"type": "mechanism", "id": "M-001"},
            "evidence_level": "E2",
            "execution_status": "completed",
            "research_outcome": "inconclusive",
            "confidence": "low",
            "observations": ["ran"],
            "measurements": {"success_rate": 0.5},
            "environment": {
                "id": "ENV-1",
                "fingerprint": "sha256:abc",
                "comparability": "COMPATIBLE",
            },
            "inputs": {"replay_suite": "data-v3"},
            "code_state": {
                "branch": "main",
                "commit": "deadbeef",
                "base_commit": "deadbeef",
                "dirty": True,
                "diff_sha256": "sha256:same",
            },
            "counts_as_evidence_iteration": False,
        }
        first = self._record_document(document)
        second = self._record_document(document)

        code, envelope = self.invoke(["compare", first, second])

        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["payload"]["attribute_verdict"], "COMPARABLE")

    def test_moving_two_inputs_forbids_attribution(self) -> None:
        base = {
            "question": "which of A and B?",
            "subject": {"type": "mechanism", "id": "M-001"},
            "evidence_level": "E2",
            "execution_status": "completed",
            "research_outcome": "inconclusive",
            "confidence": "low",
            "observations": ["ran"],
            "environment": {
                "id": "ENV-1",
                "fingerprint": "sha256:abc",
                "comparability": "COMPATIBLE",
            },
            "inputs": {"replay_suite": "data-v3", "dataset": "d1"},
            "code_state": {
                "branch": "main",
                "commit": "c",
                "base_commit": "c",
                "dirty": False,
                "diff_sha256": None,
            },
            "counts_as_evidence_iteration": False,
        }
        first = self._record_document(base)
        second = self._record_document(
            {**base, "inputs": {"replay_suite": "data-v4", "dataset": "d2"}}
        )

        code, envelope = self.invoke(["compare", first, second])

        self.assertEqual(code, 3, envelope)
        self.assertEqual(envelope["payload"]["attribute_verdict"], "ATTRIBUTION_FORBIDDEN")

    def test_a_missing_record_is_a_precondition_failure(self) -> None:
        first = self.record_evidence()

        code, envelope = self.invoke(["compare", first, "EV-20260101T000000Z-0000"])

        self.assertEqual(code, 5)
        self.assertEqual(envelope["findings"][0]["code"], "EVIDENCE_NOT_FOUND")

    def _record_document(self, document: dict) -> str:
        code, envelope = self.invoke(["record", "--from-json", json.dumps(document)])
        self.assertEqual(code, 0, envelope)
        return str(envelope["payload"]["evidence_id"])


class CheckpointCommandTests(GitCommandTestCase):
    def test_dry_run_writes_nothing(self) -> None:
        before = self.tree()

        code, envelope = self.invoke(["checkpoint", "--dry-run"])

        self.assertEqual(code, 0, envelope)
        self.assertEqual(before, self.tree())
        self.assertTrue(envelope["payload"]["dry_run"])

    def test_paths_containing_dot_dot_are_refused(self) -> None:
        code, envelope = self.invoke(["checkpoint", "--dry-run", "--paths", "../../etc/passwd"])

        self.assertEqual(code, 4)
        self.assertEqual(envelope["findings"][0]["code"], "CHECKPOINT_PATH_ESCAPES_REPO")

    def test_a_protected_path_is_excluded(self) -> None:
        (self.research("runs", "EXP-x")).mkdir(parents=True, exist_ok=True)
        (self.research("runs", "EXP-x", "stdout.log")).write_text("noise", encoding="utf-8")

        code, envelope = self.invoke(["checkpoint", "--dry-run"])

        self.assertEqual(code, 0, envelope)
        self.assertNotIn("research/runs/EXP-x/stdout.log", envelope["payload"]["files"])
        self.assertIn("CHECKPOINT_PATH_PROTECTED", [f["code"] for f in envelope["findings"]])


class ManifestCommandTests(CommandTestCase):
    def test_heartbeat_touches_only_the_liveness_field(self) -> None:
        self.invoke(
            ["manifest", "--experiment-id", "EXP-hb", "--status", "running", "--input", "seed=1"]
        )
        path = self.run_dir("EXP-hb") / "manifest.json"
        before = json.loads(path.read_text())

        code, envelope = self.invoke(["manifest", "--experiment-id", "EXP-hb", "--heartbeat"])

        self.assertEqual(code, 0, envelope)
        after = json.loads(path.read_text())
        self.assertEqual(after["inputs"], before["inputs"])
        self.assertEqual(after["status"], before["status"])
        self.assertEqual(
            envelope["payload"]["changed"], ["execution.heartbeat_or_last_observed_at"]
        )
        self.assertNotEqual(
            after["execution"]["heartbeat_or_last_observed_at"],
            before["execution"]["heartbeat_or_last_observed_at"],
        )

    def test_heartbeat_without_a_manifest_is_a_precondition_failure(self) -> None:
        code, envelope = self.invoke(["manifest", "--experiment-id", "EXP-none", "--heartbeat"])

        self.assertEqual(code, 5)
        self.assertEqual(envelope["findings"][0]["code"], "MANIFEST_ABSENT")


if __name__ == "__main__":
    unittest.main()
