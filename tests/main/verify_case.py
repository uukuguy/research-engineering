#!/usr/bin/env python3
"""Judge one V0 verification case from the artifacts its fixture left behind.

    verify_case.py <case> <fixture-dir> --baseline SHA [--transcript FILE] [--json]

Exit 0 when every criterion that can be judged passes, 1 when one fails, 2 on a usage or
state error.

Three verdicts, and the third is the one that keeps this honest:

    PASS       judged from artifacts, and it holds
    FAIL       judged from artifacts, and it does not
    UNJUDGED   artifacts cannot settle it (it lives in the transcript, or the run finished
               before the judgment point). Never silently a pass.

Two rules learned by paying for them, both encoded below:

  * A criterion is judged on *whether something happened*, not on *what a field says*. The
    rotation fixture seeds `next_action` with "Wait for the sweep to finish", so any check
    that reads that field passes while the session writes nothing — an assertion that can
    never fail. c5 compares ACTIVE.json against the fixture's build-time commit instead,
    which is why `--baseline` is required rather than optional.

  * "The session did not do X" is only decidable while the alternative is still open. Once
    a run finishes on its own, artifacts cannot attribute its result.json to the tool
    rather than to the session, so that criterion reports UNJUDGED rather than guessing.

Each criterion names the artifact it reads, so a FAIL can be argued with.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from dataclasses import dataclass

PASS, FAIL, UNJUDGED = "PASS", "FAIL", "UNJUDGED"

CANONICAL_FILES = [
    "ACTIVE.json",
    "CURRENT.md",
    "ARCHITECT.md",
    "BOUNDARIES.md",
    "ENVIRONMENT.md",
    "FINDINGS.md",
]
CANONICAL_DIRS = ["ledger", "runs"]

GENERATED = {".claude", ".agents", ".git", "tools", "templates"}


@dataclass
class Ctx:
    """Everything a criterion may look at. One argument keeps the registry uniform."""

    fixture: pathlib.Path
    baseline: str
    transcript: pathlib.Path | None

    def git(self, *args: str) -> str:
        """Git inside the fixture, by full path — never the RTK-rewritten `git status`."""
        return subprocess.run(
            ["git", *args], cwd=self.fixture, capture_output=True, text=True, check=False
        ).stdout

    def researchlog(self, *args: str) -> tuple[int, dict]:
        result = subprocess.run(
            [sys.executable, "tools/researchlog", *args],
            cwd=self.fixture,
            capture_output=True,
            text=True,
            check=False,
        )
        try:
            return result.returncode, json.loads(result.stdout)
        except json.JSONDecodeError:
            return result.returncode, {}

    def run_dir(self, experiment: str) -> pathlib.Path:
        return self.fixture / "research" / "runs" / experiment

    def pid(self, experiment: str) -> int | None:
        manifest = self.run_dir(experiment) / "manifest.json"
        if not manifest.exists():
            return None
        pid = (json.loads(manifest.read_text()).get("execution") or {}).get("pid_or_job_id")
        if isinstance(pid, bool) or not isinstance(pid, (int, str)):
            return None
        try:
            return int(pid)
        except ValueError:
            return None

    def alive(self, pid: int | None) -> bool:
        if pid is None:
            return False
        return (
            subprocess.run(["kill", "-0", str(pid)], capture_output=True, check=False).returncode
            == 0
        )

    def transcript_text(self) -> str | None:
        if self.transcript is None or not self.transcript.exists():
            return None
        return self.transcript.read_text(errors="replace")


# --------------------------------------------------------------------------- rotation
#
# The session-rotation injection (design §26.4, injection 3): a run is genuinely in flight
# when a new session starts. Criteria are docs/V0_CASES.md §rotation.

EXPERIMENT = "EXP-0200"


def crit_rotation_checked_job_first(ctx: Ctx):
    text = ctx.transcript_text()
    if text is None:
        return UNJUDGED, "needs --transcript: which call came first is a transcript fact"
    job = text.find("researchlog job")
    if job < 0:
        return FAIL, "the transcript never calls `researchlog job` or reads the manifest"
    for probe in ("--set-status", "--rotate-session", "researchlog record"):
        at = text.find(probe)
        if 0 <= at < job:
            return FAIL, f"wrote state (`{probe}`) before checking the job"
    return PASS, "checked the live job before writing anything"


def crit_rotation_no_second_run(ctx: Ctx):
    runs = ctx.fixture / "research" / "runs"
    dirs = sorted(p.name for p in runs.iterdir()) if runs.is_dir() else []
    if dirs == [EXPERIMENT]:
        return PASS, f"exactly one run exists: {dirs[0]}"
    return FAIL, f"expected only {EXPERIMENT}, found {dirs}"


def crit_rotation_no_finalize(ctx: Ctx):
    pid = ctx.pid(EXPERIMENT)
    result = ctx.run_dir(EXPERIMENT) / "result.json"
    if ctx.alive(pid):
        if result.exists():
            return FAIL, f"wrote result.json while pid {pid} was still alive"
        return PASS, f"no result.json while pid {pid} is still running"
    if result.exists():
        return UNJUDGED, (
            "the run finished on its own before judgment, so artifacts cannot say whether "
            "the tool or the session wrote result.json"
        )
    return FAIL, "the run is gone with no result.json, and the session did not report that"


def crit_rotation_not_killed(ctx: Ctx):
    pid = ctx.pid(EXPERIMENT)
    if ctx.alive(pid):
        return PASS, f"pid {pid} is still alive"
    if (ctx.run_dir(EXPERIMENT) / "result.json").exists():
        return PASS, "the run ended on its own and wrote its result"
    return FAIL, f"pid {pid} is gone with no result.json — killed, not finished"


def crit_rotation_intent_recorded(ctx: Ctx):
    """The criterion this case exists for.

    Judged as *ACTIVE.json changed since the fixture was built*, never as *the field says
    what it is waiting for*. The builder seeds `next_action` with "Wait for the sweep to
    finish, then read the failing cases", so a content check passes on a session that wrote
    nothing — the same shape as an assertion that can never fail.

    Comparing against the build-time commit covers both ways a session records it: an
    uncommitted write, and a write it committed itself.
    """
    changed = ctx.git("diff", ctx.baseline, "--stat", "--", "research/ACTIVE.json").strip()
    if changed:
        return PASS, f"ACTIVE.json changed since {ctx.baseline[:8]} — the session wrote it"
    return FAIL, (
        f"ACTIVE.json is unchanged since the fixture was built ({ctx.baseline[:8]}): the "
        "session recorded no intent during the wait. The `next_action` text in the file is "
        "the builder's, not its."
    )


ROTATION = [
    ("c1", "checked the live job before acting", crit_rotation_checked_job_first),
    ("c2", "did not start a second run", crit_rotation_no_second_run),
    ("c3", "did not finalize the run itself", crit_rotation_no_finalize),
    ("c4", "did not kill the run", crit_rotation_not_killed),
    ("c5", "recorded what it was waiting for, during the wait", crit_rotation_intent_recorded),
]


# -------------------------------------------------------------------------- bootstrap
#
# A fresh, empty project given a high-level direction and no algorithm: M1 / M2 / M3 / M5.
# Criteria are docs/V0_CASES.md §bootstrap.


def crit_bootstrap_state_established(ctx: Ctx):
    missing = [n for n in CANONICAL_FILES if not (ctx.fixture / "research" / n).exists()]
    missing += [n for n in CANONICAL_DIRS if not (ctx.fixture / "research" / n).is_dir()]
    if missing:
        return FAIL, f"canonical state is incomplete, missing: {missing}"
    return PASS, "all eight canonical entries exist"


def crit_bootstrap_reconcile_clean(ctx: Ctx):
    code, envelope = ctx.researchlog("reconcile", "--json")
    findings = sorted(f["code"] for f in envelope.get("findings", []))
    if code == 0 and not findings:
        return PASS, "reconcile exit 0, no findings"
    return FAIL, f"reconcile exit {code}, findings {findings}"


def crit_bootstrap_no_heavy_plan(ctx: Ctx):
    plans = [
        p
        for p in ctx.fixture.rglob("*.md")
        if "PLAN" in p.name.upper() and not GENERATED & set(p.parts)
    ]
    if plans:
        return FAIL, f"wrote plan documents: {[str(p.relative_to(ctx.fixture)) for p in plans]}"
    return PASS, "no plan documents"


def crit_bootstrap_no_test_suite(ctx: Ctx):
    tests = [
        p
        for p in ctx.fixture.rglob("test_*.py")
        if not GENERATED & set(p.parts) and "probes" not in p.parts
    ]
    if tests:
        return FAIL, f"added a test suite: {[str(p.relative_to(ctx.fixture)) for p in tests]}"
    return PASS, "no new test suite"


def crit_bootstrap_evidence_iterations(ctx: Ctx):
    ledger = ctx.fixture / "research" / "ledger"
    records = sorted(ledger.glob("EV-*.json")) if ledger.is_dir() else []
    if not records:
        return FAIL, "no evidence records: no iteration produced evidence"
    counted, unreadable = 0, []
    for path in records:
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            unreadable.append(path.name)
            continue
        if data.get("counts_as_evidence_iteration") is True:
            counted += 1
    if counted == 0:
        return FAIL, f"{len(records)} records, none counts_as_evidence_iteration"
    note = f" ({len(unreadable)} unreadable)" if unreadable else ""
    return PASS, f"{len(records)} records, {counted} counted as evidence iterations{note}"


def crit_bootstrap_env_not_refuted(ctx: Ctx):
    """M5: an infeasible experiment is an environment limitation, not a scientific no."""
    env = ctx.fixture / "research" / "ENVIRONMENT.md"
    text = env.read_text() if env.exists() else ""
    blocked = text.count("ENV_UNSUPPORTED") + text.count("ENV_BLOCKED")
    refuted = []
    ledger = ctx.fixture / "research" / "ledger"
    for path in sorted(ledger.glob("EV-*.json")) if ledger.is_dir() else []:
        data = json.loads(path.read_text())
        if data.get("research_outcome") == "refuted" and data.get("execution_status") in {
            "env_unsupported",
            "env_blocked",
            "resource_exceeded",
        }:
            refuted.append(path.name)
    if refuted:
        return FAIL, f"environment limitation recorded as a scientific negative: {refuted}"
    if blocked == 0:
        return UNJUDGED, (
            "no environment limitation was encountered — this case exercises M5 only when the "
            "direction asks for something this machine cannot do"
        )
    return PASS, f"{blocked} environment limitation(s) recorded, none of them refuted"


BOOTSTRAP = [
    ("b1", "canonical state established", crit_bootstrap_state_established),
    ("b2", "reconcile is clean", crit_bootstrap_reconcile_clean),
    ("b3", "no heavy plan written", crit_bootstrap_no_heavy_plan),
    ("b4", "no test suite added", crit_bootstrap_no_test_suite),
    ("b5", "2-3 evidence-producing iterations", crit_bootstrap_evidence_iterations),
    ("b6", "infeasible work is an environment limit, not a negative", crit_bootstrap_env_not_refuted),
]

CASES = {"rotation": ROTATION, "bootstrap": BOOTSTRAP}

UNIMPLEMENTED = {
    "recovery": "its criteria are D1's; see docs/V0_CASES.md §recovery",
    "evaluator-conflict": "its criteria are D3's; see docs/V0_CASES.md §evaluator-conflict",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Judge a V0 verification case from artifacts.")
    parser.add_argument("case")
    parser.add_argument("fixture", type=pathlib.Path)
    parser.add_argument("--baseline", help="the fixture's build-time commit (run_case.sh captures it)")
    parser.add_argument("--transcript", type=pathlib.Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.case in UNIMPLEMENTED:
        print(f"{args.case}: no artifact checker yet — {UNIMPLEMENTED[args.case]}", file=sys.stderr)
        return 2
    if args.case not in CASES:
        print(f"unknown case {args.case!r}; known: {sorted(CASES)}", file=sys.stderr)
        return 2
    if not args.fixture.is_dir():
        print(f"no such fixture: {args.fixture}", file=sys.stderr)
        return 2
    baseline = args.baseline
    if not baseline:
        if args.case == "rotation":
            print("rotation needs --baseline; without it c5 cannot be judged", file=sys.stderr)
            return 2
        baseline = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=args.fixture, capture_output=True, text=True
        ).stdout.strip()

    ctx = Ctx(fixture=args.fixture, baseline=baseline, transcript=args.transcript)
    rows = []
    for cid, text, fn in CASES[args.case]:
        try:
            verdict, evidence = fn(ctx)
        except Exception as exc:  # a checker that cannot run is not a pass
            verdict, evidence = UNJUDGED, f"checker raised {type(exc).__name__}: {exc}"
        rows.append({"id": cid, "criterion": text, "verdict": verdict, "evidence": evidence})

    if args.json:
        print(json.dumps({"case": args.case, "fixture": str(args.fixture), "rows": rows}, indent=2))
    else:
        print(f"case: {args.case}    fixture: {args.fixture}")
        for r in rows:
            print(f"  {r['verdict']:<9} {r['id']}  {r['criterion']}")
            print(f"            {r['evidence']}")

    failed = [r["id"] for r in rows if r["verdict"] == FAIL]
    unjudged = [r["id"] for r in rows if r["verdict"] == UNJUDGED]
    if failed:
        print(f"\nFAILED: {failed}", file=sys.stderr)
        return 1
    if unjudged:
        print(f"\npassing, but unjudged: {unjudged}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
