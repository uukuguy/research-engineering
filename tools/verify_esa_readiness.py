#!/usr/bin/env python3
"""Exercise RE against real, read-only ESA data in an isolated validation repo.

This does not resume or modify esa-study. Each CLI call is a new process. The
retained validation repo contains exact probe code, manifests, raw stdout,
immutable evidence and a recovery pointer. No model/GPU or paid service is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PROTOCOL = Path(__file__).resolve().parents[1]
ENTRY = PROTOCOL / "tools/re"
PROBE = PROTOCOL / "tools/probes/esa_package_audit.py"


def runtime_digest() -> str:
    digest = hashlib.sha256()
    files = [ENTRY, *sorted((PROTOCOL / "tools/researchlog").rglob("*.py")),
             *sorted((PROTOCOL / "tools/researchlog/schemas").glob("*.json"))]
    for path in files:
        if "tests" not in path.parts:
            digest.update(str(path.relative_to(PROTOCOL)).encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = args.data_root.resolve(strict=True)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    project = output / "project"
    project.mkdir()
    transcript: list[dict] = []
    report: dict = {
        "scope": "isolated RE CLI integration with real ESA files; not live esa-study recovery",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "project": str(project), "source_data": str(data),
        "host": {"system": platform.system(), "machine": platform.machine()},
        "re_runtime_sha256": runtime_digest(),
        "re_git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROTOCOL,
                                      capture_output=True, text=True, check=True).stdout.strip(),
        "runs": [], "passed": False,
    }

    def git(*argv: str) -> str:
        return subprocess.run(["git", *argv], cwd=project, check=True,
                              capture_output=True, text=True).stdout.strip()

    def cli(verb: str, *argv: str, allowed: tuple[int, ...] = (0,)) -> dict:
        command = [sys.executable, str(ENTRY), verb, "--json", *argv]
        result = subprocess.run(command, cwd=project, capture_output=True, text=True, timeout=45)
        try:
            envelope = json.loads(result.stdout)
        except ValueError as exc:
            transcript.append({"argv": command, "exit_code": result.returncode,
                               "stdout": result.stdout, "stderr": result.stderr})
            raise RuntimeError(f"{verb} returned no JSON: {result.stderr}") from exc
        transcript.append({"argv": command, "exit_code": result.returncode, "result": envelope})
        if result.returncode not in allowed:
            raise RuntimeError(f"{verb} failed: {envelope}")
        return envelope["payload"]

    def commit(message: str) -> None:
        git("add", "--", ".research", "probe.py", ".gitignore")
        git("commit", "-qm", message)

    def run(label: str, *, action_dim: int = 10, reproduction: bool = False) -> tuple[str, dict]:
        exp = f"EXP-ESA-{label}"
        cli("active", "--set-status", "running", "--set", f'experiment_id="{exp}"',
            "--set", 'execution.status="running"',
            "--set", f'execution.run_manifest=".research/runs/{exp}/manifest.json"',
            "--set-next-action", "Inspect the audit stdout before writing scientific interpretation.")
        result = cli(
            "run", "--experiment-id", exp, "--question", "Is the released ESA package internally consistent?",
            "--subject-type", "evaluation_surface", "--subject-id", "esa-package-contracts",
            "--input", f"dataset=sha256:{report['metadata_manifest_sha256']}",
            "--input", f"re_runtime=sha256:{report['re_runtime_sha256']}",
            "--input", f"expected_action_dim={action_dim}", "--timeout", "30", "--",
            sys.executable, "probe.py", "--data-root", str(data), "--expected-action-dim", str(action_dim),
        )
        raw = project / ".research/runs" / exp / "stdout.log"
        observation = json.loads(raw.read_text(encoding="utf-8"))
        if "execution_error" in observation:
            raise RuntimeError(observation["execution_error"])
        if result["child_exit_code"] != (0 if observation["passed"] else 1):
            raise RuntimeError("child exit status disagrees with the captured audit")
        cli("active", "--set-status", "reviewing", "--set", 'execution.status="completed"')
        measurements = observation["measurements"]
        summary = (f"Read {measurements['tasks']} real tasks; verified {measurements['metadata_files_verified']} "
                   f"release metadata files; reported {measurements['errors']} consistency errors. "
                   f"Expected action dimension {action_dim}. " + "; ".join(observation["errors"]))
        record_args = [
            "--from-orphan", exp, "--level", "E1", "--execution-status", "completed",
            "--research-outcome", "inconclusive", "--confidence", "high",
            "--belief-delta", "none" if reproduction else "refined",
            "--observation", summary, "--artifact", str(raw.relative_to(project)),
            "--artifact-role", "static-audit-report",
            "--limitation", "Static package audit only; no policy or simulator execution.",
        ]
        for key, value in measurements.items():
            record_args += ["--measurement", f"{key}={value}"]
        if reproduction:
            record_args += ["--iteration-kind", "reproduction"]
        record = cli("record", *record_args)
        report["runs"].append({"experiment_id": exp, "evidence_id": record["evidence_id"],
                               "child_exit_code": result["child_exit_code"], "audit": observation})
        commit(f"checkpoint: {label} audit recorded")
        cli("reconcile")
        return record["evidence_id"], observation

    try:
        git("init", "-q", "--initial-branch=main")
        git("config", "user.name", "RE validation")
        git("config", "user.email", "validation@example.invalid")
        git("config", "commit.gpgsign", "false")
        shutil.copyfile(PROBE, project / "probe.py")
        (project / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        report["metadata_manifest_sha256"] = hashlib.sha256(
            (data / "RELEASE_METADATA_SHA256SUMS").read_bytes()).hexdigest()
        report["probe_sha256"] = hashlib.sha256(PROBE.read_bytes()).hexdigest()
        cli("init")
        cli("current", "--set", 'objective="Verify static ESA package consistency and RE recovery."',
            "--set", 'next_empirical_action="Run the audit, negative control and cross-session reproduction."')
        cli("active", "--set-status", "planning_evidence", "--set", 'block.id="RB-ESA-VALIDATION"',
            "--set", 'block.objective="Exercise real data through RE CLI boundaries"',
            "--set", "block.max_evidence_iterations=3", "--set", "block.max_wall_clock_minutes=10",
            "--set", 'git.expected_touched_files=[".research/"]')
        cli("env", "rebaseline", "--reason", "Static local audit environment; no simulator claim.")
        commit("fixture: real-data audit code and RE state")
        report["initial_reconcile"] = cli("reconcile")
        first, first_audit = run("BASELINE")
        cli("active", "--rotate-session", "--set-next-action", "Reproduce baseline under the same pinned input.")
        report["resumed_reconcile"] = cli("reconcile")
        second, second_audit = run("REPLAY", reproduction=True)
        if first_audit != second_audit:
            raise RuntimeError("same-input replay changed the audit artifact")
        report["comparison"] = cli("compare", first, second)
        _, control = run("NEGATIVE-CONTROL", action_dim=11, reproduction=True)
        if control["measurements"]["errors"] != first_audit["measurements"]["errors"] + 24:
            raise RuntimeError("negative control did not reject the changed dimension in every task")
        cli("current", "--set", 'evidence_maturity.highest_stable_level="E1"',
            "--set", 'next_empirical_action="Resolve live esa-study recovery choice, then register actual findings there."')
        cli("active", "--close-block", "--belief-delta", "refined",
            "--set-next-action", "Keep this validation as bounded evidence; live esa-study remains unreconciled.")
        report["validation"] = cli("validate")
        # Missing E3/recovery KPIs are warnings, not a failed E1 audit.
        report["telemetry"] = cli("telemetry", "--report", allowed=(0, 3))
        report["active"] = cli("active", "--show")
        kpis = {row["kpi"]: row for row in report["telemetry"]["kpis"]}
        if [row["iterations"] for row in kpis["cumulative_evidence_iterations"]["per_session"]] != [1, 0]:
            raise RuntimeError("rotation reassigned an evidence iteration to the wrong session")
        timing = kpis["time_to_first_e1"]
        if timing["value"] < 0 or timing["evidence_id"] != second:
            raise RuntimeError("current-session time-to-first uses the wrong evidence")
        block = report["active"]["active"]["block"]
        if block["completed_evidence_iterations"] != 1 or block["reproduction_iterations"] != 2:
            raise RuntimeError("block closure mixed reproduction with evidence budget")
        commit("checkpoint: closed validation block and recovery context")
        report["final_reconcile"] = cli("reconcile")
        report["head"] = git("rev-parse", "HEAD")
        report["git_status"] = git("status", "--short")
        if runtime_digest() != report["re_runtime_sha256"]:
            raise RuntimeError("RE implementation changed during the validation run")
        report["passed"] = report["comparison"]["attribute_verdict"] == "COMPARABLE" and not report["git_status"]
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        (output / "cli-transcript.json").write_text(json.dumps(transcript, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"passed": report["passed"], "report": str(output / "report.json"),
                      "runs": len(report["runs"]), "error": report.get("error")}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
