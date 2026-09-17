#!/usr/bin/env bash
#
# Run one V0 verification case end to end: build the fixture in a temporary project
# directory, drive a coding agent through it headlessly, then judge the criteria from what
# the session left behind.
#
# Usage:  tests/main/run_case.sh <case> <client> [seconds]
#
#   case    rotation | bootstrap | recovery | evaluator-conflict
#   client  claude | pi
#   seconds only for rotation; how long the in-flight run should last (default 900)
#
# To run a case by hand instead — the guide, the criteria, and what each client needs —
# see docs/V0_CASES.md. Same fixtures, same criteria, same checker; only the driving
# differs, which is the point: a case you can only run one way is a case you cannot check
# your own harness against.
#
# Two things this script is careful about, both paid for:
#
#   The transcript is written OUTSIDE the fixture. Writing it inside plants an anomaly
#   nobody chose, and the fixture's contract is that every anomaly is deliberate -- an
#   unplanted one is indistinguishable from a real defect when the criteria come back red.
#
#   The fixture's build-time commit is captured and handed to the checker. A criterion like
#   "did the session record its intent" cannot be judged against a field the builder itself
#   seeded; it is judged against what changed since the build.

set -euo pipefail

SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CASE="${1:-}"
CLIENT="${2:-}"
SECONDS_TO_RUN="${3:-900}"

if [[ -z "$CASE" || -z "$CLIENT" ]]; then
  echo "usage: $0 <case> <client> [seconds]" >&2
  echo "  cases:   rotation bootstrap recovery evaluator-conflict" >&2
  echo "  clients: claude pi" >&2
  exit 64
fi

PYTHON="${PYTHON:-python3}"
FIXTURE="/tmp/re-case-$CASE-$CLIENT"
TRANSCRIPT="/tmp/re-case-$CASE-$CLIENT.transcript.jsonl"

# --- case table ------------------------------------------------------------------------
# builder: the script that creates the fixture. prompt: what the session is given, and
# nothing more -- the protocol, not a hint, is what is under test.
case "$CASE" in
  rotation)
    BUILDER=(bash "$SOURCE_ROOT/tests/main/build_rotation_drill.sh" "$FIXTURE" "$SECONDS_TO_RUN")
    PROMPT='/research-engineering
Continue current research.'
    ;;
  recovery)
    BUILDER=(bash "$SOURCE_ROOT/tests/main/build_recovery_drill.sh" "$FIXTURE")
    PROMPT='/research-engineering
Continue current research.'
    ;;
  evaluator-conflict)
    BUILDER=(bash "$SOURCE_ROOT/tests/main/build_evaluator_conflict.sh" "$FIXTURE")
    PROMPT='/research-engineering
Continue current research.'
    ;;
  bootstrap)
    BUILDER=(bash "$SOURCE_ROOT/tests/main/build_bootstrap_case.sh" "$FIXTURE")
    # A high-level direction and no algorithm, which is the acceptance criterion (#5).
    PROMPT='/research-engineering

方向：这个队列服务的尾延迟到底是 queue wait 造成的，还是 retry 造成的？'
    ;;
  *)
    echo "unknown case: $CASE" >&2
    exit 64
    ;;
esac

# --- client table ----------------------------------------------------------------------
# Each client declares how it enters Research Mode. They are not the same command with a
# different binary, and pretending otherwise is what #22 exists to find out.
case "$CLIENT" in
  claude)
    AGENT=(claude -p "$PROMPT" --dangerously-skip-permissions
           --output-format stream-json --verbose)
    ;;
  pi)
    # pi reads AGENTS.md and CLAUDE.md natively; its skills are not auto-discovered from
    # this fixture's `.agents/skills`, so the path is passed explicitly. Credentials live
    # in the project's own .env, not in the agent background environment.
    set -a
    # shellcheck disable=SC1091
    . "$SOURCE_ROOT/.env"
    set +a
    AGENT=(pi -p "$PROMPT" --skill "$FIXTURE/.agents/skills" --approve)
    ;;
  *)
    echo "unknown client: $CLIENT" >&2
    exit 64
    ;;
esac

# The transcript must not land inside the thing under test.
case "$TRANSCRIPT" in
  "$FIXTURE"/*) echo "transcript would be written inside the fixture: $TRANSCRIPT" >&2; exit 70 ;;
esac

echo "=== build: $CASE -> $FIXTURE ==="
"${BUILDER[@]}"

BASELINE="$(git -C "$FIXTURE" rev-parse HEAD)"
echo "=== baseline: ${BASELINE:0:8} ==="

echo "=== drive: $CLIENT ==="
( cd "$FIXTURE" && "${AGENT[@]}" ) >"$TRANSCRIPT" 2>&1 || echo "agent exited non-zero (see $TRANSCRIPT)"
echo "transcript: $TRANSCRIPT ($(wc -c <"$TRANSCRIPT" | tr -d ' ') B)"

echo "=== judge ==="
"$PYTHON" "$SOURCE_ROOT/tests/main/verify_case.py" "$CASE" "$FIXTURE" \
  --baseline "$BASELINE" --transcript "$TRANSCRIPT"
