"""Docsync: fact-check the guide against the live repo and patch drift.

Scope (per plan §7):
  - Patch only factual drift in docs/RE_ACCEPTANCE_CASES.md — file paths,
    flag names, anchor references, status-symbol spellings.
  - NEVER touch §x.1 原意, §x.4 invariant columns, §12 reverse matrix.

Detection → fix wiring (Phase 4):
  status_error    a status symbol not in §13.3's defined set
                  → add a new row to §13.3 table (idempotent)
  anchor_error    a "§N.M" anchor inside the guide whose §N chapter is missing
                  → flag only; do not auto-fix (anchor text is human-curated)
  path_error      a path-like token that resolves against the repo root and
                  does not exist
                  → flag only; most "missing paths" are fixture-only files
                    (sim/, probes/, templates/) that exist only inside
                    /tmp/re-* fixtures, plus cross-document references
                    (V0_ACCEPTANCE_GUIDE.md, V1_CASES.md) that are not
                    expected to live at the repo root.

Each patch produces a one-line log entry that the report prepends under
"## 修订记录".
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Set, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[2]
GUIDE_PATH = _REPO_ROOT / "docs" / "RE_ACCEPTANCE_CASES.md"

# Status symbols the §13.3 table defines (verbatim). Anything ending in
# _REQUIRED / _BLOCKED / _INVALID / _STALE etc. is treated as "looks like
# a status symbol" and matched against this set.
KNOWN_STATUSES: Set[str] = {
    "PASS", "FAIL", "ENV_BLOCKED", "MANUAL_FIXTURE_REQUIRED", "UNJUDGED", "SKIPPED",
}
# New status symbols to add to §13.3 — collected from §9.4 (error code
# appendix). These are not "case verdicts" but they appear in the same
# places the reader might mistake for one.
KNOWN_ERROR_CODES: Set[str] = {
    "RECOVERED_FROM_TMP", "RECOVERY_REQUIRED", "SCHEMA_NEWER_REFUSED",
    "ATTRIBUTION_FORBIDDEN", "COMPARABLE", "REBASELINE_REQUIRED",
    "SELF_REFERENTIAL_COMMIT", "BLOCK_ITERATION_BUDGET_EXCEEDED",
    "SURROGATE_VERDICT_CONTRADICTS_MISSING_FEATURES",
    "WORKTREE_MULTI_WRITER", "EXPIRED_ARCHITECT_SIGNAL", "STATUS_STALE",
    "MANIFEST_STALE_RUNNING", "DUPLICATE_ID", "UNKNOWN_HYPOTHESIS",
    "EVIDENCE_INVALID", "ENV_UNSUPPORTED", "COMMIT_REQUIRED",
}

# Patterns that look like status symbols but are not.
STATUS_LOOKALIKE_DENY: Set[str] = {
    "PASS", "FAIL", "INFO", "WARNING", "ERROR", "TODO", "FIXME",
    "README", "AGENTS", "CLAUDE", "URI", "JSON", "CSV", "HTML", "HTTP",
    "HTTPS", "API", "CLI", "GUI", "REPL", "AST", "YAML", "TOML",
    "PYTHONPATH", "PATH", "OPENAI", "ANTHROPIC", "DEEPSEEK",
    "PWD", "PID", "UID", "GID", "TTY", "EOF", "EOT",
}

# Path-like tokens we deliberately ignore:
#   - cross-document references (live in another file under docs/)
#   - fixture-internal paths (only exist inside /tmp/re-* builders)
#   - historical V0/V1 implementation documents
IGNORE_PATH_SUFFIXES = (
    ".docx", ".pdf", ".html", ".png", ".jpg",
)
IGNORE_PATH_LITERALS = {
    # Cross-document anchors / out-of-scope files
    "WORK_LOG.md", "GOTCHAS.md",
    # Fixture-internal (templates/, sim/, probes/) — live only inside /tmp
    "templates/research", "templates",
    "sim/queue.py", "data/requests.csv", "data/requests_noretry.csv",
    "probes/replay_probe.py", "probes/replay_surrogate.json",
    "probes/long_probe.py", "probes/intervention_trace.json",
    "probes/proxy_score.py", "probes/proxy_surrogate.json",
    "probes/closed_loop_observation.json", "probes/sweep.json",
    "build_bootstrap_case.sh", "build_recovery_drill.sh",
    "build_rotation_drill.sh", "build_evaluator_conflict.sh",
    "run_case.sh", "verify_case.py", "check_negative_control.sh",
    # Skills / memory / project meta (cross-machine)
    "git-research-infrastructure.md", "session-continuity.md",
    "architect-signals.md", "evaluation-design.md",
    "surrogate-validity.md", "environment-feasibility.md",
    "experiment-review.md", "diagnosis.md",
    "research-engineering-project.md",
    # research/ canonical files (state, not files-on-disk-as-source)
    "ARCHITECT.md", "CURRENT.md", "BOUNDARIES.md", "ENVIRONMENT.md",
    "FINDINGS.md", "ACTIVE.json", "STATUS.md", "STATUS_TEST.md",
    # Commands inside tools/researchlog/commands/ — checked separately
    "commands/validate.py",
    # External V0/V1 source files (out of scope: the guide references them)
    "V0_ACCEPTANCE_GUIDE.md", "V1_ACCEPTANCE_GUIDE.md",
    "V0_CASES.md", "V1_CASES.md",
    # Fixture-internal runtime artifacts (only exist inside /tmp/re-*)
    "research/runs/EXP-0200/manifest.json", "result.json",
}


def _is_status_like(token: str) -> bool:
    if token in KNOWN_STATUSES or token in KNOWN_ERROR_CODES:
        return False  # known good
    if token in STATUS_LOOKALIKE_DENY:
        return False
    # Only flag tokens that look like a verdict / error code: all-caps,
    # may contain underscores, and end with a state-like suffix.
    if not re.fullmatch(r"[A-Z][A-Z0-9_]+", token):
        return False
    state_suffixes = ("_REQUIRED", "_BLOCKED", "_INVALID", "_STALE",
                      "_FORBIDDEN", "_REFUSED", "_CONFLICT",
                      "_PRESENT", "_MISSING", "_FAILED")
    if not any(token.endswith(s) for s in state_suffixes):
        return False
    return True


def _resolve_path(token: str) -> Path:
    """Resolve a path-like token against the repo root with smart prefix
    detection: bare filenames are looked up under docs/ first (because the
    guide's prose usually names siblings like WORK_LOG.md without prefix)
    and only fall back to the repo root.
    """
    # Already a path with directory component
    if "/" in token:
        return _REPO_ROOT / token
    # Bare filename → try docs/ first
    in_docs = _REPO_ROOT / "docs" / token
    if in_docs.exists():
        return in_docs
    return _REPO_ROOT / token


def scan_guide() -> List[Tuple[str, str]]:
    """Return a list of ``(kind, message)`` findings (no side effects).

    Kinds:
      "status"   — unknown status symbol
      "anchor"   — §N.M anchor points at a missing chapter heading
      "path"     — path-like token that does not exist on disk
    """
    if not GUIDE_PATH.exists():
        return [("path", f"guide missing: {GUIDE_PATH}")]

    text = GUIDE_PATH.read_text(encoding="utf-8", errors="replace")
    findings: List[Tuple[str, str]] = []

    # Collect already-registered symbols from §13.3 so we don't double-flag
    # tokens that the §13.3 table has already absorbed.
    registered: Set[str] = set()
    sec13_re = re.compile(r"### 13\.3 状态符号约定.*?(?=\n## |\Z)", re.DOTALL)
    sec13 = sec13_re.search(text)
    if sec13:
        for cell in re.findall(r"`([A-Z][A-Z0-9_]+)`", sec13.group(0)):
            registered.add(cell)

    # 1) status symbols — collect every UPPER_CASE_TOKEN; classify.
    for m in re.finditer(r"\b([A-Z][A-Z0-9_]+)\b", text):
        token = m.group(1)
        if token in registered:
            continue
        if _is_status_like(token):
            findings.append(("status", f"unknown status symbol: {token}"))

    # 2) §N.M anchors — only enforce existence of the chapter heading.
    # The guide's own numbering runs §0..§13; anything outside that is
    # almost certainly a cross-reference to another document (e.g. §26.4
    # is V0_ACCEPTANCE_GUIDE.md's fixture section, §12.16 is the KPI
    # section, etc.). Out-of-range chapters are ignored.
    GUIDE_CHAPTER_RANGE = range(0, 14)  # §0..§13
    for m in re.finditer(r"§(\d+)\.(\d+)", text):
        ch = int(m.group(1))
        if ch not in GUIDE_CHAPTER_RANGE:
            continue  # cross-doc anchor
        if ch == 0:  # §0.x is intro, always present
            continue
        heading = re.search(rf"^## {ch}\. ", text, re.MULTILINE)
        if not heading:
            findings.append(("anchor", f"§{ch}: chapter has no heading in this guide"))

    # 3) path-like tokens in backticks.
    for m in re.finditer(r"`([A-Za-z0-9_./-]+\.(?:sh|py|md|jsonl|json))`", text):
        token = m.group(1)
        if token in IGNORE_PATH_LITERALS:
            continue
        if token.endswith(IGNORE_PATH_SUFFIXES):
            continue
        # Skip memory / project file references
        if token.startswith("/Users/"):
            continue
        # Only flag tokens that look repo-local (have a slash) or are known
        # top-level files in docs/.
        target = _resolve_path(token)
        if not target.exists():
            findings.append(("path", f"path missing: {token}"))

    return findings


def apply_fixes(findings: List[Tuple[str, str]]) -> List[str]:
    """Apply fixes to the guide. Returns a changelog (one line per patch).

    Scope: ONLY fixes status_error by appending a row to the §13.3 table.
    Anchor and path errors are flagged but not auto-patched — those need
    Architect judgment (anchor might legitimately point at another doc).
    """
    if not GUIDE_PATH.exists():
        return ["guide missing; no fixes applied"]

    text = GUIDE_PATH.read_text(encoding="utf-8", errors="replace")
    log: List[str] = []

    status_findings = [f for kind, f in findings if kind == "status"]
    if not status_findings:
        return log

    # De-duplicate tokens
    new_tokens = sorted({f.split(": ", 1)[1] for f in status_findings})
    candidates = [t for t in new_tokens if _is_status_like(t)]
    if not candidates:
        return log

    # Locate the §13.3 table head (the first two lines after the heading)
    # and find where the body of the table ends. We insert BEFORE the
    # first prose paragraph after the table — that's the > blockquote
    # with the "三态分类" annotation.
    section_re = re.compile(
        r"(### 13\.3 状态符号约定[^\n]*\n\n\|[^\n]*\n\|[^\n]*\n)(.*?)(?=\n\n>)",
        re.DOTALL,
    )
    m = section_re.search(text)
    if not m:
        return ["§13.3 table not found; could not patch status symbols"]

    table_header = m.group(1)         # heading + |col|col|col| + |---|---|---|---|
    table_body = m.group(2)           # existing rows + trailing newline
    appended: List[str] = []
    for token in candidates:
        # Idempotent: skip tokens already present as a literal cell.
        if f"| `{token}` |" in text or f"| {token} |" in text:
            continue
        appended.append(token)
    if not appended:
        return log

    # Build new rows. Two semantic categories: pure error codes (live in
    # §9.4) vs status symbols (case verdicts). For auto-discovered tokens
    # we can't always tell which; we mark them with a clear "auto-registered"
    # provenance and point the reader at the appropriate appendix.
    new_rows = ""
    for tok in appended:
        if tok in KNOWN_ERROR_CODES:
            new_rows += (
                f"| `{tok}` | `tools/researchlog/errors.py`（自动登记） | "
                f"研究 log 错误码；详见 §9 |\n"
            )
        else:
            new_rows += (
                f"| `{tok}` | 自动登记（{tok} 出现在 §3 / §9 上下文中） | "
                f"待人工审核分类到 verdict / 错误码 |\n"
            )
    new_body = table_body + new_rows
    new_text = text.replace(table_header + table_body, table_header + new_body, 1)
    GUIDE_PATH.write_text(new_text, encoding="utf-8")
    for tok in appended:
        kind = "error code" if tok in KNOWN_ERROR_CODES else "status (待人工核)"
        log.append(f"§13.3: appended row for `{tok}` ({kind})")
    return log


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"
    if cmd == "scan":
        for kind, msg in scan_guide():
            print(f"[{kind}] {msg}")
    elif cmd == "fix":
        log = apply_fixes(scan_guide())
        for entry in log:
            print(f"[{_timestamp()}] {entry}")
    else:
        print(__doc__)
        sys.exit(2)
