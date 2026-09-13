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
cp "$SOURCE_ROOT/AGENTS.md" "$SOURCE_ROOT/CLAUDE.md" .
"$PYTHON" "$SOURCE_ROOT/tools/install_research_skills.py" --target "$TARGET" --quiet

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
  --set 'hypothesis_ids=["H-037","H-039"]' \
  --set 'chosen_hypothesis=H-037' \
  --set 'experiment_id=EXP-0200' \
  --set 'intent=Run the full closed-loop sweep and read the cases that fail.' \
  --set 'execution.status=running' \
  --set 'execution.pending_cases=["case-31","case-37","case-42"]' \
  --set 'execution.run_manifest=research/runs/EXP-0200/manifest.json' \
  --set 'block.id=RB-021' \
  --set 'block.objective=Resolve whether the residual separation survives closure' \
  --set 'block.max_evidence_iterations=6' \
  --set 'block.max_wall_clock_minutes=180' \
  --set-next-action="Wait for the sweep to finish, then read the failing cases." \
  --set-observation="Sweep launched; 60 cases, 41 expected to pass."

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

echo
echo "rotation drill fixture ready in $TARGET"
echo "  the run is ALIVE (pid $pid) and will finish on its own in about $SECONDS_TO_RUN s"
echo "  next: cd $TARGET && claude    then give it only:"
echo "          /research-engineering"
echo "          Continue current research."
echo "  cleanup when you are done with it:  kill $pid"
