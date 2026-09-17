#!/usr/bin/env bash
#
# Build a repository with a long-running run genuinely in flight, for the session-rotation
# fault injection (design §26.4, injection 3):
#
#     start a run that spans a session; after rotation, confirm the new session identifies
#     the existing job and then decides observe / finalize — rather than starting it again.
#
# What makes this different from the recovery drill: the process is *alive*. Nothing here is
# backdated or simulated, so the criterion is about what the session does with a live job it
# did not start. The stale-heartbeat case is the other drill; this is the live one.
#
# Usage:  tests/main/build_rotation_drill.sh <target-dir> [seconds]
#
# The run sleeps for <seconds> (default 900) and then writes its result. It is started with
# `nohup` and `disown` so it survives this script exiting, and it keeps running until it
# finishes or someone stops it — which is the point, and also why this script prints the PID
# and a cleanup line at the end.
#
# Exit 0 means the fixture was built AND a fresh process confirmed the job reads as alive.

set -euo pipefail

SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET="${1:-}"
SECONDS_TO_RUN="${2:-900}"
if [[ -z "$TARGET" ]]; then
  echo "usage: $0 <target-dir> [seconds]" >&2
  exit 64
fi

PYTHON="${PYTHON:-python3}"

rm -rf "$TARGET"
mkdir -p "$TARGET"
cd "$TARGET"

git init -q .
git config user.email drill@example.invalid
git config user.name "rotation drill"

mkdir -p tools
cp -R "$SOURCE_ROOT/tools/researchlog" tools/
cp -R "$SOURCE_ROOT/templates" templates
cp "$SOURCE_ROOT/AGENTS.md" .

# The adapter is this project's own, not the upstream tool repository's. Copying the latter
# verbatim would make the fixture claim a layout it does not have: it names `skills/` and
# `tools/install_research_skills.py`, neither of which a project that merely *uses* the tool
# carries — and AGENTS.md's "Resuming work on the tool itself" points at `docs/WORK_LOG.md`,
# which lives in the repository that develops the tool and nowhere else. A session that read
# those paths as its own went looking for a starting point that does not exist here.
cat > CLAUDE.md <<'CLAUDE_MD'
@AGENTS.md

# Claude Code adapter

This is a research project that **uses** the research-engineering tool; it is not the
repository that develops it.

- The tool is vendored whole at `tools/researchlog`.
- Its skills are installed copies under `.claude/skills/` and `.agents/skills/`. There is no
  `skills/` canonical source here, so there is nothing to regenerate and no drift to check.
- There is no `docs/WORK_LOG.md`. AGENTS.md's "Resuming work on the tool itself" describes the
  upstream repository and does not apply here — this project has one track, the research.
CLAUDE_MD
"$PYTHON" "$SOURCE_ROOT/tools/install_research_skills.py" --target "$TARGET" --quiet

# AGENTS.md declares the workflow-control block as mechanical, enforced in
# `.claude/settings.json` — "not merely discouraged here", and the deny list is the
# load-bearing part. Copying the contract without its enforcement would test a
# configuration the project does not use.
mkdir -p .claude
cp "$SOURCE_ROOT/.claude/settings.json" .claude/settings.json

mkdir -p probes
cat > probes/long_probe.py <<PROBE
"""A long closed-loop sweep. Writes its result only at the end.

Started with $SECONDS_TO_RUN seconds of work so it is still in flight when the session
that launched it is closed.
"""

import json
import pathlib
import time

SECONDS = $SECONDS_TO_RUN


def main() -> None:
    time.sleep(SECONDS)
    pathlib.Path("probes/sweep.json").write_text(json.dumps({"cases_passed": 41, "cases_total": 60}))
    print("sweep finished")


if __name__ == "__main__":
    main()
PROBE

git add -A
git commit -qm "drill: workspace before the long run"

researchlog() { "$PYTHON" tools/researchlog "$@"; }

researchlog init --quiet

# Start the run in the background. `researchlog run` waits for its child, so the only way to
# have a manifest that is `running` while this script returns is to background the tool
# itself. nohup + disown so it outlives the shell that started it.
nohup "$PYTHON" tools/researchlog run \
  --experiment-id EXP-0200 \
  -- "$PYTHON" probes/long_probe.py >/dev/null 2>&1 &
disown || true

# Wait for the manifest to exist, so the fixture never reports a state it has not reached.
for _ in $(seq 1 100); do
  [[ -f research/runs/EXP-0200/manifest.json ]] && break
  sleep 0.1
done
if [[ ! -f research/runs/EXP-0200/manifest.json ]]; then
  echo "the background run never wrote its manifest; nothing to drill" >&2
  exit 1
fi

researchlog active --set-status running --quiet
researchlog active --rotate-session --quiet
researchlog active --quiet \
  --set 'research_question=Does the residual separation survive closed-loop closure?' \
  --set 'subject.type=harness' --set 'subject.id=HRN-001' \
  --set 'hypothesis_ids=["H-041","H-042"]' \
  --set 'chosen_hypothesis=H-041' \
  --set 'experiment_id=EXP-0200' \
  --set 'intent=Run the full closed-loop sweep and read the cases that fail.' \
  --set 'expected_evidence.supports_if=the separation persists once the loop is closed' \
  --set 'expected_evidence.weakens_if=the separation vanishes once the loop is closed' \
  --set 'execution.status=running' \
  --set 'execution.pending_cases=["case-11","case-12","case-13"]' \
  --set 'execution.run_manifest=research/runs/EXP-0200/manifest.json' \
  --set 'block.id=RB-021' \
  --set 'block.objective=Resolve whether the residual separation survives closure' \
  --set 'block.max_evidence_iterations=6' \
  --set 'block.max_wall_clock_minutes=180' \
  --set-next-action="Wait for the sweep to finish, then read the failing cases." \
  --set-observation="Sweep launched; 60 cases, 41 expected to pass."

# --- CURRENT: the working model the two hypotheses are defined against ----------------
# ACTIVE carries hypothesis *IDs*, which are a registry and not a definition. Without this
# block a session can see that H-041 and H-042 exist and cannot tell what either one claims,
# so it cannot choose the next experiment.
#
# The IDs are this fixture's own. Borrowing the skill references' worked examples (H-037 /
# H-039, whose documented meaning is recovery release timing and state ownership) made the
# fixture claim hypotheses unrelated to the question here; so did lifting `case-31/37/42`
# from the reference's stop-go example. A session that read the references first was right to
# distrust the file.
researchlog current --quiet \
  --set 'objective=Does the residual separation survive closed-loop closure?' \
  --set 'evidence_maturity.highest_stable_level=E2' \
  --set 'evidence_maturity.system_wide_level=E1' \
  --set 'evidence_maturity.note=Offline replay only. No closed-loop measurement exists on this machine.' \
  --set 'working_pieces=["probes/long_probe.py — the full closed-loop sweep","the residual metric over sixty cases"]' \
  --set 'highest_value_uncertainties=["whether the residual separation is a property of release timing or of the replay harness","whether closing the loop preserves it"]' \
  --set 'active_research=[{"id":"H-041","claim":"the residual separates release timing from noise because of the timing itself, so the separation survives closed-loop closure"},{"id":"H-042","claim":"the separation is an artifact of offline replay and disappears once the loop is closed"}]' \
  --set 'current_frontier=["offline replay reproduces the release-timing residual on 2 of 5 cases"]' \
  --set 'next_empirical_action=Read the failing cases from the sweep before touching the mechanism.'

git add -A
git commit -qm "drill: a run still in flight, and ACTIVE pointing at it"

# --- the fixture is only usable if a fresh process reads the job as alive -----------------
echo "--- job ---"
job_out="$(researchlog job --experiment-id EXP-0200 2>&1 || true)"
echo "$job_out"
case "$job_out" in
  *alive*) ;;
  *)
    echo "the job does not read as alive; the drill would test nothing" >&2
    exit 1
    ;;
esac

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
reconcile_json="$(researchlog reconcile --json || true)"
"$PYTHON" - "$reconcile_json" <<'CHECK'
import json
import sys

envelope = json.loads(sys.argv[1])
codes = sorted(f["code"] for f in envelope["findings"])
if codes:
    raise SystemExit(
        f"a live run produced findings the drill does not describe: {codes}\n"
        "Fix the fixture, not the criteria."
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
    raise SystemExit(f"validate is not clean on the fixture: {codes}")
print(f"validate exit {envelope['exit_code']}, findings {codes}")
CHECK

pid="$("$PYTHON" -c "
import json, pathlib
manifest = json.loads(pathlib.Path('research/runs/EXP-0200/manifest.json').read_text())
print(manifest.get('execution', {}).get('pid_or_job_id') or '?')
")"

echo "--- the state defines itself ---"
"$PYTHON" - <<'CHECK'
import json
import pathlib
import re

active = json.loads(pathlib.Path("research/ACTIVE.json").read_text(encoding="utf-8"))
text = pathlib.Path("research/CURRENT.md").read_text(encoding="utf-8")
match = re.search(r"```json research:current\n(.*?)\n```", text, re.S)
if match is None:
    raise SystemExit("CURRENT.md carries no research:current block")
current = json.loads(match.group(1))

live = set(active.get("hypothesis_ids") or [])
declared = {entry.get("id") for entry in current.get("active_research") or []}
undefined = sorted(live - declared)
if undefined:
    raise SystemExit(
        f"ACTIVE names hypotheses that nothing defines: {undefined}.\n"
        "A registry is not a definition. A session that can read only IDs cannot choose the\n"
        "next experiment — it can only guess, or invent state it is forbidden to invent.\n"
        "Fix the fixture, not the criteria."
    )
if current.get("objective") != active.get("research_question"):
    raise SystemExit(
        "CURRENT.md and ACTIVE.json disagree about the question:\n"
        f"  CURRENT.objective        = {current.get('objective')!r}\n"
        f"  ACTIVE.research_question = {active.get('research_question')!r}\n"
        "Fix the fixture, not the criteria."
    )
print(f"state defines itself: {len(live)} live hypotheses, each with a stated claim")

adapter = pathlib.Path("CLAUDE.md").read_text(encoding="utf-8")
if "install_research_skills" in adapter:
    raise SystemExit(
        "the adapter names the upstream tool repository's installer, so this fixture is\n"
        "claiming a layout it does not have. It carries no `skills/` source and no\n"
        "`docs/WORK_LOG.md`; a session that reads those paths as its own goes looking for a\n"
        "starting point that does not exist here.\n"
        "Fix the fixture, not the criteria."
    )
print("adapter is this project's own")
CHECK

echo
echo "rotation drill fixture ready in $TARGET"
echo "  the run is ALIVE (pid $pid) and will finish on its own in about $SECONDS_TO_RUN s"
# Only when a human is driving. Under `run_case.sh` the agent is started for you, and a
# hint to `cd` in and start one names the wrong client besides.
if [[ -n "${RE_CASE_DRIVEN:-}" ]]; then
  echo "  driven by run_case.sh — do not cd in and start a session of your own"
else
  echo "  next: cd $TARGET && claude    then give it only:"
  echo "          /research-engineering"
  echo "          Continue current research."
fi
echo "  cleanup when you are done with it:  kill $pid"
