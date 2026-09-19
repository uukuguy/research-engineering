#!/usr/bin/env python3
"""CLI entry point for the RE acceptance pipeline.

Subcommands (mirrored in the Makefile):
  run          run all AUTO cases + emit a Markdown report (default)
  list         list every registered case with its expected status
  list-manual  list only B-class cases (MANUAL_FIXTURE_REQUIRED)
  scan-docs    run docsync scan only — does not touch the report
  fix-docs     run docsync fix — patches the guide

Usage:
  python3 tools/run_acceptance.py run
  python3 tools/run_acceptance.py run --level V0
  python3 tools/run_acceptance.py run --level V1
  python3 tools/run_acceptance.py list
  python3 tools/run_acceptance.py list-manual
  python3 tools/run_acceptance.py scan-docs

The exit code is 0 when no case failed (FAIL) and 1 otherwise.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

# Resolve the repo root from this script's location (tools/run_acceptance.py)
# and put both the repo root and tools/ on sys.path so the
# tools.acceptance.* imports resolve regardless of cwd.
_REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(_REPO_ROOT)
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "tools"))

from tools.acceptance.cases import (  # type: ignore[import-not-found]
    CaseSpec,
    FAIL,
    MANUAL_FIXTURE_REQUIRED,
    cases_by_filter,
)
from tools.acceptance.docsync import scan_guide, apply_fixes  # type: ignore[import-not-found]
from tools.acceptance.manual import render_manual_list  # type: ignore[import-not-found]
from tools.acceptance.reporter import write_report  # type: ignore[import-not-found]
from tools.acceptance.runner import CaseResult  # type: ignore[import-not-found]


def _execute(cases: List[CaseSpec], partial_path: Optional[Path] = None) -> List[Tuple[CaseSpec, CaseResult]]:
    """Run each case in order. Failures are captured, never raised.

    If partial_path is given, write a partial report after each case so a
    20-minute LONG_RUN run still leaves a recoverable snapshot if
    interrupted.
    """
    from tools.acceptance.cases import (  # type: ignore[import-not-found]
        MANUAL,
        MANUAL_FIXTURE_REQUIRED,
    )
    from tools.acceptance.reporter import write_report  # type: ignore[import-not-found]
    pairs: List[Tuple[CaseSpec, CaseResult]] = []
    for case in cases:
        if case.runner is None:
            status = MANUAL_FIXTURE_REQUIRED if case.runner_mode == MANUAL else "SKIPPED"
            pairs.append((
                case,
                CaseResult(case_id=case.id, status=status, error="no runner registered"),
            ))
        else:
            start = time.monotonic()
            try:
                result = case.runner(case)
            except Exception as exc:  # last-resort safety net
                result = CaseResult(
                    case_id=case.id,
                    status=FAIL,
                    error=f"{type(exc).__name__}: {exc}",
                    notes="runner raised",
                )
            result.duration_s = time.monotonic() - start
            pairs.append((case, result))
            # Emit one-line progress to stderr so a long run feels alive.
            last = pairs[-1][1]
            sys.stderr.write(
                f"  [{last.status:<22}] {case.id}  ({case.runner_mode:<10}) "
                f"{last.duration_s:6.2f}s\n"
            )
            sys.stderr.flush()
        # Write a partial report after each case so an interrupted run
        # leaves a recoverable snapshot.
        if partial_path is not None:
            try:
                write_report(partial_path, pairs, docs_changes=[])
            except Exception as exc:  # never let report errors stop the run
                sys.stderr.write(f"  (partial report write failed: {exc})\n")
        sys.stderr.flush()
    return pairs


def cmd_run(args: argparse.Namespace) -> int:
    # Filter by level first. Then by runnable mode: `--mode AUTO` runs
    # only AUTO cases; `--mode ALL` runs AUTO + LONG_RUN. MANUAL cases
    # are never run (their runner is None) but ALWAYS included in the
    # report so the Architect can see what to do by hand.
    from tools.acceptance.cases import AUTO, LONG_RUN, MANUAL as MANUAL_MODE  # type: ignore[import-not-found]
    all_cases_for_run = cases_by_filter(args.level)
    run_modes: set
    if args.mode is None or args.mode.upper() == "AUTO":
        run_modes = {AUTO}
    elif args.mode.upper() == "ALL":
        run_modes = {AUTO, LONG_RUN}
    else:
        run_modes = {args.mode.upper()}
    # Execute only AUTO+LONG_RUN. MANUAL is included in the report so the
    # Architect sees what to do by hand — but their runner is None and
    # _execute will surface them as MANUAL_FIXTURE_REQUIRED without
    # actually invoking any subprocess.
    cases = [c for c in all_cases_for_run if c.runner_mode in run_modes or c.runner_mode == MANUAL_MODE]
    if not cases:
        print(f"no cases registered for level={args.level} mode={args.mode}", file=sys.stderr)
        return 2
    print(
        f"running {sum(1 for c in cases if c.runner_mode in run_modes)} case(s) "
        f"(level={args.level or 'ALL'}, mode={args.mode or 'AUTO'}) "
        f"+ showing {sum(1 for c in cases if c.runner_mode == MANUAL_MODE)} manual case(s) ...",
        file=sys.stderr,
    )
    # Pre-compute the report path so _execute can write a partial report
    # after each case (so an interrupted LONG_RUN still leaves a snapshot).
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out_dir = _REPO_ROOT / "docs"
    out_path = out_dir / f"RE_ACCEPTANCE_REPORT_{ts}.md"

    pairs = _execute(cases, partial_path=out_path)

    # Optional: scan + fix the guide
    changelog: List[str] = []
    if args.fix_docs:
        findings = scan_guide()
        if findings:
            print(f"docsync scan: {len(findings)} finding(s):", file=sys.stderr)
            for f in findings[:20]:
                print(f"  - {f}", file=sys.stderr)
        changelog = apply_fixes(findings)

    # Render the final report (overwrites the partial snapshot).
    write_report(out_path, pairs, docs_changes=changelog)
    print(f"report: {out_path.relative_to(_REPO_ROOT)}", file=sys.stderr)

    # Top-line summary to stdout
    counts = {}
    for _, r in pairs:
        counts[r.status] = counts.get(r.status, 0) + 1
    print(", ".join(f"{k}={v}" for k, v in sorted(counts.items())))

    return 1 if FAIL in counts else 0


def cmd_list(args: argparse.Namespace) -> int:
    cases = cases_by_filter(args.level)
    print(f"{len(cases)} case(s):")
    print()
    print(f"{'id':<28} {'inv':<6} {'expected':<28} {'level':<4} title")
    print("-" * 100)
    for case in cases:
        inv = f"#{case.invariant}" if case.invariant is not None else "cross"
        print(f"{case.id:<28} {inv:<6} {case.expected:<28} {case.level:<4} {case.title}")
    return 0


def cmd_list_manual(args: argparse.Namespace) -> int:
    pairs = [(c, CaseResult(case_id=c.id, status=c.expected, notes=c.notes or ""))
             for c in cases_by_filter(args.level)
             if c.expected == MANUAL_FIXTURE_REQUIRED]
    print(render_manual_list(pairs))
    return 0


def cmd_scan_docs(args: argparse.Namespace) -> int:
    del args  # no flags yet
    findings = scan_guide()
    if not findings:
        print("docsync scan: 0 finding(s)")
        return 0
    print(f"docsync scan: {len(findings)} finding(s):")
    for f in findings:
        print(f"  - {f}")
    return 1


def cmd_fix_docs(args: argparse.Namespace) -> int:
    del args  # no flags yet
    findings = scan_guide()
    log = apply_fixes(findings)
    print(f"docsync fix: applied {len(log)} patch(es); {len(findings)} finding(s) seen")
    for entry in log:
        print(f"  - {entry}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="run_acceptance")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="execute cases + write a Markdown report")
    p_run.add_argument("--level", choices=["V0", "V1", None], default=None,
                       help="restrict to one level (default: both)")
    p_run.add_argument("--mode", choices=["AUTO", "LONG_RUN", "ALL"], default=None,
                       help="restrict to runner_mode (default: AUTO only for "
                            "`make acceptance`; AUTO+LONG_RUN for acceptance-full)")
    p_run.add_argument("--fix-docs", action="store_true",
                       help="after running, scan the guide for drift and patch it")
    p_run.set_defaults(func=cmd_run)

    p_list = sub.add_parser("list", help="print every registered case")
    p_list.add_argument("--level", choices=["V0", "V1", None], default=None)
    p_list.set_defaults(func=cmd_list)

    p_manual = sub.add_parser("list-manual", help="list B-class cases only")
    p_manual.add_argument("--level", choices=["V0", "V1", None], default=None)
    p_manual.set_defaults(func=cmd_list_manual)

    p_scan = sub.add_parser("scan-docs", help="run docsync scan only")
    p_scan.set_defaults(func=cmd_scan_docs)

    p_fix = sub.add_parser("fix-docs", help="apply docsync patches to the guide")
    p_fix.set_defaults(func=cmd_fix_docs)

    return p


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
