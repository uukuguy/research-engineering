#!/usr/bin/env bash
#
# Run every case against the client that does nothing, and require each case to come back
# red.
#
# The rule this enforces is the one the case guide states in prose: an agent that does
# nothing must fail the criteria that ask anything of it, so **a case that passes here is
# not measuring what it claims**. That rule was true and unwritten-down, and the cost was
# concrete: two cases' checkers had never been run against a real fixture at all, and when
# they finally were, one of them judged the fixture's own seeded text as if the session had
# written it — failing a session that declined the plan while accusing it of the opposite
# behaviour.
#
# This is the same shape as tools/check_workflow_block.py: an invariant that is checked
# rather than remembered, because a list cannot notice that the machine grew. Here the
# "machine" is the set of checkers, and it grows every time one is added.
#
# What it asserts, per case:
#
#   * the case is NOT green — at least one criterion fails. Not *which* ones: pinning the
#     specific rows here would rot the moment a criterion is legitimately changed, and a
#     rotten gate gets switched off.
#   * g0 is green — the vendored tool was not modified. A red case for a harness reason is
#     not evidence about the protocol, and g0 failing means every other row is void.
#
# Cost: no model sessions at all. Each case builds a fixture and judges it.
#
# Usage:  tests/main/check_negative_control.sh [seconds-for-rotation]

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECONDS_TO_RUN="${1:-5}"
CASES=(rotation bootstrap recovery evaluator-conflict)

failing=0
for case in "${CASES[@]}"; do
  # The case's own output is captured, not streamed: what matters here is the verdict, and
  # a wall of criterion rows for four cases buries it. It is printed only when the gate
  # itself has something to say.
  output="$(bash "$HERE/run_case.sh" "$case" stub "$SECONDS_TO_RUN" 2>&1)"
  status=$?

  if [[ $status -eq 3 ]]; then
    printf 'BROKEN  %-19s the runner reported an incomplete session (status 3)\n' "$case"
    failing=1
    continue
  fi
  if [[ $status -eq 0 ]]; then
    printf 'GREEN   %-19s a do-nothing agent passed this case\n' "$case"
    printf '        → the case is not measuring what it claims; see docs/V0_CASES.md\n'
    failing=1
    continue
  fi
  if ! grep -q 'PASS *g0' <<<"$output"; then
    printf 'VOID    %-19s g0 did not pass — the session modified the tool that judges it,\n' "$case"
    printf '        so no row of this case is evidence. Re-run before reading anything else.\n'
    failing=1
    continue
  fi
  printf 'ok      %-19s red as required, guard green\n' "$case"
done

if [[ $failing -ne 0 ]]; then
  printf '\nnegative control FAILED\n'
  exit 1
fi
printf '\nnegative control: all %d cases red, guards green\n' "${#CASES[@]}"
