"""RE acceptance pipeline.

A small package that turns docs/RE_ACCEPTANCE_CASES.md into a runnable
verification pipeline. Zero external dependencies: uses only the Python
standard library plus the in-process researchlog CLI driver.

Architecture (one paragraph each):
  cases.py    — frozen CaseSpec dataclass + the hand-written registry
                (~70 cases: V0 + V1).
  runner.py   — three execution modes (researchlog CLI / filesystem /
                fixture) wrapped so a case never raises.
  reporter.py — Markdown + embedded JSON envelope for human and agent
                readers.
  manual.py   — list of B-class cases (MANUAL_FIXTURE_REQUIRED) for the
                Architect to run by hand.
  docsync.py  — fact-check the guide against the live repo and patch
                factual drift, with a per-change audit log.
"""
