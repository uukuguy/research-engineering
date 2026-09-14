#!/usr/bin/env bash
#
# Build a repository in the state the Session Recovery Benchmark (design §12.16) needs:
# a research session was killed mid-experiment, and a new session must recover the
# decision-relevant state from files alone.
#
# Why a script and not a paragraph of instructions: the state has to be exactly right —
# a stale-but-running manifest, a finished experiment whose result must not be re-derived,
# an environment limitation that must come back as a limitation rather than a failure, and
# a dirty diff whose intent is recoverable. Prose cannot be run, and so cannot be checked.
#
# Usage:  tests/main/build_recovery_drill.sh <target-dir>
#
# Exit 0 means the fixture was built AND `reconcile` reported exactly the expected picture.
# The protocol that consumes this fixture, and the pass/fail criteria, are in
# docs/V0_ACCEPTANCE_GUIDE.md.

set -euo pipefail

SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET="${1:-}"
if [[ -z "$TARGET" ]]; then
  echo "usage: $0 <target-dir>" >&2
  exit 64
fi

PYTHON="${PYTHON:-python3}"

rm -rf "$TARGET"
mkdir -p "$TARGET"
cd "$TARGET"

git init -q .
git config user.email drill@example.invalid
git config user.name "recovery drill"

# The deployment model is "copy the tool whole", plus the templates `init` reads, plus the
# two files a client reads to find its skills.
mkdir -p tools
cp -R "$SOURCE_ROOT/tools/researchlog" tools/
cp -R "$SOURCE_ROOT/templates" templates
cp "$SOURCE_ROOT/AGENTS.md" "$SOURCE_ROOT/CLAUDE.md" .
"$PYTHON" "$SOURCE_ROOT/tools/install_research_skills.py" --target "$TARGET" --quiet

# AGENTS.md declares the workflow-control block as mechanical, enforced in
# `.claude/settings.json` — "not merely discouraged here", and the deny list is the
# load-bearing part. Copying the contract without its enforcement would test a
# configuration the project does not use.
mkdir -p .claude
cp "$SOURCE_ROOT/.claude/settings.json" .claude/settings.json

mkdir -p probes
cat > probes/replay_probe.py <<'PROBE'
"""Offline replay: does the residual separate release timing from sensor noise?

Prints one line per case and writes nothing into the working tree. A probe that drops an
output file into the repository changes the code identity between runs, and then two runs
of the same code look like two different codes — an anomaly the next session has to explain
before it can trust anything else here.
"""

import argparse

# Two cases track release timing; three are ambiguous. The evidence record cites this
# breakdown, so the breakdown has to be something the artifact actually shows.
CASES = (
    ("case-01", 0.22, "release_timing"),
    ("case-02", 0.19, "release_timing"),
    ("case-03", 0.41, "ambiguous"),
    ("case-04", 0.44, "ambiguous"),
    ("case-05", 0.39, "ambiguous"),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--closed-loop", action="store_true")
    closed_loop = parser.parse_args().closed_loop
    arm = "closed-loop " if closed_loop else ""
    for name, residual, tracking in CASES:
        print(f"{name} {arm}residual {residual:.2f} tracking={tracking}")


if __name__ == "__main__":
    main()
PROBE

# The surrogate contract is part of the workspace, so it is committed before any run.
# Creating it later would move the code identity between two runs of the same code.
cat > probes/replay_surrogate.json <<'CONTRACT'
{
  "target_causal_claim": "the residual separation survives closed-loop closure",
  "required_causal_features": ["actuator dynamics in the loop", "release timing events"],
  "preserved_features": ["release timing events"],
  "missing_or_distorted_features": ["actuator dynamics in the loop"],
  "allowed_conclusions": ["the residual separation is visible in offline replay"],
  "forbidden_conclusions": ["the separation survives a real actuator"],
  "verdict": "VALID_SURROGATE"
}
CONTRACT

git add -A
git commit -qm "drill: workspace before the session that died"

researchlog() { "$PYTHON" tools/researchlog "$@"; }

researchlog init --quiet

# --- the experiment that finished: its result must not be re-derived ------------------
# The replay is E2 evidence against an E4 question, so it carries the surrogate contract
# committed with the workspace above. That is not fixture ceremony: it is the reason the
# evidence below is allowed to say anything at all, and the new session has to respect it.
researchlog run --experiment-id EXP-0141 --quiet -- "$PYTHON" probes/replay_probe.py >/dev/null
researchlog record \
  --experiment-id EXP-0141 \
  --question "Does the residual separate release timing from measurement noise?" \
  --subject-type harness --subject-id HRN-001 \
  --level E2 --target-level E4 --surrogate-contract probes/replay_surrogate.json \
  --execution-status completed --research-outcome inconclusive --confidence low \
  --hypothesis H-037 --belief-delta none \
  --observation "The residual tracked release timing on 2 of 5 cases; the other 3 were ambiguous." \
  --limitation "Offline replay only; closed-loop dynamics are mocked." >/dev/null

# --- the question that cannot be measured on this machine at all ----------------------
# No target level: the question was never reached here, so claiming a target the evidence
# was meant to satisfy would be inventing an experiment that did not happen.
researchlog record \
  --question "Does the real actuator saturate at 30 Hz?" \
  --subject-type instrumentation --subject-id INS-002 \
  --level E1 \
  --execution-status env_unsupported --research-outcome none --confidence low \
  --hypothesis H-037 --no-experiment \
  --observation "The machine exposes no actuator interface; no command reached hardware." \
  --limitation "There is no actuator on this machine; the question cannot be measured here." >/dev/null

# --- the experiment that was in flight when the session died --------------------------
researchlog manifest --experiment-id EXP-0142 --status running --quiet \
  --command "$PYTHON probes/replay_probe.py --closed-loop" \
  --input replay_suite=replay-v3 --input mock_closure=true \
  --expected-output probes/residual.json

# Partial output from the cases the dead session did reach, so that ACTIVE's
# `completed_cases` is backed by an artifact. Without this the fixture contradicts itself:
# it claims progress nothing supports, and a careful session is *right* to distrust the
# claim — which turns the case-progress criterion into a test of the fixture. The log stops
# after case-02 because that is where the session died; that is the evidence for pending.
mkdir -p research/runs/EXP-0142
cat > research/runs/EXP-0142/stdout.log <<'STDOUT'
case-01 closed-loop residual 0.22 tracking=release_timing
case-02 closed-loop residual 0.19 tracking=release_timing
STDOUT

# Elapsed time is the one input a fixture cannot manufacture: a run killed one second ago
# has a fresh heartbeat, and this drill is about a session that died 150 minutes ago. So
# the heartbeat is written back. This is the single deliberate mutation in this script,
# and it is what a real 150-minute-old corpse looks like.
"$PYTHON" - <<'BACKDATE'
import json
import pathlib
from datetime import datetime, timedelta, timezone

path = pathlib.Path("research/runs/EXP-0142/manifest.json")
manifest = json.loads(path.read_text(encoding="utf-8"))
manifest["execution"]["heartbeat_or_last_observed_at"] = (
    datetime.now(timezone.utc) - timedelta(minutes=150)
).isoformat()
path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
BACKDATE

# --- ACTIVE: mid-experiment, naming the hypothesis, the cases reached and the ones not  -
researchlog active --set-status running --quiet
researchlog active --rotate-session --quiet
researchlog active --quiet \
  --set 'research_question=Does the residual separation survive closed-loop closure?' \
  --set 'subject.type=harness' --set 'subject.id=HRN-001' \
  --set 'hypothesis_ids=["H-037","H-039"]' \
  --set 'chosen_hypothesis=H-037' \
  --set 'experiment_id=EXP-0142' \
  --set 'intent=Replay the closed-loop slice to see whether the residual separation survives closure.' \
  --set 'expected_evidence.supports_if=the separation persists once the loop is closed' \
  --set 'expected_evidence.weakens_if=the separation vanishes once the loop is closed' \
  --set 'execution.status=running' \
  --set 'execution.completed_cases=["case-01","case-02"]' \
  --set 'execution.pending_cases=["case-03","case-04","case-05"]' \
  --set 'execution.run_manifest=research/runs/EXP-0142/manifest.json' \
  --set 'block.id=RB-014' \
  --set 'block.objective=Resolve whether the residual separation survives closure' \
  --set 'block.max_evidence_iterations=6' \
  --set 'block.max_wall_clock_minutes=180' \
  --set 'block.max_tokens=400000' \
  --set 'block.stop_conditions=["question_resolved","hard_boundary","no_valid_evidence_path"]' \
  --set 'git.expected_touched_files=["research/","probes/replay_probe.py"]' \
  --set-next-action="Inspect whether case-03 reproduces the release-timing residual under closure." \
  --set-observation="Cases 01-02 show the residual tracking release timing; 3 cases unreached."

# --- the architect signal ------------------------------------------------------------
# Signals have no command. They are appended to ARCHITECT.md as fenced blocks and checked
# by validate/reconcile; the shape below is the contract that file states.
"$PYTHON" - <<'SIGNAL'
import pathlib

path = pathlib.Path("research/ARCHITECT.md")
signal = """
```json research:signal
{
  "id": "C-014",
  "type": "CONSTRAINT",
  "statement": "Do not modify the navigation planner.",
  "scope": "closed-loop residual research",
  "expiry": "RB-014 close",
  "source_text": "导航 planner 先别动，等这轮闭环 residual 研究收尾再说。",
  "created_at": "2026-09-13T22:40:00+08:00",
  "active": true
}
```
"""
path.write_text(path.read_text(encoding="utf-8").rstrip() + "\n" + signal, encoding="utf-8")
SIGNAL

# --- commit the state, then leave the tree dirty the way the dead session left it ------
# The uncommitted probe edit is the diff whose intent the new session has to recover:
# the session that died had begun adding the closed-loop flag the in-flight run used.
researchlog active --quiet --set 'git.dirty_expected=true'
git add -A
git commit -qm "drill: state as the session that died left it"

"$PYTHON" - <<'PROBE_EDIT'
import pathlib

path = pathlib.Path("probes/replay_probe.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    'import json\nimport pathlib',
    'import argparse\nimport json\nimport pathlib',
).replace(
    'RESIDUAL = 0.41',
    'RESIDUAL = 0.41\nCLOSED_LOOP_RESIDUAL = 0.19',
).replace(
    'def main() -> None:',
    'def main() -> None:\n'
    '    argparse.ArgumentParser().add_argument("--closed-loop", action="store_true").parse_args()',
)
path.write_text(text, encoding="utf-8")
PROBE_EDIT

# --- the fixture is only usable if it reports the picture the drill expects ------------
# --- the fixture must be internally consistent before a session is asked to trust it ---
"$PYTHON" - <<'CONSISTENCY'
import json
import pathlib

stdout = pathlib.Path("research/runs/EXP-0141/stdout.log").read_text(encoding="utf-8")
cases = [line for line in stdout.splitlines() if line.strip()]
if len(cases) != 5:
    raise SystemExit(
        f"the finished experiment's log has {len(cases)} case lines, and the evidence "
        "record citing it claims a breakdown over 5 — the artifact has to support the claim"
    )
tracking = sum(1 for line in cases if "tracking=release_timing" in line)
if tracking != 2:
    raise SystemExit(f"the log shows {tracking} tracking cases, the evidence claims 2")
print(f"  EXP-0141 stdout: {len(cases)} cases, {tracking} tracking release timing")

identity = {
    experiment: (json.loads(pathlib.Path(f"research/runs/{experiment}/manifest.json").read_text())
                 .get("code_state", {}).get("diff_sha256"))
    for experiment in ("EXP-0141", "EXP-0142")
}
if len(set(identity.values())) != 1:
    raise SystemExit(
        "the two runs of the same code carry different code identities: "
        f"{identity}. Something in the workspace moved between them, and the next session "
        "will have to explain it before it can trust anything else."
    )
print(f"  both runs carry the same code identity: {next(iter(identity.values()))[:22]}…")
CONSISTENCY

echo "--- workflow control ---"
"$PYTHON" - <<'CHECK'
import json
import pathlib

# Asserted against the content AGENTS.md declares, not against the source file: the fixture
# is a byte copy of that file, so comparing the two can never fail and would assert nothing.
settings = json.loads(pathlib.Path(".claude/settings.json").read_text())
denied = [
    d for d in settings.get("permissions", {}).get("deny", [])
    if d.startswith("Skill(superpowers:")
]
overrides = [k for k, v in settings.get("skillOverrides", {}).items() if v == "off"]
if not denied:
    raise SystemExit(
        "the drill's settings.json denies no Skill(superpowers:*) entry, so AGENTS.md's\n"
        "workflow block is declared but not wired. A session would face a contract whose\n"
        "enforcement is missing, and the drill could not tell 'the protocol held' from\n"
        "'the model happened not to reach for it'.\n"
        "Fix the fixture, not the criteria."
    )
if not overrides:
    raise SystemExit(
        "the drill's settings.json sets no skillOverride to \"off\". AGENTS.md needs both\n"
        "mechanisms — skillOverrides does not apply to plugin skills, which is why the deny\n"
        "list alone is not the whole block.\n"
        "Fix the fixture, not the criteria."
    )
print(f"workflow block wired: {len(denied)} denied skills, {len(overrides)} overridden off")
CHECK

echo "--- reconcile ---"
# `|| true`: a warning-severity finding makes reconcile exit 3, and that is the expected
# outcome here. The exit code is not the criterion — the check below is.
reconcile_json="$(researchlog reconcile --json || true)"
"$PYTHON" - "$reconcile_json" <<'CHECK'
import json
import sys

envelope = json.loads(sys.argv[1])
codes = sorted(f["code"] for f in envelope["findings"])
expected = ["MANIFEST_STALE_RUNNING"]
if codes != expected:
    raise SystemExit(
        f"fixture built a state the drill does not describe.\n"
        f"  expected: {expected}\n"
        f"  actual:   {codes}\n"
        "Fix the fixture, not the criteria: a drill that runs against an unexpected state\n"
        "produces a verdict nobody can attribute."
    )
print(f"reconcile exit {envelope['exit_code']}, findings {codes}")
CHECK

echo "--- validate ---"
validate_json="$(researchlog validate --json || true)"
"$PYTHON" - "$validate_json" <<'CHECK'
import json
import sys

envelope = json.loads(sys.argv[1])
codes = sorted(f["code"] for f in envelope["findings"])
if codes:
    raise SystemExit(
        f"validate is not clean on the fixture: {codes}\n"
        "The drill's criteria assume a state whose only anomaly is the dead session."
    )
print(f"validate exit {envelope['exit_code']}, findings {codes}")
CHECK

echo
echo "recovery drill fixture ready in $TARGET"
echo "next: open a new session there and give it only '/research-engineering' + 'Continue current research.'"
