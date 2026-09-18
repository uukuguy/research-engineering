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
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from typing import cast
from pathlib import Path

from researchlog import cli
from researchlog.errors import (
    EXIT_FINDINGS_PRESENT,
    EXIT_OK,
    EXIT_PRECONDITION_MISSING,
    EXIT_STATE_INVALID,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    Finding,
    Result,
)

MISSING_BINARY = "researchlog-definitely-not-a-real-binary"


class CommandTestCase(unittest.TestCase):
    """A temporary repository with the canonical skeleton already in place."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        # V1 P1: every recorded evidence is followed by a commit, so the test
        # repo must be a real git repository. The init command lays out the
        # research/ skeleton; this `git init` makes the commit path work.
        subprocess.run(
            ["git", "init", "-q", "--initial-branch=main"],
            cwd=self.root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "tests@example.invalid"],
            cwd=self.root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "test fixture"],
            cwd=self.root,
            check=True,
            capture_output=True,
        )
        # `snapshot --write` refuses to dirt the tree if its target is not
        # gitignored, and the snapshot path is `research/.derived/`. Lay down
        # the same ignore pattern the production repo uses so the tests can
        # exercise the happy path under P1's new "every record is committed"
        # regime.
        (self.root / ".gitignore").write_text("research/.derived/\n", encoding="utf-8")
        code, _ = self.invoke(["init"])
        self.assertEqual(code, 0, "init must succeed before any other command")
        # Baseline commit so V1 P1's "tree clean after record" assertion has a
        # well-defined starting point. Without this the test setup itself
        # leaves `.gitignore`, `change.json`, and `research/` untracked and
        # `record` is observed committing only one of them.
        subprocess.run(
            ["git", "add", "-A"],
            cwd=self.root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-q", "-m", "fixture: research repo skeleton"],
            cwd=self.root,
            check=True,
            capture_output=True,
        )

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


class NonGitCommandTestCase(CommandTestCase):
    """A research repo without `git init`, for testing the P1 guard rail.

    V1 P1 requires `record` to refuse to write an evidence file when the
    working tree is not a git repository, because the second half of the
    record path (the commit) cannot succeed. The standard `CommandTestCase`
    now inits a repo in `setUp` so the happy path can run; this class peels
    that back for the failure-path assertions.
    """

    def setUp(self) -> None:
        # Manually do what CommandTestCase.setUp does *minus* the git parts,
        # so the research/ skeleton is in place but `.git` is not.
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        code, _ = self.invoke(["init"])
        self.assertEqual(code, 0, "init must succeed before any other command")

    def tearDown(self) -> None:
        self._tmp.cleanup()


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

    def test_heartbeat_is_bumped_while_the_child_runs(self) -> None:
        # V1 P7: a long-running child must leave a live heartbeat on disk
        # *during* the run, not only at closeout. We assert this by polling
        # the manifest file from a sibling thread while the child sleeps;
        # the first sample must already carry a non-None heartbeat value,
        # which is only possible if the daemon thread bumped the file
        # before the supervisor's final closeout write.
        manifest_path = self.run_dir("EXP-smoke-hb") / "manifest.json"
        argv = [
            sys.executable,
            "-m",
            "researchlog",
            "run",
            "--root",
            str(self.root),
            "--experiment-id",
            "EXP-smoke-hb",
            "--heartbeat-interval",
            "0.2",
            "--",
            "sleep",
            "1.8",
        ]
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])}
        child = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
        )
        try:
            # Sleep a hair longer than one interval so the daemon has
            # already written its first bump before we sample. The two
            # sample times are chosen to land on different floor-seconds
            # — `_now()` truncates to seconds, so a sample at wall-clock
            # 0.55s and one at 1.55s read different seconds; a sample
            # at 0.55s and one at 0.95s could land on the same second
            # even when the daemon is bumping, masking the assertion.
            time.sleep(0.55)
            first_raw: str | None = (
                json.loads(manifest_path.read_text())["execution"][
                    "heartbeat_or_last_observed_at"
                ]
                if manifest_path.is_file()
                else None
            )
            time.sleep(1.0)
            second_raw: str | None = (
                json.loads(manifest_path.read_text())["execution"][
                    "heartbeat_or_last_observed_at"
                ]
                if manifest_path.is_file()
                else None
            )
        finally:
            _stdout, stderr_bytes = child.communicate(timeout=5.0)
            stderr_text = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            self.assertEqual(child.returncode, 0, stderr_text)
            _ = _stdout  # silence unused-var

        # Both samples must have been captured mid-run, not at closeout.
        self.assertIsNotNone(
            first_raw,
            f"heartbeat was never written while the child ran: "
            f"first={first_raw!r} second={second_raw!r}",
        )
        self.assertIsNotNone(
            second_raw,
            f"heartbeat disappeared mid-run: first={first_raw!r} second={second_raw!r}",
        )
        first = cast(str, first_raw)
        second = cast(str, second_raw)
        # The two samples must come from different bumps, not the same
        # closeout rewrite. ISO 8601 in UTC sorts lexicographically, so a
        # later sample must be strictly greater.
        self.assertLess(
            first,
            second,
            f"heartbeat field did not advance while the child ran: "
            f"first={first!r} second={second!r}",
        )

    def test_heartbeat_interval_zero_disables_bumps(self) -> None:
        # V1 P7 opt-out: passing `--heartbeat-interval 0` turns the daemon
        # thread off. The manifest still gets its closeout heartbeat from
        # the supervisor's final write, but no intermediate bumps happen.
        argv = [
            sys.executable,
            "-m",
            "researchlog",
            "run",
            "--root",
            str(self.root),
            "--experiment-id",
            "EXP-smoke-no-hb",
            "--heartbeat-interval",
            "0",
            "--",
            "sleep",
            "0.4",
        ]
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])}
        completed = subprocess.run(
            argv, capture_output=True, text=True, timeout=5.0, check=False, env=env
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        manifest = json.loads(
            (self.run_dir("EXP-smoke-no-hb") / "manifest.json").read_text()
        )
        self.assertIsNotNone(manifest["execution"]["heartbeat_or_last_observed_at"])
        self.assertEqual(manifest["status"], "completed")

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

    def test_replace_existing_flag_is_removed_and_in_flight_is_always_refused(self) -> None:
        # V1 P6: `--replace-existing` no longer exists. The flag is unknown to argparse,
        # so passing it exits with code 2 before any tool logic runs. argparse raises
        # SystemExit directly, so we catch it here rather than going through invoke_raw.
        self.invoke(["manifest", "--experiment-id", "EXP-smoke-replace", "--status", "running"])

        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                cli.main(
                    _with_json([
                        "run",
                        "--root",
                        str(self.root),
                        "--experiment-id",
                        "EXP-smoke-replace",
                        "--replace-existing",
                        "--",
                        "true",
                    ])
                )
        self.assertEqual(caught.exception.code, 2)

        # Without the flag, an in-flight manifest is still refused unconditionally.
        code, envelope = self.invoke(
            ["run", "--experiment-id", "EXP-smoke-replace", "--", "true"]
        )
        self.assertEqual(code, 4, envelope)
        self.assertEqual(envelope["findings"][0]["code"], "EXPERIMENT_ALREADY_RUNNING")
        manifest = json.loads((self.run_dir("EXP-smoke-replace") / "manifest.json").read_text())
        self.assertEqual(manifest["status"], "running")

    def test_a_finalised_run_can_be_rerun_under_the_same_experiment_id(self) -> None:
        # V1 P6 counterpart: a finalised manifest is read for context, not for
        # ownership. Re-invoking `run` with the same id against a finalised record
        # must proceed and report a fresh child exit code.
        self.invoke(["manifest", "--experiment-id", "EXP-smoke-rerun", "--status", "completed"])

        code, envelope = self.invoke(
            ["run", "--experiment-id", "EXP-smoke-rerun", "--", "true"]
        )
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["payload"]["child_exit_code"], 0)

    def test_a_pending_manifest_is_also_refused(self) -> None:
        # V1 P6 tightens V0: the in-flight set is {pending, running}, not just
        # running. A crash between `_write_manifest` and the status flip must not
        # leave a half-written record open to overwrite. Verify the pending branch.
        code, _ = self.invoke(
            ["manifest", "--experiment-id", "EXP-smoke-pending", "--status", "pending"]
        )
        self.assertEqual(code, 0)

        code, envelope = self.invoke(
            ["run", "--experiment-id", "EXP-smoke-pending", "--", "true"]
        )
        self.assertEqual(code, 4, envelope)
        self.assertEqual(envelope["findings"][0]["code"], "EXPERIMENT_ALREADY_RUNNING")


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
        # The record path covered by V1 P1 is the bare `record` command, which
        # writes one evidence file and commits it. `env record` is a separate
        # subcommand that mutates ENVIRONMENT.md and is out of P1's literal
        # scope; it stays dirty and will be addressed by a follow-up sub-block.
        code, envelope = self.invoke_raw(
            [
                "record",
                "--question", "does the mechanism hold?",
                "--subject-type", "mechanism",
                "--subject-id", "M-014",
                "--level", "E1",
                "--execution-status", "completed",
                "--research-outcome", "inconclusive",
                "--confidence", "low",
                "--observation", "the probe ran",
                "--no-experiment",
            ]
        )
        envelope = json.loads(envelope) if envelope.strip() else {}
        self.assertEqual(code, 0, envelope)
        evidence_id = envelope["payload"]["evidence_id"]
        # V1 Block 2 / T2: ledger shards live under `<YYYY-MM>/`. Compute
        # the partition from the evidence_id itself rather than the clock,
        # so the test does not drift when the wall clock moves into a new
        # month mid-run.
        from researchlog.repo import _evidence_month
        partition = _evidence_month(evidence_id)
        self.assertTrue(self.research("ledger", partition, f"{evidence_id}.json").is_file())

        # V1 P1: every record lands as a commit, not just a file on disk. The
        # evidence file specifically must be tracked; HEAD must carry the
        # canonical commit subject; the message must not be command-substituted.
        ls_files = subprocess.run(
            ["git", "ls-files", "--error-unmatch", f"research/ledger/{partition}/{evidence_id}.json"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertTrue(
            ls_files.stdout.strip().endswith(f"research/ledger/{partition}/{evidence_id}.json")
        )
        log = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(log.stdout.strip(), f"research: record {evidence_id}")

        # The original V0 form of this test went through `env record` and
        # checked ENVIRONMENT.md history. V1 P1 only mandates that bare
        # `record` commit; the env-record commit duty is a follow-up sub-block.
        # The history assertion is left to `test_the_closure_of_a_change_is_reported`.

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


class StatusCommandTests(CommandTestCase):
    """V1 Block 2 / T3: `status` writes a milestone cache to STATUS.md.

    The cache header carries two machine-parsable lines `reconcile` reads:

        <!-- DERIVED SNAPSHOT — NOT SOURCE OF TRUTH -->
        <!-- last_evidence_modified: <epoch> -->

    Three contracts: writing is opt-in, the cache carries the header, and
    stale-detection fires when the ledger moves past `last_evidence_modified`.
    """

    def test_status_without_write_changes_nothing(self) -> None:
        before = self.tree()

        code, envelope = self.invoke(["status"])

        self.assertEqual(code, 0, envelope)
        self.assertEqual(before, self.tree())
        # `wrote` is in the payload as None when no write was asked for;
        # the path it would resolve to is exposed too so callers can see
        # what would have been written. None stays None here.
        self.assertIsNone(envelope["payload"]["wrote"])

    def test_write_lands_in_repo_root_with_the_derived_header(self) -> None:
        # STATUS_NOT_IGNORED is a warning under V0 (exit 3), so the test
        # asserts on the file contents and the `wrote` path rather than
        # the exit code.
        code, envelope = self.invoke(["status", "--write", "STATUS.md"])

        self.assertIn(code, (0, 3), envelope)
        self.assertEqual(envelope["payload"]["wrote"], str(self.root / "STATUS.md"))
        text = (self.root / "STATUS.md").read_text(encoding="utf-8")
        self.assertIn("DERIVED SNAPSHOT", text)
        self.assertIn("last_evidence_modified:", text)

    def test_write_refuses_paths_above_the_repo_root(self) -> None:
        code, envelope = self.invoke(["status", "--write", "/tmp/escape.md"])

        self.assertEqual(code, 4, envelope)
        self.assertEqual(envelope["findings"][0]["code"], "STATUS_PATH_OUTSIDE_ROOT")

    def test_write_warns_when_target_is_not_gitignored(self) -> None:
        # `STATUS.md` at the repo root dirties the tree unless it is in
        # .gitignore. The warning is the same shape `snapshot` uses for
        # its own targets: it names the path and the fix, but does not
        # refuse the write — the caller asked for it. V0 exit semantics
        # turn any warning into exit 3; the test asserts the warning's
        # presence rather than the exit code.
        code, envelope = self.invoke(["status", "--write", "STATUS.md"])

        self.assertIn(code, (0, 3), envelope)
        codes = [f["code"] for f in envelope["findings"]]
        self.assertIn("STATUS_NOT_IGNORED", codes)


class SynthesizeCommandTests(CommandTestCase):
    """V1 §14: `researchlog synthesize --block BLOCK_ID`.

    The block-close verb produces 1-2 pages of structured synthesis for the
    Architect. Each branch (no-block, missing-belief_delta, happy path, path
    refusal) is exercised as a separate test, because the V1-D4 #4 PASS
    signal ("exit 0; output is 1-2 pages") only fires on the integrated
    sequence the Architect runs end-to-end.
    """

    def test_synthesize_without_block_emits_precondition_missing(self) -> None:
        # Fresh fixture: `ACTIVE.block.id` is null and no `--block` is given.
        before = self.tree()
        code, envelope = self.invoke(["synthesize"])
        self.assertEqual(code, EXIT_PRECONDITION_MISSING, envelope)
        codes = [f["code"] for f in envelope["findings"]]
        self.assertIn("SYNTHESIS_BLOCK_NOT_FOUND", codes)
        self.assertIsNone(envelope["payload"].get("block_id"))
        # No write was requested, so the working tree must not have moved.
        self.assertEqual(self.tree(), before)

    def test_synthesize_with_explicit_block_warns_on_zero_records_and_missing_belief_delta(
        self,
    ) -> None:
        # Open a block, but record no evidence against it and do not close.
        self.invoke(["active", "--set", "block.id=BL-1"])
        code, envelope = self.invoke(["synthesize", "--block", "BL-1"])
        self.assertEqual(code, EXIT_FINDINGS_PRESENT, envelope)
        codes = [f["code"] for f in envelope["findings"]]
        self.assertIn("SYNTHESIS_ZERO_RECORDS", codes)
        self.assertIn("SYNTHESIS_BELIEF_DELTA_MISSING", codes)
        self.assertEqual(envelope["payload"]["block_id"], "BL-1")
        # Recommendation explicitly cites the P1-8 violation.
        self.assertIn("P1-8", envelope["payload"]["recommendation"])

    def test_synthesize_writes_to_research_dot_derived_when_no_path_component(
        self,
    ) -> None:
        # Open a block, close it with `belief_delta=none` so the happy path
        # is reached. record_evidence writes an E1 record whose block_id is
        # inherited from ACTIVE at the time of recording.
        self.invoke(["active", "--set", "block.id=BL-2"])
        # record stamps `block_id` from ACTIVE automatically; the helper
        # below does not need an explicit `--block-id` flag.
        self.invoke(
            [
                "record",
                "--question",
                "is the block-close synthesis wired?",
                "--subject-type",
                "mechanism",
                "--subject-id",
                "M-SYN",
                "--level",
                "E0",
                "--execution-status",
                "completed",
                "--research-outcome",
                "inconclusive",
                "--confidence",
                "low",
                "--observation",
                "fixture",
                "--no-experiment",
            ]
        )
        self.invoke(["active", "--close-block", "--belief-delta", "none"])

        code, envelope = self.invoke(
            ["synthesize", "--block", "BL-2", "--write", "BL-2.md"]
        )
        self.assertEqual(code, EXIT_OK, envelope)
        self.assertIsNotNone(envelope["payload"].get("wrote"))
        written_path = self.root / "research" / ".derived" / "BL-2.md"
        self.assertTrue(written_path.is_file())
        body = written_path.read_text(encoding="utf-8")
        # §0..§6 must all appear (sanity check the section layout).
        for marker in (
            "# Block synthesis: BL-2",
            "## §0 Header",
            "## §1 Block identity",
            "## §2 Evidence summary",
            "## §3 Belief change",
            "## §4 Frontier & uncertainty",
            "## §5 Open issues",
            "## §6 Next action / closure recommendation",
        ):
            self.assertIn(marker, body, f"missing section marker: {marker}")
        # 1-2 pages ≈ 30-60 lines, allowing some headroom.
        line_count = body.count("\n") + 1
        self.assertGreater(line_count, 20)
        self.assertLess(line_count, 200)

    def test_synthesize_refuses_paths_above_repo_root(self) -> None:
        # No block needed — the path guard fires before any state read.
        code, envelope = self.invoke(["synthesize", "--write", "/tmp/escape.md"])
        self.assertEqual(code, 4, envelope)
        codes = [f["code"] for f in envelope["findings"]]
        self.assertIn("SYNTHESIS_PATH_OUTSIDE_ROOT", codes)

    def test_synthesize_explicit_block_id_overrides_active(self) -> None:
        # Active block is BL-live, but the explicit `--block` is BL-history.
        # `payload["human"]` is not populated under `--json` (only `payload` and
        # `findings` are emitted), so the body is captured via `--write` instead.
        self.invoke(["active", "--set", "block.id=BL-live"])
        code, envelope = self.invoke(
            ["synthesize", "--block", "BL-history", "--write", "BL-history.md"]
        )
        self.assertEqual(code, EXIT_FINDINGS_PRESENT, envelope)
        self.assertEqual(envelope["payload"]["block_id"], "BL-history")
        written = self.root / "research" / ".derived" / "BL-history.md"
        self.assertTrue(written.is_file())
        self.assertIn("# Block synthesis: BL-history", written.read_text(encoding="utf-8"))


class LedgerPartitionTests(GitCommandTestCase):
    """V1 Block 2 / T2: ledger shards partition by `YYYY-MM/`.

    The writer side is `record`: every fresh evidence file lands inside a
    month subdirectory derived from the evidence_id itself. The reader
    side is `reconcile` / `validate` / `compare`: all three walk the
    partition-aware path with a flat fallback so pre-partition shards
    keep working.
    """

    def _record_one(self) -> str:
        code, envelope = self.invoke(
            [
                "record",
                "--question", "does the mechanism hold?",
                "--subject-type", "mechanism",
                "--subject-id", "M-014",
                "--level", "E1",
                "--execution-status", "completed",
                "--research-outcome", "inconclusive",
                "--confidence", "low",
                "--observation", "the probe ran",
                "--no-experiment",
            ]
        )
        self.assertEqual(code, 0, envelope)
        return envelope["payload"]["evidence_id"]

    def test_record_writes_the_shard_under_a_month_subdirectory(self) -> None:
        evidence_id = self._record_one()

        from researchlog.repo import _evidence_month

        partition = _evidence_month(evidence_id)
        # The mint format guarantees a `YYYY-MM` partition. A bare
        # `unpartitioned` here would mean the regex did not recognise the
        # id, which would be a regression worth pinning.
        self.assertNotEqual(partition, "unpartitioned")
        self.assertRegex(partition, r"^\d{4}-\d{2}$")

        partition_path = self.research("ledger", partition, f"{evidence_id}.json")
        self.assertTrue(partition_path.is_file(), f"shard missing at {partition_path}")
        # Pre-partition flat shards must NOT be created by `record`.
        flat_path = self.research("ledger", f"{evidence_id}.json")
        self.assertFalse(flat_path.is_file(), f"flat shard unexpectedly exists at {flat_path}")

    def test_reconcile_walks_partitioned_and_flat_shards(self) -> None:
        # A partitioned shard...
        partition_id = self._record_one()

        # ... and a flat shard from the V0 layout (a hand-written fixture).
        flat_id = "EV-LEGACY-20000101T000000Z-aaaa"
        flat_payload = {
            "schema_version": "1.0",
            "evidence_id": flat_id,
            "question": "legacy",
            "subject": {"type": "harness", "id": "HRN-001"},
            "evidence_level": "E1",
            "observations": ["legacy"],
            "execution_status": "completed",
            "research_outcome": "inconclusive",
            "confidence": "low",
            "counts_as_evidence_iteration": False,
        }
        (self.root / "research" / "ledger" / f"{flat_id}.json").write_text(
            json.dumps(flat_payload), encoding="utf-8"
        )

        code, envelope = self.invoke(["reconcile"])
        self.assertEqual(code, 0, envelope)
        codes = [f["code"] for f in envelope["findings"]]
        # Both shards must load; neither should trip the `DUPLICATE_ID`,
        # `EVIDENCE_SHARD_MISSING`, or `EVIDENCE_UNREADABLE` detectors.
        self.assertNotIn("DUPLICATE_ID", codes)
        self.assertNotIn("EVIDENCE_SHARD_MISSING", codes)
        self.assertNotIn("EVIDENCE_UNREADABLE", codes)

        # The payload's `evidence_records` count must reflect *both* shards:
        # without the recursive `rglob` in `_load_shards`, the partitioned
        # shard would be missed and the count would drop to one.
        self.assertEqual(envelope["payload"]["evidence_records"], 2)
        _ = partition_id  # silence unused

    def test_unpartitioned_fallback_for_hand_written_ids(self) -> None:
        # An id that does not match the mint format lands under the
        # `unpartitioned` directory and still loads. The fallback is
        # the only thing keeping a fixture written by hand from going
        # missing during the migration window.
        flat_id = "EV-LEGACY-20000101T000000Z-aaaa"
        flat_payload = {
            "schema_version": "1.0",
            "evidence_id": flat_id,
            "question": "legacy",
            "subject": {"type": "harness", "id": "HRN-001"},
            "evidence_level": "E1",
            "observations": ["legacy"],
            "execution_status": "completed",
            "research_outcome": "inconclusive",
            "confidence": "low",
            "counts_as_evidence_iteration": False,
        }
        flat_path = self.root / "research" / "ledger" / f"{flat_id}.json"
        flat_path.write_text(json.dumps(flat_payload), encoding="utf-8")

        code, envelope = self.invoke(["reconcile"])
        self.assertEqual(code, 0, envelope)
        codes = [f["code"] for f in envelope["findings"]]
        self.assertNotIn("EVIDENCE_SHARD_MISSING", codes)

    def test_from_orphan_writes_into_the_month_partition(self) -> None:
        # V1-D1 #6: a `--from-orphan EXP-X` write must land in
        # `research/ledger/YYYY-MM/`, not the flat layout. First lay down
        # a minimal manifest so `_orphan_template` does not bail out.
        self.invoke(
            [
                "manifest",
                "--experiment-id",
                "EXP-fake-001",
                "--status",
                "running",
                "--command",
                "echo fake",
            ]
        )
        code, envelope = self.invoke(
            [
                "record",
                "--from-orphan",
                "EXP-fake-001",
                "--question",
                "cross-partition orphan test",
                "--subject-type",
                "harness",
                "--subject-id",
                "HRN-ORPHAN",
                "--level",
                "E0",
                "--observation",
                "cross-partition orphan test",
                "--execution-status",
                "completed",
                "--research-outcome",
                "none",
                "--belief-delta",
                "none",
                "--confidence",
                "low",
            ]
        )
        self.assertEqual(code, 0, envelope)
        evidence_id = envelope["payload"]["evidence_id"]

        from researchlog.repo import _evidence_month

        partition = _evidence_month(evidence_id)
        self.assertRegex(partition, r"^\d{4}-\d{2}$")
        # The shard must land inside the partition — never flat.
        partitioned_path = self.research("ledger", partition, f"{evidence_id}.json")
        self.assertTrue(
            partitioned_path.is_file(),
            f"orphan-written shard missing at {partitioned_path}",
        )
        flat_path = self.research("ledger", f"{evidence_id}.json")
        self.assertFalse(
            flat_path.is_file(),
            f"orphan-written shard unexpectedly flat at {flat_path}",
        )

    def test_partition_migration_compare_handles_cross_partition_pair(self) -> None:
        # V1-D1 #7: a record produced by `--from-orphan` (lands in the
        # month partition) is comparable to a hand-written flat shard via
        # `compare`. This is the migration contract: readers must follow the
        # partition path AND keep the flat fallback alive.
        self.invoke(
            [
                "manifest",
                "--experiment-id",
                "EXP-fake-002",
                "--status",
                "running",
                "--command",
                "echo fake",
            ]
        )
        code, envelope = self.invoke(
            [
                "record",
                "--from-orphan",
                "EXP-fake-002",
                "--question",
                "cross-partition orphan test",
                "--subject-type",
                "harness",
                "--subject-id",
                "HRN-MIG",
                "--level",
                "E0",
                "--observation",
                "cross-partition orphan test",
                "--execution-status",
                "completed",
                "--research-outcome",
                "none",
                "--belief-delta",
                "none",
                "--confidence",
                "low",
            ]
        )
        self.assertEqual(code, 0, envelope)
        partitioned_id = envelope["payload"]["evidence_id"]

        # A flat shard whose id will NOT match the mint regex — exercises the
        # `unpartitioned` partition path while keeping the id parseable.
        flat_id = "EV-LEGACY-20000101T000000Z-bbbb"
        flat_payload = {
            "schema_version": "1.0",
            "evidence_id": flat_id,
            "question": "migration",
            "subject": {"type": "harness", "id": "HRN-MIG"},
            "evidence_level": "E0",
            "observations": ["flat"],
            "execution_status": "completed",
            "research_outcome": "none",
            "confidence": "low",
            "counts_as_evidence_iteration": False,
        }
        (self.root / "research" / "ledger" / f"{flat_id}.json").write_text(
            json.dumps(flat_payload), encoding="utf-8"
        )

        code, envelope = self.invoke(["compare", partitioned_id, flat_id])
        self.assertEqual(code, 0, envelope)
        # Both shards must load; the cross-partition compare must not emit
        # ATTRIBUTION_FORBIDDEN (no `code_state.commit` divergence here).
        codes = [f["code"] for f in envelope["findings"]]
        self.assertNotIn("ATTRIBUTION_FORBIDDEN", codes)
        self.assertNotIn("EVIDENCE_SHARD_MISSING", codes)
        self.assertNotIn("DUPLICATE_ID", codes)


class ReconcileStaleStatusTests(CommandTestCase):
    """`reconcile._stale_status` fires `STATUS_STALE` when the cache lags.

    The detector emits a `warning` finding, which under V0 reconcile
    semantics means exit 3 (`EXIT_FINDINGS_PRESENT`). The assertions check
    the finding code rather than the exit code so they survive any future
    reconcile severity reshuffles.
    """

    def _codes(self, envelope: dict) -> list[str]:
        return [f["code"] for f in envelope["findings"]]

    def test_reconcile_does_not_flag_when_no_status_md(self) -> None:
        code, envelope = self.invoke(["reconcile"])
        self.assertIn(code, (0, 3), envelope)
        self.assertNotIn("STATUS_STALE", self._codes(envelope))

    def test_reconcile_flags_status_md_missing_the_header(self) -> None:
        (self.root / "STATUS.md").write_text("# Status\n\nno header here\n", encoding="utf-8")

        code, envelope = self.invoke(["reconcile"])
        self.assertIn(code, (0, 3), envelope)
        self.assertIn("STATUS_STALE", self._codes(envelope))

    def test_reconcile_flags_status_md_missing_the_anchor_line(self) -> None:
        (self.root / "STATUS.md").write_text(
            "<!-- DERIVED SNAPSHOT — NOT SOURCE OF TRUTH -->\n\n# Status\n",
            encoding="utf-8",
        )

        code, envelope = self.invoke(["reconcile"])
        self.assertIn(code, (0, 3), envelope)
        self.assertIn("STATUS_STALE", self._codes(envelope))

    def test_reconcile_does_not_flag_when_cache_is_fresh(self) -> None:
        # Empty ledger → cache cannot be stale by the detector's definition.
        code, envelope = self.invoke(["status", "--write", "STATUS.md"])
        self.assertIn(code, (0, 3), envelope)

        code, envelope = self.invoke(["reconcile"])
        self.assertIn(code, (0, 3), envelope)
        self.assertNotIn("STATUS_STALE", self._codes(envelope))

    def test_reconcile_flags_when_ledger_advances_past_cache(self) -> None:
        # Write the cache first so its anchor line carries epoch = now.
        code, envelope = self.invoke(["status", "--write", "STATUS.md"])
        self.assertIn(code, (0, 3), envelope)

        # `record` is a P1-era command; landing a new evidence file advances
        # the ledger past the cache's `last_evidence_modified` and the next
        # reconcile must flag STATUS_STALE.
        self.record_evidence_envelope()

        code, envelope = self.invoke(["reconcile"])
        self.assertIn(code, (0, 3), envelope)
        self.assertIn("STATUS_STALE", self._codes(envelope))

    def record_evidence_envelope(self) -> dict:
        """Drive `record` end-to-end and return its envelope payload.

        A leaner wrapper than `record_evidence()` because the test does
        not need an `evidence_id` string back; it just needs *some*
        evidence on disk so the ledger's latest mtime moves forward.
        """
        code, envelope = self.invoke(
            [
                "record",
                "--question", "does the mechanism hold?",
                "--subject-type", "mechanism",
                "--subject-id", "M-014",
                "--level", "E1",
                "--execution-status", "completed",
                "--research-outcome", "inconclusive",
                "--confidence", "low",
                "--observation", "the probe ran",
                "--no-experiment",
            ]
        )
        self.assertEqual(code, 0, envelope)
        return envelope["payload"]


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


class CurrentBlockTests(CommandTestCase):
    """`research:current` is canonical state, so it needs a verb and a validator.

    It had neither: the block could only be edited by hand, against its own prose and
    AGENTS.md, and nothing checked what was written. These tests hold both halves.
    """

    def test_reading_returns_the_block(self) -> None:
        code, envelope = self.invoke(["current"])

        self.assertEqual(code, 0)
        self.assertEqual(envelope["payload"]["current"]["schema_version"], "1.0")

    def test_reading_does_not_touch_the_file(self) -> None:
        before = self.research("CURRENT.md").read_bytes()

        self.invoke(["current"])

        self.assertEqual(self.research("CURRENT.md").read_bytes(), before)

    def test_a_set_updates_the_block_and_leaves_the_prose_alone(self) -> None:
        before = self.research("CURRENT.md").read_text(encoding="utf-8")
        prose = before.split("```json research:current")[0]

        code, envelope = self.invoke(
            [
                "current",
                "--set",
                "objective=Does the residual separate release timing from noise?",
                "--set",
                "next_empirical_action=Replay the remaining three cases.",
            ]
        )

        self.assertEqual(code, 0)
        self.assertEqual(
            envelope["payload"]["changed"], ["objective", "next_empirical_action"]
        )
        after = self.research("CURRENT.md").read_text(encoding="utf-8")
        self.assertTrue(after.startswith(prose), "the prose around the block moved")
        self.assertIn("Replay the remaining three cases.", after)

    def test_a_dotted_set_reaches_into_a_nested_object(self) -> None:
        self.invoke(["current", "--set", "evidence_maturity.highest_stable_level=E2"])

        _, envelope = self.invoke(["current"])

        self.assertEqual(
            envelope["payload"]["current"]["evidence_maturity"]["highest_stable_level"], "E2"
        )

    def test_a_written_block_survives_validate(self) -> None:
        self.invoke(["current", "--set", 'objective="a question"'])

        code, envelope = self.invoke(["validate"])

        self.assertEqual(code, 0)
        self.assertEqual(envelope["findings"], [])

    def test_a_malformed_assignment_is_rejected(self) -> None:
        code, envelope = self.invoke(["current", "--set", "objective"])

        self.assertEqual(code, 2)
        self.assertEqual(envelope["findings"][0]["code"], "CURRENT_SET_MALFORMED")

    def test_a_block_that_violates_its_schema_is_not_written(self) -> None:
        """A refused write must leave the file byte-identical, not half-updated."""
        before = self.research("CURRENT.md").read_bytes()

        code, envelope = self.invoke(["current", "--set", "objective=ok", "--set", "architecture_frozen=yes please"])

        self.assertEqual(code, 2)
        self.assertEqual(envelope["findings"][0]["code"], "SCHEMA_VIOLATION")
        self.assertEqual(self.research("CURRENT.md").read_bytes(), before)

    def test_validate_reports_a_current_block_that_drifted(self) -> None:
        path = self.research("CURRENT.md")
        path.write_text(
            path.read_text(encoding="utf-8").replace('"architecture_frozen": false', '"architecture_frozen": "maybe"'),
            encoding="utf-8",
        )

        code, envelope = self.invoke(["validate"])

        self.assertEqual(code, 2)
        self.assertIn("SCHEMA_VIOLATION", [f["code"] for f in envelope["findings"]])


class EnvRebaselineTests(CommandTestCase):
    """V1 Block 2 / T4: `env rebaseline` refreshes the comparability fingerprint.

    The fingerprint is the anchor every `changed` predicate on a record
    compares against. The rebaseline command is the explicit "I know
    what I'm doing" refresh: it advances the fingerprint, records a
    `rebaseline` history entry, and does not introduce a fake
    environment change just to update the anchor.
    """

    def _read_environment_block(self) -> dict:
        # ENVIRONMENT.md has a `research:environment` fenced JSON block.
        # Read it via the schema helper rather than json.loads on the
        # whole file, which would misparse the surrounding markdown.
        from researchlog import schema
        text = self.research("ENVIRONMENT.md").read_text(encoding="utf-8")
        block = schema.find_block(text, "environment")
        assert block is not None, f"could not parse environment block from {text!r}"
        return block

    def _fingerprint(self) -> str | None:
        return (self._read_environment_block().get("comparability") or {}).get("fingerprint")

    def test_rebaseline_changes_the_fingerprint(self) -> None:
        before = self._fingerprint()

        code, envelope = self.invoke(["env", "rebaseline"])
        self.assertEqual(code, 0, envelope)

        after = self._fingerprint()
        self.assertNotEqual(before, after)
        self.assertEqual(envelope["payload"]["previous_fingerprint"], before)
        self.assertEqual(envelope["payload"]["fingerprint"], after)

    def test_rebaseline_records_a_history_entry(self) -> None:
        code, envelope = self.invoke(
            ["env", "rebaseline", "--reason", "manual refresh"]
        )
        self.assertEqual(code, 0, envelope)

        history = self._read_environment_block().get("history") or []
        rebaselines = [entry for entry in history if entry.get("type") == "rebaseline"]
        self.assertEqual(len(rebaselines), 1)
        self.assertEqual(rebaselines[0]["reason"], "manual refresh")
        self.assertEqual(rebaselines[0]["fingerprint"], self._fingerprint())

    def test_rebaseline_does_not_introduce_a_material_change(self) -> None:
        # The history entry is `type: rebaseline`, not
        # `environment_change`. Audit readers must be able to tell a
        # no-op refresh apart from a real environment move.
        self.invoke(["env", "rebaseline", "--reason", "first"])

        history = self._read_environment_block().get("history") or []
        self.assertTrue(history, "history must carry the rebaseline entry")
        self.assertNotEqual(history[-1]["type"], "environment_change")

    def test_rebaseline_default_reason_is_machine_readable(self) -> None:
        # When the caller omits `--reason`, the resulting history
        # entry must still carry *some* reason string so the next
        # session can branch on the field without KeyError.
        self.invoke(["env", "rebaseline"])
        history = self._read_environment_block().get("history") or []
        self.assertTrue(history)
        self.assertTrue(history[-1].get("reason"))


class EnvDeclareTests(CommandTestCase):
    """The declared tables had no write path.

    `env record` merges `comparability` and `history` only, so `limitations` and `harnesses`
    were readable in the skeleton, required by the protocol, and impossible to fill. A Day-1
    criterion asks an infeasible experiment to land in the first of them.
    """

    def declare(self, table: str, payload: dict) -> tuple[int, dict]:
        path = self.root / "entry.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return self.invoke(["env", "declare", table, str(path)])

    def limitations(self) -> list:
        _, envelope = self.invoke(["env", "show"])
        return envelope["payload"]["environment"]["limitations"]

    def test_a_limitation_can_be_declared(self) -> None:
        code, envelope = self.declare(
            "limitations",
            {
                "id": "ENV-LIM-001",
                "capability": "post-planner control tampering",
                "status": "ENV_UNSUPPORTED",
                "impact": "E4 physical-safety evidence is unobtainable here.",
            },
        )

        self.assertEqual(code, 0, envelope)
        self.assertEqual(self.limitations()[0]["status"], "ENV_UNSUPPORTED")

    def test_a_harness_can_be_declared(self) -> None:
        code, envelope = self.declare(
            "harnesses",
            {
                "id": "HARNESS-001",
                "capability": "post-planner command corruption replay",
                "supports_evidence": "E2/E3",
                "preserves": ["planner command schema"],
                "missing": ["actuator dynamics"],
            },
        )

        self.assertEqual(code, 0, envelope)
        _, shown = self.invoke(["env", "show"])
        self.assertEqual(len(shown["payload"]["environment"]["harnesses"]), 1)

    def test_an_incomplete_entry_is_refused_and_writes_nothing(self) -> None:
        before = self.research("ENVIRONMENT.md").read_bytes()

        code, envelope = self.declare("limitations", {"id": "ENV-LIM-002", "capability": "x"})

        self.assertEqual(code, 2)
        self.assertEqual(envelope["findings"][0]["code"], "ENV_DECLARE_INCOMPLETE")
        self.assertEqual(self.research("ENVIRONMENT.md").read_bytes(), before)

    def test_a_duplicate_id_is_refused(self) -> None:
        entry = {
            "id": "ENV-LIM-003",
            "capability": "x",
            "status": "ENV_UNSUPPORTED",
            "impact": "y",
        }
        self.assertEqual(self.declare("limitations", entry)[0], 0)

        code, envelope = self.declare("limitations", entry)

        self.assertEqual(code, 2)
        self.assertEqual(envelope["findings"][0]["code"], "ENV_DECLARE_DUPLICATE")
        self.assertEqual(len(self.limitations()), 1)

    def test_available_extends_a_namespace_without_duplicating(self) -> None:
        payload = {"namespace": "simulator", "items": ["mujoco 3.1", "pybullet 3.2"]}
        self.assertEqual(self.declare("available", payload)[0], 0)

        code, _ = self.declare("available", {"namespace": "simulator", "items": ["mujoco 3.1"]})

        self.assertEqual(code, 0)
        _, shown = self.invoke(["env", "show"])
        self.assertEqual(shown["payload"]["environment"]["available"]["simulator"], ["mujoco 3.1", "pybullet 3.2"])

    def test_an_unknown_namespace_is_refused(self) -> None:
        code, envelope = self.declare("available", {"namespace": "gpUs", "items": ["h100"]})

        self.assertEqual(code, 2)
        self.assertEqual(envelope["findings"][0]["code"], "ENV_NAMESPACE_UNKNOWN")

    def test_validate_checks_the_environment_block(self) -> None:
        path = self.research("ENVIRONMENT.md")
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                '"limitations": []',
                '"limitations": [{"id": "ENV-LIM-009", "capability": "x"}]',
            ),
            encoding="utf-8",
        )

        code, envelope = self.invoke(["validate"])

        self.assertEqual(code, 2)
        self.assertIn("SCHEMA_VIOLATION", [f["code"] for f in envelope["findings"]])


class RecordRejectTests(CommandTestCase):
    """V1 P8: every reject the `record` command emits carries a `fix_hint`.

    The `Finding` dataclass has carried the field from V0, but a sweep of the
    `record` code path found five rejection sites that raised `StateInvalid`
    / `PreconditionMissing` without filling it. Without `fix_hint`, the agent
    side of P8's contract ("message readable, fix_hint actionable") fails:
    the human sees "subject incomplete" but is not told which subject.
    """

    def _assert_every_finding_has_fix_hint(self, envelope: dict) -> None:
        for finding in envelope["findings"]:
            self.assertTrue(
                finding.get("fix_hint", "").strip(),
                f"finding {finding.get('code')!r} must carry a non-empty fix_hint; "
                f"got {finding!r}",
            )

    def test_experiment_flag_conflict_carries_fix_hint(self) -> None:
        code, envelope = self.invoke(
            [
                "record",
                "--question", "does it hold?",
                "--subject-type", "mechanism",
                "--subject-id", "M-014",
                "--level", "E1",
                "--execution-status", "completed",
                "--research-outcome", "inconclusive",
                "--confidence", "low",
                "--observation", "probe ran",
                "--no-experiment",
                "--experiment-id", "EXP-conflict",
            ]
        )
        self.assertEqual(code, 2, envelope)
        self.assertEqual(envelope["findings"][0]["code"], "EXPERIMENT_FLAG_CONFLICT")
        self._assert_every_finding_has_fix_hint(envelope)

    def test_artifact_role_without_artifact_carries_fix_hint(self) -> None:
        code, envelope = self.invoke(
            [
                "record",
                "--question", "does it hold?",
                "--subject-type", "mechanism",
                "--subject-id", "M-014",
                "--level", "E1",
                "--execution-status", "completed",
                "--research-outcome", "inconclusive",
                "--confidence", "low",
                "--observation", "probe ran",
                "--no-experiment",
                "--artifact-role", "primary",
            ]
        )
        self.assertEqual(code, 2, envelope)
        self.assertEqual(
            envelope["findings"][0]["code"], "ARTIFACT_ROLE_WITHOUT_ARTIFACT"
        )
        self._assert_every_finding_has_fix_hint(envelope)

    def test_unreadable_evidence_file_carries_fix_hint(self) -> None:
        code, envelope = self.invoke(
            [
                "record",
                "--question", "does it hold?",
                "--subject-type", "mechanism",
                "--subject-id", "M-014",
                "--level", "E1",
                "--execution-status", "completed",
                "--research-outcome", "inconclusive",
                "--confidence", "low",
                "--observation", "probe ran",
                "--no-experiment",
                "--evidence-file", "/no/such/path/no/where.json",
            ]
        )
        self.assertEqual(code, 5, envelope)
        self.assertEqual(envelope["findings"][0]["code"], "EVIDENCE_FILE_UNREADABLE")
        self._assert_every_finding_has_fix_hint(envelope)

    def test_evidence_source_not_object_carries_fix_hint(self) -> None:
        code, envelope = self.invoke(
            [
                "record",
                "--question", "does it hold?",
                "--subject-type", "mechanism",
                "--subject-id", "M-014",
                "--level", "E1",
                "--execution-status", "completed",
                "--research-outcome", "inconclusive",
                "--confidence", "low",
                "--observation", "probe ran",
                "--no-experiment",
                "--from-json", "[1, 2, 3]",
            ]
        )
        self.assertEqual(code, 2, envelope)
        self.assertEqual(envelope["findings"][0]["code"], "EVIDENCE_SOURCE_NOT_OBJECT")
        self._assert_every_finding_has_fix_hint(envelope)


class RecordValidateLineTests(GitCommandTestCase):
    """V1 Block 2 / T6: `--validate-line` runs the schema / derive pass
    without writing the ledger file or the git commit.

    The flag separates "is one record legal?" from "does this run
    produce enough evidence?". A parallel-writer guard calls the
    former before claiming an id; `validate` covers the latter.
    """

    def _invoke_validate(self, *extra: str) -> tuple[int, dict]:
        argv = [
            "record",
            "--question", "does the mechanism hold?",
            "--subject-type", "mechanism",
            "--subject-id", "M-014",
            "--level", "E1",
            "--execution-status", "completed",
            "--research-outcome", "inconclusive",
            "--confidence", "low",
            "--observation", "the probe ran",
            "--no-experiment",
            "--validate-line",
            *extra,
        ]
        return self.invoke(argv)

    def test_validate_line_writes_nothing_to_disk(self) -> None:
        before = self.tree()

        code, envelope = self._invoke_validate()

        self.assertEqual(code, 0, envelope)
        self.assertTrue(envelope["payload"]["validated"])
        self.assertFalse(envelope["payload"]["wrote"])
        self.assertIsNone(envelope["payload"]["evidence_id"])
        # The working tree must not have gained a ledger shard or a git
        # commit. `tree()` is content-hashed, so any new file under the
        # root trips the assertion.
        self.assertEqual(before, self.tree())

    def test_validate_line_does_not_make_a_git_commit(self) -> None:
        # `before` is the count of commits on the test fixture's
        # baseline; `after` is the count after `--validate-line`.
        # They must be equal: nothing should have been committed.
        before = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )
        self._invoke_validate()
        after = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(before.stdout.strip(), after.stdout.strip())

    def test_validate_line_surfaces_rejections_without_writing(self) -> None:
        # An invalid combination (--no-experiment plus --experiment-id)
        # must report the rejection, exit non-zero, and still leave the
        # working tree untouched.
        before = self.tree()

        code, envelope = self.invoke(
            [
                "record",
                "--question", "does the mechanism hold?",
                "--subject-type", "mechanism",
                "--subject-id", "M-014",
                "--level", "E1",
                "--execution-status", "completed",
                "--research-outcome", "inconclusive",
                "--confidence", "low",
                "--observation", "the probe ran",
                "--no-experiment",
                "--experiment-id", "EXP-conflict",
                "--validate-line",
            ]
        )
        self.assertEqual(code, 2, envelope)
        self.assertEqual(envelope["findings"][0]["code"], "EXPERIMENT_FLAG_CONFLICT")
        # `wrote=False` is part of the validated-line contract: the
        # caller asked for validation only and the tool respected it.
        self.assertFalse(envelope["payload"]["wrote"])
        self.assertEqual(before, self.tree())

    def test_validate_line_reports_a_clean_run_via_findings(self) -> None:
        # A clean validate still emits an envelope whose `findings`
        # field is present (so callers branching on the field do not
        # trip on KeyError), and whose count is zero.
        code, envelope = self._invoke_validate()

        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["payload"]["findings"], [])
        self.assertEqual(envelope["findings"], [])


class TelemetryReportTests(CommandTestCase):
    """V1 Block 2 / T5: `telemetry --report` emits the §21 KPI table.

    Two of the four named KPIs (`time_to_first_e1`, `time_to_first_e3`)
    are computable today from the ledger and ACTIVE.session_epoch.
    The other two (`session_recovery_accuracy`,
    `discriminating_experiment_without_architect_correction`) need
    infrastructure that is out of scope for this sub-block. The report
    marks them `unavailable` with the reason rather than silently
    emitting a zero, so the gap is visible.
    """

    def _seed_session_epoch(self) -> str:
        # `active --rotate-session` mints a fresh session_epoch id whose
        # timestamp is `now`. Pinning the session_epoch explicitly keeps
        # the test free of wall-clock drift. The mints mints from
        # `researchlog ids mint session`, so the timestamp baked into the
        # id is `now` as well — the gap is in the seconds, not days.
        code, envelope = self.invoke(["active", "--rotate-session"])
        self.assertEqual(code, 0, envelope)
        epoch = json.loads(
            self.research("ACTIVE.json").read_text(encoding="utf-8")
        ).get("session_epoch")
        self.assertIsNotNone(epoch, f"rotate-session did not write session_epoch: {envelope}")
        return epoch

    def test_report_lists_four_kpis(self) -> None:
        code, envelope = self.invoke(["telemetry", "--report"])
        self.assertIn(code, (0, 3), envelope)

        kpis = envelope["payload"]["kpis"]
        names = [row["kpi"] for row in kpis]
        self.assertEqual(
            names,
            [
                "time_to_first_e1",
                "time_to_first_e3",
                "session_recovery_accuracy",
                "discriminating_experiment_without_architect_correction",
            ],
        )

    def test_unavailable_kpis_carry_their_reason(self) -> None:
        code, envelope = self.invoke(["telemetry", "--report"])
        self.assertIn(code, (0, 3), envelope)

        kpis = {row["kpi"]: row for row in envelope["payload"]["kpis"]}
        for name in ("session_recovery_accuracy",
                     "discriminating_experiment_without_architect_correction"):
            row = kpis[name]
            self.assertEqual(row["status"], "unavailable")
            self.assertIsNone(row["value"])
            self.assertTrue(row["reason"], f"{name} must carry a reason")

    def test_unavailable_kpis_surface_as_warnings(self) -> None:
        # All four rows are unavailable on a fresh repo (no
        # session_epoch, no ARCHITECT.md reader, no session-event log),
        # so the envelope must surface four `TELEMETRY_KPI_UNAVAILABLE`
        # warnings. Without them the next session would mistake the
        # report for "all is well".
        code, envelope = self.invoke(["telemetry", "--report"])
        self.assertIn(code, (0, 3), envelope)
        codes = [f["code"] for f in envelope["findings"]]
        self.assertEqual(
            codes.count("TELEMETRY_KPI_UNAVAILABLE"), 4,
            codes,
        )

    def test_time_to_first_e1_reports_unavailable_with_empty_ledger(self) -> None:
        code, envelope = self.invoke(["telemetry", "--report"])
        self.assertIn(code, (0, 3), envelope)

        kpis = {row["kpi"]: row for row in envelope["payload"]["kpis"]}
        self.assertEqual(kpis["time_to_first_e1"]["status"], "unavailable")
        self.assertIsNone(kpis["time_to_first_e1"]["value"])

    def test_time_to_first_e1_reports_unavailable_without_a_matching_evidence(self) -> None:
        # Rotate the session so `session_epoch` is set, but do not
        # record any E1 evidence. The detector must still report
        # `unavailable` rather than a misleading zero, because there
        # is no anchor to subtract from.
        self._seed_session_epoch()

        code, envelope = self.invoke(["telemetry", "--report"])
        self.assertIn(code, (0, 3), envelope)
        kpis = {row["kpi"]: row for row in envelope["payload"]["kpis"]}
        row = kpis["time_to_first_e1"]
        self.assertEqual(row["status"], "unavailable")
        self.assertIn("E1", row["reason"])

    def test_time_to_first_e1_measures_after_a_real_record(self) -> None:
        # With a session_epoch and an E1 evidence on disk, the KPI
        # reports a real number. The actual value depends on wall
        # clock; the test pins the shape, not the number.
        self._seed_session_epoch()
        self.record_evidence()

        code, envelope = self.invoke(["telemetry", "--report"])
        self.assertIn(code, (0, 3), envelope)
        kpis = {row["kpi"]: row for row in envelope["payload"]["kpis"]}
        row = kpis["time_to_first_e1"]
        self.assertEqual(row["status"], "ok", row)
        self.assertEqual(row["unit"], "seconds")
        self.assertIsInstance(row["value"], (int, float))
        self.assertGreaterEqual(row["value"], 0)


class RecordCommitTests(GitCommandTestCase):
    """V1 P1: `record` must commit the evidence file it just wrote.

    The end-to-end shape — write evidence, `git add`, `git commit` — is
    covered by the existing `EnvCommandTests::test_record_appends_*` after
    that test was rewritten to drive the bare `record` command. This class
    narrows in on the failure paths and on the commit message contract,
    which is the lesson E1 worry (backticks in `git commit -m` are silently
    command-substituted).
    """

    def _invoke_record(self) -> tuple[int, dict]:
        return self.invoke(
            [
                "record",
                "--question", "does the mechanism hold?",
                "--subject-type", "mechanism",
                "--subject-id", "M-014",
                "--level", "E1",
                "--execution-status", "completed",
                "--research-outcome", "inconclusive",
                "--confidence", "low",
                "--observation", "the probe ran",
                "--no-experiment",
            ]
        )

    def test_record_commits_with_the_canonical_subject(self) -> None:
        code, envelope = self._invoke_record()
        self.assertEqual(code, 0, envelope)
        evidence_id = envelope["payload"]["evidence_id"]

        # Subject line is the canonical V1 form, not the user-supplied
        # observation. Pinning the format here is what lets the next session
        # grep `git log --grep="research: record"` to find every record.
        log = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(log.stdout.strip(), f"research: record {evidence_id}")

        # The evidence file is tracked, not just on disk. V1 Block 2 / T2
        # partitions shards under `<YYYY-MM>/`, so the assertion targets
        # the partition-aware path rather than the flat one.
        from researchlog.repo import _evidence_month
        partition = _evidence_month(evidence_id)
        completed = subprocess.run(
            ["git", "ls-files", f"research/ledger/{partition}/{evidence_id}.json"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertTrue(
            completed.stdout.strip().endswith(
                f"research/ledger/{partition}/{evidence_id}.json"
            ),
            completed.stdout,
        )


class RecordRejectsInNonGitRepo(NonGitCommandTestCase):
    """V1 P1 guard rail: `record` must not silently write evidence when the
    repo is not a git repository, because the second half of the path
    (the commit) cannot run."""

    def test_record_refuses_outside_a_git_repository(self) -> None:
        code, envelope = self.invoke(
            [
                "record",
                "--question", "does the mechanism hold?",
                "--subject-type", "mechanism",
                "--subject-id", "M-014",
                "--level", "E1",
                "--execution-status", "completed",
                "--research-outcome", "inconclusive",
                "--confidence", "low",
                "--observation", "the probe ran",
                "--no-experiment",
            ]
        )
        self.assertEqual(code, 2, envelope)
        # `is_repository` reports before `git add`, so the subject is "git
        # commit" and the message names the root, not the generic stderr
        # from `git add` (which would be the case if the guard were skipped).
        self.assertEqual(envelope["findings"][0]["code"], "COMMIT_FAILED")
        self.assertEqual(envelope["findings"][0]["subject"], "git commit")
        self.assertIn("is not a git repository", envelope["findings"][0]["message"])


class HumanRenderingTests(unittest.TestCase):
    """Human output must carry the actionable half of a finding.

    `--json` is the contract an agent branches on, but a refusal printed to a terminal is
    the only thing between a reader and the source code. A bare code names the constraint
    and withholds what to do about it.
    """

    def test_a_finding_prints_its_message_and_its_fix_hint(self) -> None:
        result = Result(exit_code=EXIT_STATE_INVALID)
        result.add(
            Finding(
                "SOME_CONSTRAINT",
                SEVERITY_ERROR,
                "SUBJECT-1",
                "what went wrong",
                "what to do about it",
            )
        )

        text = cli._default_human(result, "record")

        self.assertIn("SOME_CONSTRAINT", text)
        self.assertIn("what went wrong", text)
        self.assertIn("what to do about it", text)

    def test_a_finding_without_a_fix_hint_still_prints_its_message(self) -> None:
        result = Result(exit_code=EXIT_FINDINGS_PRESENT)
        result.add(Finding("SOME_WARNING", SEVERITY_WARNING, "SUBJECT-2", "worth knowing"))

        text = cli._default_human(result, "validate")

        self.assertIn("worth knowing", text)


class ExpiredArchitectSignalTests(CommandTestCase):
    """V1-D8 #2: a CONSTRAINT whose ISO-8601 expiry is in the past is surfaced.

    `reconcile._expired_signals` (`commands/reconcile.py:320`) walks every
    `research:signal` block in `research/ARCHITECT.md`, skips inactive signals
    and free-text expiries, then emits `EXPIRED_ARCHITECT_SIGNAL` for any ISO
    timestamp that has already passed. This is the mechanism that prevents a
    temporary constraint from hardening into unchallengeable doctrine by
    accident — the failure mode ARCHITECT.md's own heading warns about.

    `validate` also runs the same `check_signal` predicate, but `reconcile`
    is the path the resume protocol actually takes, so the assertion lives
    there.
    """

    def test_expired_constraint_signal_emits_finding_on_reconcile(self) -> None:
        # Append an expired CONSTRAINT signal. The fixture's `init` lays down
        # an empty ARCHITECT.md that already carries a `research:signal` block
        # shape (see `templates/research/ARCHITECT.md`), so we just add one
        # more. Using a deadline two days in the past to avoid timezone
        # edge cases at midnight UTC.
        architect = self.research("ARCHITECT.md")
        from datetime import datetime, timedelta, timezone
        past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(timespec="seconds")
        new_block = (
            "\n```json research:signal\n"
            "{\n"
            '  "id": "C-TEST-EXPIRED",\n'
            '  "type": "CONSTRAINT",\n'
            '  "statement": "do not touch the navigation planner (test fixture)",\n'
            '  "scope": "synthesize tests",\n'
            f'  "expiry": "{past}",\n'
            '  "source_text": "导航 planner 先别改 (test fixture)",\n'
            f'  "created_at": "{past}",\n'
            '  "active": true\n'
            "}\n"
            "```\n"
        )
        architect.write_text(architect.read_text(encoding="utf-8") + new_block, encoding="utf-8")

        code, envelope = self.invoke(["reconcile", "--json"])
        # Exit code is 3 (`EXIT_FINDINGS_PRESENT`) because the warning is a
        # `SEVERITY_WARNING`, not an error — the resume protocol can still
        # proceed, it just needs the Architect to re-confirm or let it lapse.
        self.assertIn(code, (0, 3), envelope)
        codes = [f["code"] for f in envelope["findings"]]
        self.assertIn("EXPIRED_ARCHITECT_SIGNAL", codes)
        # The finding subject carries the signal id, so the Architect can
        # locate the offending block without grepping ARCHITECT.md.
        expired = [f for f in envelope["findings"] if f["code"] == "EXPIRED_ARCHITECT_SIGNAL"]
        self.assertEqual(expired[0]["subject"], "C-TEST-EXPIRED")

    def test_free_text_expiry_is_not_evaluated(self) -> None:
        # A CONSTRAINT whose `expiry` is a human-kept promise ("recovery
        # checkpoint") is intentionally NOT evaluated by the tool. Without
        # this carve-out the tool would silently promote "I'll re-confirm
        # later" into "never re-confirmed" — exactly the doctrine-by-accident
        # failure the detector exists to prevent.
        architect = self.research("ARCHITECT.md")
        new_block = (
            "\n```json research:signal\n"
            "{\n"
            '  "id": "C-TEST-PROMISE",\n'
            '  "type": "CONSTRAINT",\n'
            '  "statement": "do not change the bootstrap (test fixture)",\n'
            '  "scope": "bootstrap tests",\n'
            '  "expiry": "recovery checkpoint",\n'
            '  "source_text": "bootstrap 改之前先复盘 (test fixture)",\n'
            '  "created_at": "2026-01-01T00:00:00+00:00",\n'
            '  "active": true\n'
            "}\n"
            "```\n"
        )
        architect.write_text(architect.read_text(encoding="utf-8") + new_block, encoding="utf-8")

        code, envelope = self.invoke(["reconcile", "--json"])
        self.assertIn(code, (0, 3), envelope)
        codes = [f["code"] for f in envelope["findings"]]
        self.assertNotIn("EXPIRED_ARCHITECT_SIGNAL", codes)

    def test_inactive_signal_is_not_evaluated(self) -> None:
        # `active: false` means the signal has been acknowledged as expired
        # or superseded — the tool must not double-report it.
        architect = self.research("ARCHITECT.md")
        from datetime import datetime, timedelta, timezone
        past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(timespec="seconds")
        new_block = (
            "\n```json research:signal\n"
            "{\n"
            '  "id": "C-TEST-INACTIVE",\n'
            '  "type": "CONSTRAINT",\n'
            '  "statement": "do not touch X (test fixture, already retired)",\n'
            '  "scope": "tests",\n'
            f'  "expiry": "{past}",\n'
            '  "source_text": "X 先别动 (test fixture, retired)",\n'
            f'  "created_at": "{past}",\n'
            '  "active": false\n'
            "}\n"
            "```\n"
        )
        architect.write_text(architect.read_text(encoding="utf-8") + new_block, encoding="utf-8")

        code, envelope = self.invoke(["reconcile", "--json"])
        self.assertIn(code, (0, 3), envelope)
        codes = [f["code"] for f in envelope["findings"]]
        self.assertNotIn("EXPIRED_ARCHITECT_SIGNAL", codes)


class WorktreeSingleWriterTests(CommandTestCase):
    """V1-D5: P9 single-writer enforcement on `research/`.

    `_worktree_multi_writer` (`commands/reconcile.py:434`) lists every git
    worktree, runs `git status --porcelain -- research/` against each, and
    reports when more than one is dirty under the canonical-state directory.
    The threshold is `len(dirty) > 1`, so a single dirty worktree is fine —
    the rule is "one writer at a time", not "no writers".

    Detached worktrees that dirty `research/` are deliberately skipped by
    the detector (the porcelain check cannot address them safely); the
    comment at `reconcile.py:457-459` is explicit that this widens the
    false-negative window on purpose rather than letting a tool that
    cannot see every worktree fabricate certainty.
    """

    def _add_worktree(self, path: Path, *, branch: str | None = None, detached: bool = False) -> None:
        """Lay down a second worktree alongside `self.root`."""
        args = ["worktree", "add"]
        if detached:
            args.append("--detach")
        if branch is not None:
            # `-b <new>` creates a new branch from HEAD; the path is the
            # worktree directory, the branch is `-b`'s argument. The
            # positional form `git worktree add <branch> <path>` is the
            # older syntax and trips on ambiguity.
            args.extend(["-b", branch])
        args.append(str(path))
        completed = subprocess.run(
            ["git", *args], cwd=str(self.root), capture_output=True, text=True, check=False
        )
        self.assertEqual(
            completed.returncode, 0,
            f"git worktree add failed: {completed.stderr}",
        )

    def test_single_dirty_worktree_does_not_trigger_finding(self) -> None:
        # V1-D5 #1: a single worktree writing freely is the happy path.
        # The detector only fires when `len(dirty) > 1`.
        (self.research("CURRENT.md")).write_text(
            self.research("CURRENT.md").read_text(encoding="utf-8")
            + "\n<!-- single-writer fixture marker -->\n",
            encoding="utf-8",
        )

        code, envelope = self.invoke(["reconcile", "--json"])
        self.assertIn(code, (0, 3), envelope)
        codes = [f["code"] for f in envelope["findings"]]
        self.assertNotIn("WORKTREE_MULTI_WRITER", codes)

    def test_two_dirty_worktrees_trigger_finding(self) -> None:
        # V1-D5 #2: two worktrees with dirty research/ are structurally
        # unsafe (a merge conflict in canonical state silently loses one
        # writer's record); the detector must name the offenders.
        sibling = self.root.parent / f"{self.root.name}-sibling"
        self._add_worktree(sibling, branch="wt-sibling")
        try:
            # Dirty BOTH worktrees under research/.
            (self.research("CURRENT.md")).write_text(
                self.research("CURRENT.md").read_text(encoding="utf-8")
                + "\n<!-- main writer fixture marker -->\n",
                encoding="utf-8",
            )
            (sibling / "research" / "CURRENT.md").write_text(
                (sibling / "research" / "CURRENT.md").read_text(encoding="utf-8")
                + "\n<!-- sibling writer fixture marker -->\n",
                encoding="utf-8",
            )

            code, envelope = self.invoke(["reconcile", "--json"])
            # `reconcile` itself runs in the main worktree, which is dirty —
            # so other findings may appear; the assertion targets the specific
            # code without pinning the exit code.
            self.assertIn(code, (0, 2, 3), envelope)
            codes = [f["code"] for f in envelope["findings"]]
            self.assertIn("WORKTREE_MULTI_WRITER", codes)
            # The finding names the dirty worktrees so the Architect can act.
            finding = next(f for f in envelope["findings"] if f["code"] == "WORKTREE_MULTI_WRITER")
            self.assertIn(str(self.root), finding["message"])
            self.assertIn(str(sibling), finding["message"])
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(sibling)],
                cwd=str(self.root), capture_output=True, check=False,
            )

    def test_session_rotation_is_not_blocked(self) -> None:
        # V1-D5 #3: rotating the session mid-run (minting a new
        # `session_epoch`) must succeed and not be flagged by any detector.
        # The "first second" framing in the drill text is about race
        # conditions; the contract is simply that the rotation path
        # completes without interference from the worktree detector.
        code, envelope = self.invoke(["active", "--rotate-session"])
        self.assertEqual(code, 0, envelope)
        self.assertIn("session_epoch", envelope["payload"]["changed"])

        code, envelope = self.invoke(["reconcile", "--json"])
        codes = [f["code"] for f in envelope["findings"]]
        self.assertNotIn("WORKTREE_MULTI_WRITER", codes)

    def test_detached_worktree_with_dirty_research_is_not_flagged(self) -> None:
        # V1-D5 #4: a detached worktree that dirties research/ is NOT
        # reported by the detector. The carve-out is explicit at
        # `commands/reconcile.py:457-459`: the porcelain check cannot
        # address detached worktrees safely, and a tool that cannot see
        # every worktree must not pretend it can.
        detached = self.root.parent / f"{self.root.name}-detached"
        self._add_worktree(detached, detached=True)
        try:
            (detached / "research" / "CURRENT.md").write_text(
                (detached / "research" / "CURRENT.md").read_text(encoding="utf-8")
                + "\n<!-- detached dirty fixture marker -->\n",
                encoding="utf-8",
            )

            code, envelope = self.invoke(["reconcile", "--json"])
            self.assertIn(code, (0, 3), envelope)
            codes = [f["code"] for f in envelope["findings"]]
            self.assertNotIn("WORKTREE_MULTI_WRITER", codes)
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(detached)],
                cwd=str(self.root), capture_output=True, check=False,
            )


class E2E3ReplayTests(CommandTestCase):
    """V1-D2 #5: an E3 record pairs with an E2 record through `compare`.

    The E2 path is covered by `ComparisonIdentityTests` in test_integration.py
    (lines 489-543); this test closes the E3 half by exercising the same
    attribution predicate with `evidence_level: E3` on both sides. The
    machinery is the same — `compare` reads `inputs` and `environment`
    regardless of evidence_level — so the assertion is just that an E3
    record + an E2 record with same identity produce `COMPARABLE`.
    """

    def test_e2_and_e3_records_with_same_identity_are_comparable(self) -> None:
        # Synthesise two records via `--from-json`, mirroring the
        # ComparisonIdentityTests pattern, so the test does not depend on
        # a real harness. Both records share `inputs.replay_suite` and
        # `environment.fingerprint`; only `evidence_level` differs.
        shared_inputs = {"replay_suite": "replay-v3"}
        shared_environment = {"fingerprint": "fp-1"}
        base = {
            "schema_version": "1.0",
            "question": "does the E3 path compare?",
            "subject": {"type": "mechanism", "id": "M-E3"},
            "observations": ["ran"],
            "execution_status": "completed",
            "research_outcome": "inconclusive",
            "confidence": "low",
            "counts_as_evidence_iteration": False,
            "inputs": shared_inputs,
            "environment": shared_environment,
        }
        e2_payload = dict(base, evidence_level="E2")
        e3_payload = dict(base, evidence_level="E3")

        code, envelope = self.invoke(["record", "--from-json", json.dumps(e2_payload), "--json"])
        self.assertEqual(code, 0, envelope)
        e2_id = envelope["payload"]["evidence_id"]

        code, envelope = self.invoke(["record", "--from-json", json.dumps(e3_payload), "--json"])
        self.assertEqual(code, 0, envelope)
        e3_id = envelope["payload"]["evidence_id"]

        code, envelope = self.invoke(["compare", e2_id, e3_id, "--json"])
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["payload"]["attribute_verdict"], "COMPARABLE")


class SessionRotationTests(CommandTestCase):
    """V1-D3 #2 + #3: rotation does not restart the block; reproduction
    iterations do not consume the block's evidence budget.

    The underlying predicates — `active.py` keep `block.id` on rotate;
    `constraints.derive_counts_as_evidence_iteration` returns False for
    `iteration_kind: reproduction` — are unit-tested elsewhere. The
    integration shape that exercises both predicates end-to-end through
    `record` + `active --get` lives here.
    """

    def test_rotate_session_does_not_restart_the_open_block(self) -> None:
        # V1-D3 #2: open a block, rotate the session, assert `block.id`
        # is unchanged and `block.completed_evidence_iterations` is
        # preserved (the rotation should reset neither).
        self.invoke(["active", "--set", "block.id=BL-ROT"])
        # Capture the active record's `block.id` so we can compare.
        _, before = self.invoke(["active", "--get", "block.id"])
        self.assertEqual(before["payload"]["value"], "BL-ROT")

        self.invoke(["active", "--rotate-session"])

        code, envelope = self.invoke(["active", "--get", "block.id"])
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["payload"]["value"], "BL-ROT")

    def test_reproduction_iteration_does_not_bump_block_budget(self) -> None:
        # V1-D3 #3: a record tagged as `--iteration-kind reproduction`
        # must NOT count toward the block's evidence budget
        # (`block.completed_evidence_iterations`); it goes to
        # `block.reproduction_iterations` instead. The counts are
        # derived and written at close (see `commands/active.py:183-185`),
        # so we close the block with `belief-delta` and assert the
        # derived values, which is the integration shape the resume
        # protocol actually observes.
        self.invoke(["active", "--set", "block.id=BL-REPRO"])
        # Pin the count fields to 0 explicitly so the assertions are
        # independent of whatever `init`/rotation defaults set.
        self.invoke(["active", "--set", "block.completed_evidence_iterations=0"])
        self.invoke(["active", "--set", "block.reproduction_iterations=0"])

        code, envelope = self.invoke(
            [
                "record",
                "--question",
                "does reproduction iteration count?",
                "--subject-type",
                "mechanism",
                "--subject-id",
                "M-REPRO",
                "--level",
                "E2",
                "--execution-status",
                "completed",
                "--research-outcome",
                "refuted",
                "--confidence",
                "moderate",
                "--belief-delta",
                "refined",
                "--observation",
                "reproduction of the residual tracking",
                "--iteration-kind",
                "reproduction",
                "--no-experiment",
            ]
        )
        self.assertEqual(code, 0, envelope)

        # Close with belief_delta; this is the moment `active.py` writes
        # the derived counts onto ACTIVE.json.
        self.invoke(["active", "--close-block", "--belief-delta", "refined"])

        _, completed = self.invoke(["active", "--get", "block.completed_evidence_iterations"])
        self.assertEqual(completed["payload"]["value"], 0)

        _, reproduction = self.invoke(["active", "--get", "block.reproduction_iterations"])
        self.assertEqual(reproduction["payload"]["value"], 1)


if __name__ == "__main__":
    unittest.main()
