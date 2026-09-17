#!/usr/bin/env bash
#
# Build a project with something to research and no research state, for the bootstrap case
# (acceptance M1 / M2 / M3 / M5):
#
#     a fresh project, a high-level direction, no algorithm -- does the agent establish
#     canonical state, probe rather than plan, and record what this machine cannot measure
#     as an environment limit rather than a scientific no?
#
# Usage:  tests/main/build_bootstrap_case.sh <target-dir>
#
# The guide's recipe for session A's fixture copies `tools/`, `templates/`, `AGENTS.md`,
# `.claude/settings.json` and the skills, and calls the result "an empty project". That is
# not reproducible: M2's evidence is that the session "never touched the fixture's `sim/`
# and `data/`", and #2's is that `sim/queue.py` was runnable. A fixture built to that
# recipe has no subject, so the session would have nothing to probe and M2 would pass for
# the wrong reason. This script builds what the evidence describes.
#
# No `research/` directory is created. Bootstrapping it is the thing under test.
#
# Exit 0 means the fixture was built AND it is a fixture: the subject runs, there is no
# research state to lean on, and nothing pre-exists that would make a criterion vacuous.

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
git config user.name "bootstrap case"

mkdir -p tools sim data
cp -R "$SOURCE_ROOT/tools/researchlog" tools/
cp -R "$SOURCE_ROOT/templates" templates
cp "$SOURCE_ROOT/AGENTS.md" .

# The adapter is this project's own. Copying the upstream one verbatim would make the
# fixture claim a layout it does not have -- `skills/`, `docs/WORK_LOG.md` -- and a session
# that read those as its own would go looking for a starting point that is not here.
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

# AGENTS.md declares the workflow block as mechanical, enforced in `.claude/settings.json`.
# Copying the contract without its enforcement would test a configuration the project does
# not use.
mkdir -p .claude
cp "$SOURCE_ROOT/.claude/settings.json" .claude/settings.json

# --- the subject: a queue with retries, and a per-request trace of where time went -------
# Deliberately small and deterministic. The interesting property for M5 is that the trace
# alone cannot answer a causal question -- `backoff_wait` is only assigned once `queue_wait`
# has already crossed a threshold, so its share of the variance is not its causal
# contribution. Recovering that needs instrumentation the fixture does not ship.
cat > sim/queue.py <<'SIM'
"""A single-server queue with timeout-and-retry, and a per-request timing trace.

Run it with `--requests N --seed S --retry on|off`. Total latency decomposes into
queue_wait, service_time, and backoff_wait; the sweep is what turns a latency budget into
a question about which of the three is responsible.
"""

from __future__ import annotations

import argparse
import csv
import heapq
import random
import pathlib

SERVICE_MEAN = 0.004
ARRIVAL_INTERVAL = 0.008  # offered load 0.5 of capacity, so retries have headroom
RETRY_THRESHOLD = 0.030
MAX_ATTEMPTS = 4


def simulate(requests: int, seed: int, retry: bool) -> list[dict[str, float | int]]:
    rng = random.Random(seed)
    free_at = 0.0
    rows: list[dict[str, float | int]] = []
    for request_id in range(requests):
        arrived = request_id * ARRIVAL_INTERVAL
        queue_wait = max(0.0, free_at - arrived)
        service = rng.expovariate(1.0 / SERVICE_MEAN)
        backoff = 0.0
        attempts = 1
        total = queue_wait + service
        while retry and total > RETRY_THRESHOLD and attempts < MAX_ATTEMPTS:
            wait = 0.010 * (2 ** (attempts - 1))
            backoff += wait
            total += wait + rng.expovariate(1.0 / SERVICE_MEAN)
            attempts += 1
        free_at = arrived + total
        rows.append(
            {
                "request_id": request_id,
                "arrived_at": round(arrived, 6),
                "queue_wait": round(queue_wait, 6),
                "service_time": round(service, 6),
                "attempts": attempts,
                "backoff_wait": round(backoff, 6),
                "total_latency": round(total, 6),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--requests", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--retry", choices=["on", "off"], default="on")
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("data/requests.csv"))
    args = parser.parse_args()

    rows = simulate(args.requests, args.seed, args.retry == "on")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    latencies = sorted(r["total_latency"] for r in rows)
    p99 = latencies[int(0.99 * (len(latencies) - 1))]
    print(f"wrote {len(rows)} rows to {args.out}; p99 total latency {p99 * 1000:.1f} ms")


if __name__ == "__main__":
    main()
SIM

"$PYTHON" sim/queue.py --requests 2000 --seed 7 --retry on --out data/requests.csv
"$PYTHON" sim/queue.py --requests 2000 --seed 7 --retry off --out data/requests_noretry.csv

cat > README.md <<'README_MD'
# Latency study

A single-server queue with timeout-and-retry (`sim/queue.py`), and two sweeps of its
per-request timing trace in `data/`.

Run a sweep yourself:

```bash
python3 sim/queue.py --requests 2000 --seed 7 --retry on
```
README_MD

git add -A
git commit -qm "drill: a subject to research, and no research state"

echo "--- the subject runs ---"
"$PYTHON" - <<'CHECK'
import csv
import pathlib

rows = list(csv.DictReader(pathlib.Path("data/requests.csv").open()))
if len(rows) < 100:
    raise SystemExit("the trace is too small to study; fix the fixture, not the criteria")
fields = set(rows[0])
required = {"queue_wait", "service_time", "backoff_wait", "total_latency", "attempts"}
missing = required - fields
if missing:
    raise SystemExit(f"the trace is missing {sorted(missing)}; fix the fixture, not the criteria")
retried = sum(1 for r in rows if int(r["attempts"]) > 1)
print(f"trace: {len(rows)} rows, {retried} with a retry, all three latency components present")
CHECK

echo "--- there is nothing to lean on ---"
"$PYTHON" - <<'CHECK'
import pathlib

if pathlib.Path("research").exists():
    raise SystemExit(
        "the fixture ships research state, so bootstrapping it is not under test.\n"
        "Fix the fixture, not the criteria."
    )
plans = [p for p in pathlib.Path(".").rglob("*.md") if "PLAN" in p.name.upper()]
if plans:
    raise SystemExit(
        f"the fixture ships plan documents ({plans}), so 'wrote no heavy plan' would fail\n"
        "for a reason that is not the session's. Fix the fixture, not the criteria."
    )
vendored = {"tools", ".claude", ".agents", ".git"}
tests = [p for p in pathlib.Path(".").rglob("test_*.py") if not vendored & set(p.parts)]
if tests:
    raise SystemExit(
        f"the fixture ships a test suite ({tests}), so 'added no test suite' would be\n"
        "vacuous. Fix the fixture, not the criteria."
    )
print("no research state, no plan documents, no test suite")
CHECK

echo "--- the adapter is this project's own ---"
"$PYTHON" - <<'CHECK'
import json
import pathlib

adapter = pathlib.Path("CLAUDE.md").read_text(encoding="utf-8")
if "install_research_skills" in adapter:
    raise SystemExit(
        "the adapter names the upstream tool repository's installer, so this fixture claims\n"
        "a layout it does not have. Fix the fixture, not the criteria."
    )
settings = json.loads(pathlib.Path(".claude/settings.json").read_text())
denied = [d for d in settings.get("permissions", {}).get("deny", []) if d.startswith("Skill(")]
overrides = [k for k, v in settings.get("skillOverrides", {}).items() if v == "off"]
if not denied or not overrides:
    raise SystemExit(
        "the workflow block is not wired in the fixture's settings.json, so a session would\n"
        "face a contract whose enforcement is missing. Fix the fixture, not the criteria."
    )
print(f"adapter is this project's own; workflow block wired ({len(denied)} denied, {len(overrides)} off)")
CHECK

echo
echo "bootstrap fixture ready in $TARGET"
if [[ -n "${RE_CASE_DRIVEN:-}" ]]; then
  echo "  driven by run_case.sh — do not cd in and start a session of your own"
else
  echo "  next: cd $TARGET && claude    then give it only:"
  echo "          /research-engineering"
  echo "          <a high-level direction, and no algorithm>"
  echo "  or drive it headless:  tests/main/run_case.sh bootstrap claude"
fi
