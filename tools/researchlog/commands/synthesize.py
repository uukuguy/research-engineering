"""`researchlog synthesize --block BLOCK_ID` — block-close summary for the Architect.

V1 §14 (`docs/design/V1_IMPLEMENTATION_PLAN.md` lines 119/151/196). The output is a
1-2 page structured summary the Architect reads at block close. It is derived state
in the same sense `STATUS.md` is: a human-readable digest that names the canonical
files it draws from and explicitly defers to them on disagreement.

This verb closes two long-standing gaps:

- V1-D4 #4 (`docs/V1_CASES.md` line 141): the drill's PASS signal is "exit 0;
  output is 1-2 pages", which cannot pass while the verb is undeclared-but-unwired.
- P1-8 (`docs/RESEARCH_ENGINEERING_V1.5_REVIEW.html` line 766): block close is
  supposed to force `belief_delta: none|refined|overturned` to be written; this
  command surfaces a missing `belief_delta` as a `SYNTHESIS_BELIEF_DELTA_MISSING`
  warning so the invariant does not go unrecorded.

The verb is read-only by default — exactly like `status` and `snapshot`, a query
that persisted dirtied the working tree and made the next resume trip over the
query's own footprints. `--write` is the explicit opt-in, and the body that
goes to disk is the same body that goes to stdout; the contract is one
markdown document with two audiences, not two documents.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from researchlog import jgit, repo, schema, state
from researchlog.constraints import (
    BELIEF_DELTAS,
    block_members,
    count_evidence_iterations,
    count_reproduction_iterations,
)
from researchlog.errors import (
    EXIT_PRECONDITION_MISSING,
    Finding,
    RefusedByPolicy,
    Result,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
)

NAME = "synthesize"
HELP = "produce a 1-2 page block-close synthesis for the Architect; writes nothing by default"

# Cap the belief-change section so a block that closes a long-running hypothesis
# cannot leak a wall of text into the synthesis output. The full list is in
# `payload["findings_citing"]` for `--json` consumers; the human body only needs
# enough to back the recommendation.
_FINDINGS_TRUNCATE_AT = 5

# Block ID resolution order:
#   1. `args.block` (explicit override, even when no current block is open)
#   2. `ACTIVE.block.id` (the live block)
# Both None means there is nothing to synthesize — `SYNTHESIS_BLOCK_NOT_FOUND`
# with exit code 5.


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--block",
        metavar="BLOCK_ID",
        nargs="?",
        default=None,
        help="block id to synthesize; default = ACTIVE.block.id",
    )
    parser.add_argument(
        "--write",
        metavar="PATH",
        default=None,
        help="persist the synthesis under the repo root (bare filename lands in research/.derived/)",
    )


def run(args: argparse.Namespace) -> Result:
    paths = repo.require(args.root)

    # Resolve the write target first so an escape attempt fires regardless of
    # block state. A path-above-root refusal is a `RefusedByPolicy` exception,
    # which the CLI converts to a `SYNTHESIS_PATH_OUTSIDE_ROOT` finding at
    # exit code 4 — and the rest of `run()` never gets to look at the block.
    write_target: Path | None = None
    if args.write is not None:
        write_target = _target(paths, args.write)

    active = _safe_load_active(paths)
    ledger = _safe_load_ledger(paths)

    block_id = args.block or (active.get("block.id") if active else None)
    if block_id is None:
        result = Result(
            payload={"block_id": None, "generated_at": _now()},
            human=_now(),
        )
        result.add(
            Finding(
                "SYNTHESIS_BLOCK_NOT_FOUND",
                SEVERITY_ERROR,
                "-",
                "no block id supplied and ACTIVE.block.id is null",
                "open a block with `researchlog active --set block.id=BL-N` or "
                "pass `--block BL-N` explicitly",
            )
        )
        # Refuse at the precondition layer rather than the state layer — the
        # agent reading the exit code should not have to distinguish "I forgot
        # to open a block" from "the state file is corrupted". Override the
        # default Result exit (which would be EXIT_STATE_INVALID = 2) so the
        # code matches `PreconditionMissing`'s contract.
        result.exit_code = EXIT_PRECONDITION_MISSING
        return result

    block_section_dict: dict[str, Any] = {}
    if active is not None:
        section = active.get("block")
        if isinstance(section, dict):
            block_section_dict = dict(section)
    members: Sequence[Mapping[str, Any]] = block_members(
        block_id, list(ledger.records.values())
    )
    derived_count = count_evidence_iterations(members)
    derived_repro = count_reproduction_iterations(members)
    evidence_levels = Counter(
        str(record.get("evidence_level") or "?")
        for record in members
    )

    findings_citing = _findings_citing(paths, ledger, members)
    frontier = _frontier(paths)
    reconcile_codes = _reconcile_codes(paths)
    recommendation, rec_finding = _recommend(
        block_section=block_section_dict,
        derived_count=derived_count,
        members=members,
        reconcile_codes=reconcile_codes,
    )

    body = _render(
        block_id=block_id,
        block_section=block_section_dict,
        derived_count=derived_count,
        derived_repro=derived_repro,
        evidence_levels=evidence_levels,
        members_count=len(members),
        total_records=len(ledger.records),
        findings_citing=findings_citing,
        frontier=frontier,
        reconcile_codes=reconcile_codes,
        recommendation=recommendation,
    )

    payload: dict[str, Any] = {
        "block_id": block_id,
        "generated_at": _now(),
        "wrote": None,
        "iterations": {
            "completed": derived_count,
            "reproduction": derived_repro,
            "block_declared_completed": block_section_dict.get("completed_evidence_iterations"),
            "block_declared_reproduction": block_section_dict.get("reproduction_iterations"),
        },
        "evidence_levels": dict(sorted(evidence_levels.items())),
        "findings_citing": findings_citing,
        "frontier": frontier,
        "open_reconcile_codes": reconcile_codes,
        "recommendation": recommendation,
    }

    result = Result(payload=payload, human=body)

    if not members:
        result.add(
            Finding(
                "SYNTHESIS_ZERO_RECORDS",
                SEVERITY_WARNING,
                block_id,
                "no evidence records carry this block_id",
                "verify `record --block-id` was set when the records were created, "
                "or that the ledger has not been migrated to a different id format",
            )
        )

    if block_section_dict.get("belief_delta") is None:
        result.add(
            Finding(
                "SYNTHESIS_BELIEF_DELTA_MISSING",
                SEVERITY_WARNING,
                block_id,
                "block.belief_delta is unset; P1-8 invariant: a block must close with "
                "belief_delta in {none, refined, overturned}",
                "close the block with "
                "`researchlog active --close-block --belief-delta <none|refined|overturned>`",
            )
        )

    if rec_finding is not None:
        result.add(rec_finding)

    if write_target is None:
        return result

    # `research/.derived/` is not created by `init`; mirror `ioutil.write_json_atomic`
    # and create the parent on demand so the first `--write` of a session does not
    # FileNotFoundError out of an otherwise valid verb.
    write_target.parent.mkdir(parents=True, exist_ok=True)
    write_target.write_text(body, encoding="utf-8")
    result.payload["wrote"] = str(write_target)
    for finding in _guard_ignored(paths, write_target):
        result.add(finding)
    return result


def _safe_load_active(paths: repo.ResearchPaths) -> Any:
    """Load ACTIVE.json without crashing the synthesis on a broken state file.

    The default `load_active` raises on parse errors; here a broken ACTIVE
    degrades gracefully to "no block, no recommendation" so the Architect still
    sees a body that points at the canonical files. `reconcile` is the right
    place to be loud about ACTIVE damage. Return type is `Any` because the
    Record wrapper exposes `.get()` but is not itself a `dict[str, Any]`.
    """
    try:
        return state.load_active(paths)
    except Exception:  # noqa: BLE001 - degraded mode is by design here
        return None


def _safe_load_ledger(paths: repo.ResearchPaths) -> state.Ledger:
    try:
        return state.load_ledger(paths)
    except Exception:  # noqa: BLE001
        return state.Ledger()


def _findings_citing(
    paths: repo.ResearchPaths,
    ledger: state.Ledger,
    members: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Findings whose `evidence` list overlaps with this block's records.

    Block-evidence IDs are derived from member records (any record that carries
    the matching `block_id`), then intersected against each finding's cited EV
    list. The result is intentionally structural — synthesize does not judge
    whether the citation is current or stale; that is `reconcile`'s job.
    """
    if not members or not paths.findings.is_file():
        return []
    try:
        block_evidence_ids = {str(record.get("evidence_id")) for record in members}
        block_evidence_ids.discard("None")
        out: list[dict[str, Any]] = []
        for entry in ledger.findings_entries:
            cited = {str(ev) for ev in (entry.get("evidence") or [])}
            if cited & block_evidence_ids:
                out.append(
                    {
                        "id": entry.get("id"),
                        "status": entry.get("status"),
                        "confidence": entry.get("confidence"),
                        "max_evidence_level": entry.get("max_evidence_level"),
                    }
                )
        return out
    except Exception:  # noqa: BLE001
        return []


def _frontier(paths: repo.ResearchPaths) -> dict[str, Any]:
    """Pull the research-frontier fields out of CURRENT.md's `research:current` block.

    Missing fields render as `(unset)` in the human body; the payload mirrors
    the same shape so `--json` consumers see the same empty-state contract.
    """
    if not paths.current.is_file():
        return {"present": False}
    try:
        block = schema.find_block(paths.current.read_text(encoding="utf-8"), "current")
    except Exception:  # noqa: BLE001
        return {"present": True, "readable": False}
    if block is None:
        return {"present": False}
    maturity = block.get("evidence_maturity") or {}
    return {
        "present": True,
        "objective": block.get("objective"),
        "current_frontier": list(block.get("current_frontier") or []),
        "highest_value_uncertainties": list(block.get("highest_value_uncertainties") or []),
        "next_empirical_action": block.get("next_empirical_action"),
        "evidence_maturity": {
            "highest_stable_level": maturity.get("highest_stable_level"),
            "system_wide_level": maturity.get("system_wide_level"),
            "note": maturity.get("note"),
        },
    }


def _reconcile_codes(paths: repo.ResearchPaths) -> list[str]:
    """Find the codes reported by `reconcile`, but without re-running the full detector suite.

    The cheapest source of "what does reconcile think is wrong" is `snapshot`,
    which already embeds a one-level reconcile summary. We do not import
    `commands.snapshot` (cycle risk — see notes in the Plan) so we only borrow
    the *idea* of the summary, not its code path. If `snapshot` is unavailable,
    we return `[]` and the human body surfaces `(none)` rather than fabricating
    a reconcile pass.
    """
    try:
        from researchlog.commands.snapshot import _build as snapshot_build  # type: ignore

        snap = snapshot_build(paths)
        codes = snap.get("reconcile", {}).get("codes") or []
        return [str(c) for c in codes]
    except Exception:  # noqa: BLE001 - the import cycle is "never fatal"
        return []


def _recommend(
    *,
    block_section: dict[str, Any],
    derived_count: int,
    members: Sequence[Mapping[str, Any]],
    reconcile_codes: list[str],
) -> tuple[str, Finding | None]:
    """One of four close-time recommendations, surfaced as `recommendation`.

    The finding is `None` for the happy path; the others carry their own
    severity so the exit code reflects the right level of concern.
    """
    belief_delta = block_section.get("belief_delta")
    max_iter = block_section.get("max_evidence_iterations")

    if belief_delta is None:
        return (
            "P1-8 violated — write belief_delta before close "
            "(`researchlog active --close-block --belief-delta <none|refined|overturned>`)",
            None,
        )
    if reconcile_codes:
        return (
            "reconcile disagrees — run `researchlog reconcile --json` and address the codes "
            "before closing",
            None,
        )
    if isinstance(max_iter, int) and derived_count >= max_iter:
        return (
            f"ready to close — iteration budget exhausted "
            f"({derived_count}/{max_iter}, belief_delta={belief_delta})",
            None,
        )
    if not members:
        return (
            "more iterations possible — block has no records yet; record an evidence "
            "iteration and re-synthesize",
            None,
        )
    return (
        f"more iterations possible — {derived_count} iterations so far, "
        f"budget {max_iter if max_iter is not None else 'unset'}; belief_delta already set",
        None,
    )


def _render(
    *,
    block_id: str,
    block_section: dict[str, Any],
    derived_count: int,
    derived_repro: int,
    evidence_levels: Counter[str],
    members_count: int,
    total_records: int,
    findings_citing: list[dict[str, Any]],
    frontier: dict[str, Any],
    reconcile_codes: list[str],
    recommendation: str,
) -> str:
    """Markdown body. 30-60 lines, Architect-readable.

    The opening is a blockquote, not the HTML comment that STATUS.md uses —
    STATUS.md's `<!-- DERIVED SNAPSHOT — NOT SOURCE OF TRUTH -->` is the
    machine anchor `reconcile._stale_status` parses. Synthesize has no such
    contract, so a prose disclaimer is the right shape.
    """
    belief_delta = block_section.get("belief_delta")
    belief_delta_rendered = (
        belief_delta
        if belief_delta in BELIEF_DELTAS
        else "(unset — P1-8 violation)"
    )
    max_iter = block_section.get("max_evidence_iterations")
    max_wall = block_section.get("max_wall_clock_minutes")
    max_tokens = block_section.get("max_tokens")
    stop_conditions = block_section.get("stop_conditions") or []

    lines: list[str] = [
        f"# Block synthesis: {block_id}",
        "",
        "> Derived summary — read alongside `research/ACTIVE.json`, "
        "`research/CURRENT.md`, and `research/FINDINGS.md` (the canonical state). "
        "This document is what the block's evidence implies; the canonical files "
        "are authoritative when they disagree.",
        "",
        "## §0 Header",
        "",
        f"- generated_at: `{_now()}`",
        f"- ledger: {total_records} total records; {members_count} belong to block `{block_id}`",
        "- canonical sources: ACTIVE.json, CURRENT.md, FINDINGS.md",
        "",
        "## §1 Block identity",
        "",
        f"- id: `{block_id}`",
        f"- objective: {block_section.get('objective') or '(unset)'}",
        f"- belief_delta: {belief_delta_rendered}",
        f"- stop_conditions: {stop_conditions if stop_conditions else '(none)'}",
        f"- max_evidence_iterations: {max_iter if max_iter is not None else '(unset)'}",
        f"- max_wall_clock_minutes: {max_wall if max_wall is not None else '(unset)'}",
        f"- max_tokens: {max_tokens if max_tokens is not None else '(unset)'}",
        "",
        "## §2 Evidence summary",
        "",
        f"- iterations: completed={derived_count} "
        f"/ max={max_iter if max_iter is not None else '(unset)'}",
        f"- reproduction iterations: {derived_repro}",
        "- evidence-level breakdown: "
        + ", ".join(
            f"{level}={evidence_levels.get(level, 0)}"
            for level in ("E0", "E1", "E2", "E3", "E4", "E5")
        ),
        f"- block count agreement: "
        + _count_agreement(derived_count, block_section.get("completed_evidence_iterations")),
        "",
        "## §3 Belief change",
        "",
    ]

    if not findings_citing:
        lines.append("- (no FINDINGS.md entries cite this block's evidence)")
    else:
        lines.append(
            f"Findings citing this block's evidence ({len(findings_citing)} of "
            f"{len(findings_citing)} total):"
        )
        for entry in findings_citing[:_FINDINGS_TRUNCATE_AT]:
            lines.append(
                f"- `{entry.get('id')}`: {entry.get('status')} · "
                f"{entry.get('confidence') or '?'} · "
                f"max evidence {entry.get('max_evidence_level') or '?'}"
            )
        if len(findings_citing) > _FINDINGS_TRUNCATE_AT:
            lines.append(f"- (+{len(findings_citing) - _FINDINGS_TRUNCATE_AT} more in payload)")
    lines.append("")

    lines.extend(
        [
            "## §4 Frontier & uncertainty",
            "",
            f"- objective: {frontier.get('objective') or '(unset)'}",
            f"- current_frontier: {_render_list(frontier.get('current_frontier'))}",
            f"- highest_value_uncertainties: "
            f"{_render_list(frontier.get('highest_value_uncertainties'))}",
            f"- next_empirical_action: {frontier.get('next_empirical_action') or '(unset)'}",
            "- evidence_maturity: "
            + _render_maturity(frontier.get("evidence_maturity") or {}),
            "",
            "## §5 Open issues",
            "",
            f"- run `researchlog reconcile --json` "
            f"(codes: {', '.join(reconcile_codes) if reconcile_codes else '(none)'})",
            "",
            "## §6 Next action / closure recommendation",
            "",
            f"- budget: "
            + (
                "exhausted"
                if isinstance(max_iter, int) and derived_count >= max_iter
                else f"remaining ({derived_count}/{max_iter if max_iter is not None else 'unset'})"
            ),
            f"- belief_delta: {'set' if belief_delta is not None else 'missing — P1-8'}",
            f"- recommendation: {recommendation}",
            "",
        ]
    )
    return "\n".join(lines)


def _count_agreement(derived: int, declared: Any) -> str:
    """Phrase the block count check without inventing a finding.

    The block contract check that does the real work lives in
    `constraints.check_block_contract`; this is the prose mirror for the
    Architect's eye. Drift between derived and declared is reported verbatim
    so the Architect sees the same number reconcile would.
    """
    if declared is None:
        return "(block.completed_evidence_iterations is unset)"
    if derived == declared:
        return f"matches ledger ({derived})"
    return f"DRIFT — derived={derived}, declared={declared} (see reconcile)"


def _render_list(values: Any) -> str:
    if not values:
        return "(unset)"
    if isinstance(values, list):
        return "; ".join(str(v) for v in values) if values else "(unset)"
    return str(values)


def _render_maturity(maturity: dict[str, Any]) -> str:
    if not maturity:
        return "(unset)"
    return (
        f"highest_stable={maturity.get('highest_stable_level') or '?'}, "
        f"system_wide={maturity.get('system_wide_level') or '?'}"
    )


def _target(paths: repo.ResearchPaths, raw: str) -> Path:
    """Resolve a write path, refusing escapes above the repo root.

    Synthesize's body is Architect prose — the safest default is to land bare
    filenames under `research/.derived/` (gitignored scratch space), while
    letting the caller route elsewhere with an explicit relative path. A `..`
    component or absolute path above the repo root is refused outright, because
    synthesizing outside the repo would put a second source of truth next to
    the canonical files.
    """
    candidate = Path(raw)
    if candidate.is_absolute():
        target = candidate.resolve()
    elif candidate.parent == Path("."):
        target = (paths.derived / candidate).resolve()
    else:
        target = (paths.root / candidate).resolve()
    if not target.is_relative_to(paths.root.resolve()):
        raise RefusedByPolicy(
            "SYNTHESIS_PATH_OUTSIDE_ROOT",
            f"{raw!r} resolves to {target}, outside {paths.root}",
            "a block synthesis belongs at or under the repo root; pass a "
            "relative path, or move the file into research/.derived/ if that "
            "is the intent",
        )
    return target


def _guard_ignored(paths: repo.ResearchPaths, target: Path) -> list[Finding]:
    """Mirror `status._guard_ignored` / `snapshot._guard_ignored`.

    A synthesis file the Architect asks for under the repo root will dirty the
    tree unless gitignored. The warning names the path and the fix; it does
    not refuse the write — the caller asked for it.
    """
    if not jgit.is_repository(paths.root):
        return []
    relative = target.relative_to(paths.root.resolve()).as_posix()
    if jgit.check_ignore(paths.root, relative) is not None:
        return []
    return [
        Finding(
            "SYNTHESIS_NOT_IGNORED",
            SEVERITY_WARNING,
            relative,
            "the synthesis path is not excluded by .gitignore, so writing it dirties the tree",
            f"add '{relative}' (or its parent directory) to .gitignore; a "
            "block synthesis is derived state and must not be a source of truth on disk",
        )
    ]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")