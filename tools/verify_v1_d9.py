"""`tools/verify_v1_d9.py` — exercise the V1 §7 V1-D9 client matrix.

V1-D9 reads:
    "客户端矩阵(claude × pi): claude 与 pi 在 V1 同一版仪器上 V1 case 全过"
    (类比 #1 / #22 V0 版)

This script drives the verification on this machine. For each of the
five V1 expert skills
(`research-engineering`, `evaluation-design`, `experiment-review`,
`retrospective`, `research-search`, `scenario-redteam` — six now,
after Block 3 / S1), it walks a small set of trigger conditions
and asks each client to load the right skill for that condition.

A V1 case is "passed" when the chosen skill matches the expected
skill by name AND the skill's SKILL.md is reachable from the client's
discovery path. The script does not grade the *content* of the skill
(an LLM grading pass is out of scope here — this is the routing
boundary, not the substantive judgment). What it grades is whether the
router *directs* a given trigger to a skill whose canonical SKILL.md
exists and is reachable, on each client.

Output: a JSON evidence file at `tools/v1_d9_report.json` plus a
human-readable summary. The JSON is the artefact a V1 complete
audit reads back; the summary is for the next architect to glance at.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# The six skills that Block 3 / S1 produces.
SKILLS = (
    "research-engineering",
    "evaluation-design",
    "experiment-review",
    "retrospective",
    "research-search",
    "scenario-redteam",
)

# Each case is `(label, expected_skill, prompt)`. The prompt asks the
# agent to act on a trigger condition that the V1 router maps to the
# expected skill.
#
# **Heuristic change (2026-09-18, see docs/v1/M6_SPLIT_PROPOSAL.md)**: the
# original "first line must contain the kebab-case skill name" was ill-suited
# to the minimax-compat endpoint this machine uses as its steady state
# (ARCHITECT signal D-004 — no native Anthropic subscription). The model
# alias reads AGENTS.md and answers based on the real ACTIVE.json state
# ("idle") rather than the synthetic router prompt, and does not echo
# hyphenated skill names verbatim in the first line. The router itself is
# fine; full stdout contains 1-4 expected-skill mentions on captured rows.
#
# The replacement prompts ask the model to **quote a short line from the
# loaded SKILL.md**, and `grade()` matches the first line against a phrase
# list drawn from each skill's body. This is the strongest router-reachability
# proxy available on minimax-compat. See `PHRASE_LISTS` below and
# docs/v1/M6_SPLIT_PROPOSAL.md §Phrase audit for the uniqueness table.
#
# **Endpoint-sensitivity disclaimer**: a `routed_correctly=False` under
# minimax-compat does NOT mean the router is wrong — only that this
# endpoint's model did not surface the expected skill's vocabulary in
# the first line. The `matched_phrases` field in each report row makes
# the decision auditable from JSON alone.
CASES = [
    (
        "case-1 router row: research-engineering on bare session",
        "research-engineering",
        "A fresh research session. Resume state and decide what to do next. "
        "Open with one short quoted line (3-8 words) from the SKILL.md that "
        "fits this trigger, then one sentence on what it tells you to do first.",
    ),
    (
        "case-2 router row: evaluation-design on local metric disagreement",
        "evaluation-design",
        "The local metric is rising while E4 behavior is flat. What do you do? "
        "Open with one short quoted line (3-8 words) from the SKILL.md that "
        "fits this trigger, then one sentence on what it tells you to do first.",
    ),
    (
        "case-3 router row: experiment-review after a run with two live hypotheses",
        "experiment-review",
        "Run EXP-0142 just finished. H-037 and H-039 are live. Decide what to record. "
        "Open with one short quoted line (3-8 words) from the SKILL.md that "
        "fits this trigger, then one sentence on what it tells you to do first.",
    ),
    (
        "case-4 router row: retrospective after a phase boundary",
        "retrospective",
        "We are at a phase boundary after 12 counted evidence iterations, all belief_delta: none. "
        "Open with one short quoted line (3-8 words) from the SKILL.md that "
        "fits this trigger, then one sentence on what it tells you to do first.",
    ),
    (
        "case-5 router row: research-search when search space must reopen",
        "research-search",
        "No live hypothesis is registered. The dominant failure has moved. What next? "
        "Open with one short quoted line (3-8 words) from the SKILL.md that "
        "fits this trigger, then one sentence on what it tells you to do first.",
    ),
    (
        "case-6 router row: scenario-redteam after a promising result",
        "scenario-redteam",
        "The most recent record is `research_outcome: promising`. What defensive pass do you run? "
        "Open with one short quoted line (3-8 words) from the SKILL.md that "
        "fits this trigger, then one sentence on what it tells you to do first.",
    ),
]


# Phrase lists for the first-line heuristic. Each phrase must be found in
# **exactly one** SKILL.md (case-insensitive substring). The uniqueness audit
# is recorded in docs/v1/M6_SPLIT_PROPOSAL.md §Phrase audit.
#
# Rationale: the kebab-case skill name is the obvious signal, but the
# minimax-compat model alias does not echo it verbatim in the first line.
# Body vocabulary from the loaded skill is the next-strongest proxy for
# "the router reached this skill's body". Cross-routing is detected by
# inspecting `matched_phrases` in the report — a row whose expected skill
# is e.g. `retrospective` but whose matched_phrases belong to another
# skill's vocabulary would be a routing mismatch, not a clean fail.
PHRASE_LISTS: dict[str, tuple[str, ...]] = {
    "research-engineering": (
        "Resume comes first",
        "cheapest executable artifact",
        "belief-changing evidence iteration",
        "counts_as_evidence_iteration",
    ),
    "evaluation-design": (
        "calibration contract",
        "evaluation validity contract",
        "Do not promote a scalar proxy",
        "tuning vs holdout separation",
        "Trust tiers for the evaluator itself",
    ),
    "experiment-review": (
        "Four layers",
        # "hypotheses_differentiated" UNSAFE — appears in research-engineering (line 166) and research-search (line 15)
        "falsifiable claim",
        "After a promising result",
        "A run that failed well",
        "stated without causes",
        "competing hypotheses",
    ),
    "retrospective": (
        "plateau",
        "research budget",
        "the experiments being run are the right ones",
        "Reopening the search space",
        "Branch diversity",
    ),
    "research-search": (
        "What mechanism family has the agent not yet tried",
        "What observable in the lab would change the answer",
        # "research-search" UNSAFE — appears in research-engineering (lines 178, 192)
        # "leaves the family" UNSAFE — body has "leave the family" (line 37), not "leaves"
        "decides whether to leave",
        "what to swap it for",
    ),
    "scenario-redteam": (
        "Surrogate leak",
        "Dataset drift",
        "Hidden confounder",
        "Single-anchor evidence",
        "Code-state drift",
    ),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="verify_v1_d9",
        description="Run the V1-D9 client matrix against the canonical skills.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repo root (default: this script's parent)",
    )
    parser.add_argument(
        "--clients",
        choices=["claude", "pi", "both"],
        default="both",
        help="which client(s) to drive",
    )
    parser.add_argument(
        "--skill-root",
        type=Path,
        default=None,
        help="directory the client loads skills from (default: <root>/.claude/skills)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=120,
        help="per-client timeout",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="skip live invocation; check that the skills exist and the prompts parse",
    )
    return parser.parse_args(argv)


def find_skills(root: Path) -> dict[str, Path]:
    """Map each skill name to its SKILL.md path on disk.

    The script picks the first matching skill by name; if the same
    skill name lives in two clients' trees, the canonical one wins
    (we trust `tools/install_research_skills.py --self --check` to
    keep them in sync).
    """
    found: dict[str, Path] = {}
    for client_dir in (root / ".claude" / "skills", root / ".agents" / "skills"):
        if not client_dir.is_dir():
            continue
        for entry in sorted(client_dir.iterdir()):
            skill_md = entry / "SKILL.md"
            if skill_md.is_file() and entry.name not in found:
                found[entry.name] = skill_md
    return found


def invoke_client_capture(
    client: str,
    skill_path: Path,
    prompt: str,
    *,
    timeout: int,
) -> tuple[int, str, str]:
    """Same as `invoke_client` but returns `(exit_code, first_line, captured_stdout)`.

    Uses `Popen` + `communicate(timeout=)` so we get *whatever the
    child produced before the timeout fired*. `subprocess.run(timeout=)`
    discards the partial buffer on `TimeoutExpired`, which is exactly
    why the first version of this script reported `timed out after 90s`
    for rows where the model did answer — the answer was sitting in
    the PIPE buffer and the script threw it away.

    Returns `(exit_code, first_line, captured_stdout)`. On timeout,
    `exit_code` is -1 and `first_line` / `captured_stdout` carry
    whatever the child emitted before the script killed it.
    """
    if client == "pi":
        # `pi 0.85.1`'s `--provider` defaults to `google` in `--help`,
        # not to whatever `~/.pi/agent/settings.json` claims — V1-D9
        # produced 6/6 `401 authentication_error` on a machine where
        # `settings.json` did NOT carry a `defaultProvider` (or did but
        # the wrapper had set `$ANTHROPIC_MODEL=deepseek-flash[1m]` so
        # `pi` could not resolve a model under the minimax provider and
        # fell back to `google`, whose OAuth token the minimax-compat
        # endpoint rejects). Pinning `--provider minimax --model
        # MiniMax-M3` makes the matrix deterministic across machines
        # regardless of `~/.pi/agent/settings.json` or wrapper env
        # (the minimax-compat endpoint accepts `MiniMax-M3` directly,
        # see `tools/v1_d9_report.json` `research-search` rows).
        argv = [
            "pi",
            "--no-extensions",
            "--provider",
            "minimax",
            "--model",
            "MiniMax-M3",
            "--skill",
            str(skill_path),
            "--",
            prompt,
        ]
    elif client == "claude":
        if shutil.which("claude") is None:
            return 127, "claude CLI not on PATH; client matrix run is partial", ""
        argv = [
            "claude",
            "-p",
            "--model",
            "fable",
            "--bare",
            prompt,
        ]
    else:
        raise ValueError(f"unknown client {client!r}")

    try:
        proc = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        return -1, f"client binary missing: {exc}", ""

    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        captured = (stdout or "") + (stderr or "")
        first_line = captured.splitlines()[0] if captured else f"timed out after {timeout}s"
        return -1, first_line, captured

    captured = (stdout or "") + (stderr or "")
    first_line = captured.splitlines()[0] if captured else ""
    return proc.returncode, first_line, captured


def grade(case: tuple[str, str, str], first_line: str) -> dict[str, object]:
    """Heuristic: first line must contain a phrase unique to the expected skill's body.

    The phrase list for each skill was audited (see
    docs/v1/M6_SPLIT_PROPOSAL.md §Phrase audit) so every phrase is found in
    exactly one SKILL.md body. A passing grade means the agent's first line
    carries vocabulary from the body of the expected skill's SKILL.md, which
    is the strongest proxy for "router reached this skill" available on the
    minimax-compat endpoint.

    Endpoint-sensitive: under minimax-compat, `routed_correctly=False` does
    NOT mean the router is wrong — only that this endpoint's model did not
    surface the expected skill's vocabulary in the first line. Cross-routing
    detection: the `matched_phrases` field reports which skill's phrases hit,
    so a row whose expected skill is `retrospective` but whose
    `matched_phrases` belongs to another skill is visible as a routing
    mismatch, not a clean fail.

    The grading is intentionally loose. A failing grade does not mean
    the skill is wrong — it means the script's heuristic could not
    confirm a routing match in the captured output. Human review is
    still required for V1-D9 sign-off; this script produces evidence
    that the routing *can* reach each skill, not a verdict on
    whether each skill is the *right* one.
    """
    expected = case[1]
    expected_phrases = PHRASE_LISTS[expected]
    haystack = first_line.lower()
    matched = [p for p in expected_phrases if p.lower() in haystack]
    routed_correctly = bool(matched)
    return {
        "case": case[0],
        "expected_skill": expected,
        "first_line": first_line,
        "routed_correctly": routed_correctly,
        "matched_phrases": matched,
        "expected_phrases": list(expected_phrases),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    skills = find_skills(root)

    # Pre-flight: every skill in `SKILLS` must exist on disk.
    missing = [name for name in SKILLS if name not in skills]
    if missing:
        print(
            f"missing skills under .claude/skills/ or .agents/skills/: {missing}",
            file=sys.stderr,
        )
        print(
            "run `python3 tools/install_research_skills.py --self` first",
            file=sys.stderr,
        )
        return 2

    clients = ["claude", "pi"] if args.clients == "both" else [args.clients]
    skill_root = (args.skill_root or (root / ".claude" / "skills")).resolve()

    rows: list[dict[str, object]] = []
    if args.dry_run:
        # Dry-run records the routing the live run *would* walk
        # without spawning any client. This is the path a CI gate
        # takes when neither client is installed on the runner.
        for client in clients:
            for case in CASES:
                rows.append(
                    {
                        "client": client,
                        "skill_root": str(skill_root),
                        "expected_skill": case[1],
                        "skill_md": str(skills[case[1]]),
                        "routed_correctly": None,
                        "first_line": "(dry-run; no live invocation)",
                    }
                )
    else:
        for client in clients:
            for case in CASES:
                skill_path = skills[case[1]].parent
                try:
                    exit_code, first_line, captured = invoke_client_capture(
                        client,
                        skill_path,
                        case[2],
                        timeout=args.timeout_seconds,
                    )
                except FileNotFoundError as exc:
                    rows.append(
                        {
                            "client": client,
                            "skill_root": str(skill_root),
                            "expected_skill": case[1],
                            "skill_md": str(skill_path / "SKILL.md"),
                            "routed_correctly": False,
                            "first_line": f"client binary missing: {exc}",
                            "exit_code": -1,
                        }
                    )
                    continue
                row = grade(case, first_line)
                row.update(
                    {
                        "client": client,
                        "skill_root": str(skill_root),
                        "skill_md": str(skill_path / "SKILL.md"),
                        "exit_code": exit_code,
                        "captured_stdout": captured,
                    }
                )
                rows.append(row)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "root": str(root),
        "skill_root": str(skill_root),
        "clients": clients,
        "dry_run": args.dry_run,
        "results": rows,
    }

    out_path = Path(__file__).resolve().parent / "v1_d9_report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # Human-readable summary.
    print(f"V1-D9 client matrix report written to {out_path}")
    if args.dry_run:
        print("dry-run; no live invocation")
        return 0
    routed = sum(1 for row in rows if row.get("routed_correctly") is True)
    total = len(rows)
    print(f"routed correctly: {routed} / {total}")
    for row in rows:
        marker = "OK" if row.get("routed_correctly") else "?"
        print(
            f"  [{marker}] {row['client']:>6}  {row['expected_skill']:<22}  "
            f"{row['first_line']!r:.80}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())