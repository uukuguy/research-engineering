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
  echo "  clients: claude pi stub (stub is the negative control: it must FAIL)" >&2
  exit 64
fi

PYTHON="${PYTHON:-python3}"
FIXTURE="${CASE_FIXTURE:-/tmp/re-case-$CASE-$CLIENT}"

# The transcript goes in a private, unpredictable directory rather than a fixed name in
# /tmp: a predictable path is one another local user can pre-create — as a symlink, say —
# and it also means two runs of the same case collide. The fixture keeps its documented,
# predictable path because the manual workflow in docs/V0_CASES.md tells you to `cd` into
# it, and because the builder `rm -rf`s it before use.
WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/re-cases.XXXXXX")"
chmod 700 "$WORKDIR"
TRANSCRIPT="$WORKDIR/$CASE-$CLIENT.transcript.jsonl"

if [[ -L "$FIXTURE" ]]; then
  echo "refusing: the fixture path is a symlink ($FIXTURE)" >&2
  exit 70
fi

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
    # `--dangerously-skip-permissions` is load-bearing today, and that is a defect in the
    # harness rather than a requirement of the case. The fixture copies the project's
    # `.claude/settings.json`, which carries `permissions.deny` and `skillOverrides` but no
    # `defaultMode` and no `allow` list — so headless, every tool call would wait for an
    # approval nobody is there to give.
    #
    # Two reasons to want it gone, and the second is the stronger one:
    #
    #   Security: the agent runs with every permission bypassed. The exposure is the
    #   developer's own machine and an in-repo fixture, not untrusted input — but it is a
    #   real bypass and a sandbox would be the honest place for it.
    #
    #   Validity: a case that only completes because permissions were bypassed does not
    #   tell us what happens in the architect's own session, which is permissioned. The
    #   acceptance criterion is that the protocol works without a human present; a harness
    #   that removes the permission system is testing a different thing.
    #
    # Set CASE_PERMISSION_MODE=default to run without the flag. That run is the experiment:
    # if it completes, the flag can go; if it stalls at an approval, we learn exactly which
    # verb the protocol needs and can allow-list that one.
    PERMISSION_MODE="${CASE_PERMISSION_MODE:-bypass}"
    if [[ "$PERMISSION_MODE" == "bypass" ]]; then
      AGENT=(claude -p "$PROMPT" --dangerously-skip-permissions
             --output-format stream-json --verbose)
    else
      AGENT=(claude -p "$PROMPT" --output-format stream-json --verbose)
    fi
    echo "permission mode: $PERMISSION_MODE (CASE_PERMISSION_MODE)" >&2
    ;;
  pi)
    # Three things about pi, each checked rather than assumed:
    #
    #   1. It reads AGENTS.md and CLAUDE.md natively.
    #   2. It does not discover this fixture's `.agents/skills` on its own, and `--skill`
    #      needs the absolute path -- a relative one silently loads nothing and the session
    #      runs with the user's skills instead.
    #   3. `--no-skills` is pi's equivalent of the workflow block. Without it pi loads the
    #      user-level delivery-workflow skills -- brainstorming, writing-plans,
    #      test-driven-development, project-state -- which AGENTS.md says are mechanically
    #      disabled for this project. `.claude/settings.json` does that on the Claude side;
    #      there is no project-level equivalent for pi, so the flag is the mechanism.
    #
    # Credentials live in the project's own .env, not in the agent background environment.
    set -a
    # shellcheck disable=SC1091
    . "$SOURCE_ROOT/.env"
    set +a
    AGENT=(pi -p "$PROMPT" --no-skills --skill "$FIXTURE/.agents/skills" --approve)
    ;;
  stub)
    # A negative control, and the only client that costs nothing. An agent that does
    # nothing must FAIL the criteria that ask anything of it. A case that *passes* against
    # this client is not measuring what it claims, and the smoke test below is what makes
    # that visible without spending a session.
    AGENT=(sh -c 'echo "stub: no session was started; this is the negative control" >&2; exit 0')
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
# Tells the builder a script is driving, so it does not print a hand-driving hint that
# names the wrong client.
export RE_CASE_DRIVEN=1
"${BUILDER[@]}"
chmod 700 "$FIXTURE"

BASELINE="$(git -C "$FIXTURE" rev-parse HEAD)"
# The digest of the vendored tool, taken now, before any agent has run. Without it the
# checker cannot tell a session that used the tool from one that rewrote it.
TOOL_HASH="$("$PYTHON" "$SOURCE_ROOT/tests/main/verify_case.py" --tool-hash-of "$FIXTURE")"
echo "=== baseline: ${BASELINE:0:8} · tool ${TOOL_HASH:0:12} ==="

echo "=== drive: $CLIENT ==="
( cd "$FIXTURE" && "${AGENT[@]}" ) >"$TRANSCRIPT" 2>&1 || echo "agent exited non-zero (see $TRANSCRIPT)"
echo "transcript: $TRANSCRIPT ($(wc -c <"$TRANSCRIPT" | tr -d ' ') B)"

# An agent that never finished is not an agent that failed.
#
# A session killed mid-stream leaves a fixture that looks like one where nothing happened,
# and the criteria then return FAILs that read like behaviour — "it recorded no intent",
# "it produced no evidence" — when in fact the run has no verdict at all. This is the
# measurement-point defect the M1 criterion already taught: when the criteria are
# unambiguous, the question can just be *where the measurement was taken*.
COMPLETE=no
case "$CLIENT" in
  stub) COMPLETE=yes ;;
  claude) if grep -q '"type":"result"' "$TRANSCRIPT" 2>/dev/null; then COMPLETE=yes; fi ;;
  pi) if [[ -s "$TRANSCRIPT" ]]; then COMPLETE=yes; fi ;;
esac

if [[ "$COMPLETE" != yes ]]; then
  echo
  echo "INCOMPLETE: the $CLIENT session has no completion marker, so it was cut short"
  echo "  (or never started). Transcript: $TRANSCRIPT"
  echo "  Nothing is judged: a run that was stopped mid-stream has no verdict, and FAILs"
  echo "  from it would describe the interruption, not the protocol."
  echo "  Re-drive it by hand:  cd $FIXTURE  and start the client yourself."
  exit 3
fi

echo "=== judge ==="
"$PYTHON" "$SOURCE_ROOT/tests/main/verify_case.py" "$CASE" "$FIXTURE" \
  --baseline "$BASELINE" --tool-hash "$TOOL_HASH" --transcript "$TRANSCRIPT"
