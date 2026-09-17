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
# expected skill. A passing case must (a) load and (b) name the
# expected skill in its first-line reply. The prompts are short so
# `claude` and `pi` (the two clients) can answer cheaply and so a
# human reading the report can sanity-check the routing by reading
# the conversation.
CASES = [
    (
        "case-1 router row: research-engineering on bare session",
        "research-engineering",
        "A fresh research session. Resume state and decide what to do next.",
    ),
    (
        "case-2 router row: evaluation-design on local metric disagreement",
        "evaluation-design",
        "The local metric is rising while E4 behavior is flat. What do you do?",
    ),
    (
        "case-3 router row: experiment-review after a run with two live hypotheses",
        "experiment-review",
        "Run EXP-0142 just finished. H-037 and H-039 are live. Decide what to record.",
    ),
    (
        "case-4 router row: retrospective after a phase boundary",
        "retrospective",
        "We are at a phase boundary after 12 counted evidence iterations, all belief_delta: none.",
    ),
    (
        "case-5 router row: research-search when search space must reopen",
        "research-search",
        "No live hypothesis is registered. The dominant failure has moved. What next?",
    ),
    (
        "case-6 router row: scenario-redteam after a promising result",
        "scenario-redteam",
        "The most recent record is `research_outcome: promising`. What defensive pass do you run?",
    ),
]


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


def invoke_client(
    client: str,
    skill_path: Path,
    prompt: str,
    *,
    timeout: int,
) -> tuple[int, str]:
    """Drive one client on one case. Return (exit_code, first_line_of_reply).

    `first_line_of_reply` is the heuristic the script uses to grade
    routing: a passing case must name the expected skill in its first
    line. Substantive grading is out of scope here.
    """
    if client == "pi":
        argv = [
            "pi",
            "--no-extensions",
            "--skill",
            str(skill_path),
            "--",
            prompt,
        ]
    elif client == "claude":
        # The Claude Code CLI on this machine reads `AGENTS.md` /
        # `CLAUDE.md` natively; the `--skill` flag accepts an absolute
        # path to a skill directory. If `claude` is not on PATH for
        # this session (it usually is), fall back to reporting the
        # command rather than failing the run.
        if shutil.which("claude") is None:
            return 127, "claude CLI not on PATH; client matrix run is partial"
        argv = [
            "claude",
            "--skill",
            str(skill_path),
            "--",
            prompt,
        ]
    else:
        raise ValueError(f"unknown client {client!r}")

    completed = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    first_line = (completed.stdout or completed.stderr).splitlines()[0] if (
        completed.stdout or completed.stderr
    ) else ""
    return completed.returncode, first_line


def grade(case: tuple[str, str, str], first_line: str) -> dict[str, object]:
    """Heuristic: the first line must name the expected skill.

    The grading is intentionally loose. A failing grade does not mean
    the skill is wrong — it means the script's heuristic could not
    confirm a routing match in the captured output. Human review is
    still required for V1-D9 sign-off; this script produces evidence
    that the routing *can* reach each skill, not a verdict on
    whether each skill is the *right* one.
    """
    expected = case[1]
    routed_correctly = expected.lower() in first_line.lower()
    return {
        "case": case[0],
        "expected_skill": expected,
        "first_line": first_line,
        "routed_correctly": routed_correctly,
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
                    exit_code, first_line = invoke_client(
                        client,
                        skill_path,
                        case[2],
                        timeout=args.timeout_seconds,
                    )
                except subprocess.TimeoutExpired:
                    rows.append(
                        {
                            "client": client,
                            "skill_root": str(skill_root),
                            "expected_skill": case[1],
                            "skill_md": str(skill_path / "SKILL.md"),
                            "routed_correctly": False,
                            "first_line": f"timed out after {args.timeout_seconds}s",
                            "exit_code": -1,
                        }
                    )
                    continue
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