"""Manual case lister.

Used by ``make acceptance-manual`` (and ``tools/run_acceptance.py list-manual``)
to print the B-class cases that the Architect must run by hand.

The cases themselves live in ``cases.py`` (with ``expected=MANUAL_FIXTURE_REQUIRED``).
This module is purely a renderer — it does not invent cases.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "tools"))

from tools.acceptance.cases import CaseSpec, MANUAL_FIXTURE_REQUIRED  # type: ignore[import-not-found]
from tools.acceptance.runner import CaseResult  # type: ignore[import-not-found]


def manual_cases(
    pairs: List[Tuple[CaseSpec, CaseResult]],
) -> List[Tuple[CaseSpec, CaseResult]]:
    """Filter to the B-class subset, preserving registry order."""
    return [
        (case, result)
        for case, result in pairs
        if case.expected == MANUAL_FIXTURE_REQUIRED
    ]


def render_manual_list(pairs: List[Tuple[CaseSpec, CaseResult]]) -> str:
    """Plain-text table for the terminal. The Architect scans this on the CLI."""
    rows = manual_cases(pairs)
    if not rows:
        return "No MANUAL_FIXTURE_REQUIRED cases registered.\n"
    out = []
    out.append(f"# {len(rows)} case(s) require Architect execution")
    out.append("")
    out.append(
        "These are the B-class cases — runs that cannot be automated. "
        "Per `V0_ACCEPTANCE_GUIDE.md`, the Architect runs them by hand and "
        "records the verdict in the guide's status table."
    )
    out.append("")
    out.append("| case-id | invariant | 标题 | 跑法 | 来源 |")
    out.append("|---|---|---|---|---|")
    for case, result in rows:
        how = (result.notes or "").replace("|", "\\|")
        inv = f"#{case.invariant}" if case.invariant is not None else "cross"
        out.append(
            f"| `{case.id}` | {inv} | {case.title} | {how} | {case.source} |"
        )
    return "\n".join(out) + "\n"
