"""`researchlog env` — record an environment change, and find what it invalidates.

An evidence record declares the conditions it depends on:

    "invalidated_if": ["env.sim_physics_hz != 30", "inputs.replay_suite changed"]

When the environment moves, the affected evidence is whatever said it depended on the
thing that moved. That turns "is this comparison still valid?" from a judgement call into
a lookup, which is the only reason the predicate mini-language exists.

**Change file format** — the one argument these subcommands take:

    {
      "capability": "simulator upgraded to 3.2",
      "comparability": "REBASELINED",
      "changes": {"sim_physics_hz": 60, "inputs.replay_suite": "data-v4"},
      "notes": "optional free text"
    }

A bare key in `changes` is an `env.` key; a key already prefixed with `env.`, `inputs.`
or `code.` is taken as written. Those are exactly the namespaces predicates address.

Two deliberate constraints:

* **`env query` never touches FINDINGS.md.** Invalidation is a fact about comparability;
  demotion is a belief change and goes through `findings demote`. A scan that silently
  rewrites beliefs is a scan nobody can afford to run.
* **Every list is sorted and no timestamp enters the payload**, so the same query asked
  twice is byte-identical. A report that changes every time it is run cannot be diffed,
  and a report that cannot be diffed cannot be trusted to mean anything.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from researchlog import constraints, ids, ioutil, jgit, model, predicate, repo, schema, state
from researchlog.errors import (
    Finding,
    PredicateSyntaxError,
    PreconditionMissing,
    RefusedByPolicy,
    Result,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    StateInvalid,
)

NAME = "env"
HELP = "record an environment change, or query what it invalidates"

NAMESPACES: tuple[str, ...] = ("env", "inputs", "code")
COMPARABILITY: tuple[str, ...] = ("COMPATIBLE", "REBASELINED", "INCOMPARABLE")
SUPPORTED_BLOCK_VERSION = "1.0"
REVIEW_ACTION = "review confidence; not auto-demoted"
DEFAULT_ENVIRONMENT_ID = "ENV-unspecified"

# The declared tables, and the keys an entry must carry. `available` is handled separately:
# it is a namespace of lists rather than a list of entries.
DECLARABLE: dict[str, tuple[str, ...]] = {
    "limitations": ("id", "capability", "status", "impact"),
    "harnesses": ("id", "capability", "supports_evidence"),
    # V1 Block 1.5 / P4 (docs/design/CAPABILITY_MAP_SHAPE_PROPOSAL.md):
    # capability_map tracks which capabilities are worth investing in next,
    # via a reuse_counter that V1-D7 tests against.
    "capability_map": ("id", "capability", "status", "reuse_counter"),
}
AVAILABLE_NAMESPACES: tuple[str, ...] = ("compute", "simulator", "data", "external_services")


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=None)
    actions = parser.add_subparsers(dest="action", required=True, metavar="ACTION")

    record = actions.add_parser("record", help="merge a change into ENVIRONMENT.md and record it")
    record.add_argument("file", metavar="FILE", help="the change document")
    query = actions.add_parser("query", help="report what the change invalidates; writes nothing")
    query.add_argument("file", metavar="FILE", help="the change document")
    show = actions.add_parser("show", help="print the research:environment block; writes nothing")
    declare = actions.add_parser(
        "declare", help="append an entry to a declared ENVIRONMENT.md table"
    )
    declare.add_argument(
        "table",
        choices=(*DECLARABLE, "available"),
        metavar="TABLE",
        help="limitations | harnesses | capability_map | available",
    )
    declare.add_argument("file", metavar="FILE", help="the entry document")

    # V1 Block 2 / T4: force-update the comparability fingerprint without
    # adding a new history entry. The fingerprint is the anchor every
    # `changed` predicate on a record compares against; if the lab
    # changed something that did not flow through `env record` (a manual
    # edit, a third-party file drop, a CI artefact), the next session's
    # predicates will silently keep comparing against the stale anchor.
    # `rebaseline` is the explicit "I know what I'm doing, refresh the
    # anchor" command.
    rebaseline = actions.add_parser(
        "rebaseline",
        help="refresh the comparability fingerprint without recording a change",
    )
    rebaseline.add_argument(
        "--reason",
        default="manual rebaseline",
        metavar="TEXT",
        help="free-form note; lands in the history entry that records the refresh",
    )

    for action in (record, query, show, declare, rebaseline):
        _accept_shared_flags(action)


def _accept_shared_flags(action: argparse.ArgumentParser) -> None:
    """Let the global flags appear after the verb too, as `env query FILE --json`."""
    action.add_argument("--root", type=Path, default=argparse.SUPPRESS)
    action.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    action.add_argument("--quiet", action="store_true", default=argparse.SUPPRESS)


def run(args: argparse.Namespace) -> Result:
    paths = repo.require(args.root)
    text = _read_environment(paths)
    block = schema.require_block(text, "environment", source=paths.environment.name)

    if args.action == "show":
        return Result(
            payload={"environment": block}, human=json.dumps(block, ensure_ascii=False, indent=2)
        )

    if args.action == "declare":
        return _declare(paths, text, block, args.table, _read_change(args.file))

    if args.action == "rebaseline":
        return _rebaseline(paths, text, block, args.reason)

    change = _read_change(args.file)
    return (
        _record(paths, text, block, change)
        if args.action == "record"
        else _query(paths, block, change)
    )


def _declare(
    paths: repo.ResearchPaths,
    text: str,
    block: dict[str, Any],
    table: str,
    entry: dict[str, Any],
) -> Result:
    """Append to a table this block declares, which until now nothing could write.

    `limitations` and `harnesses` are the two canonical tables that carry evidence
    semantics — a Day-1 criterion asks an infeasible experiment to land in the first as a
    limitation rather than as a refuted hypothesis, and a surrogate's boundary belongs in
    the second. `env record` merges only `comparability` and `history`, so both were
    readable in the skeleton, required by the protocol, and impossible to fill.
    """
    _require_writable_block(block, paths.environment)
    updated = json.loads(json.dumps(block, ensure_ascii=False))

    if table == "available":
        namespace = entry.get("namespace")
        items = entry.get("items")
        if namespace not in AVAILABLE_NAMESPACES:
            raise StateInvalid(
                [
                    Finding(
                        "ENV_NAMESPACE_UNKNOWN",
                        SEVERITY_ERROR,
                        str(namespace),
                        f"unknown namespace; expected one of {', '.join(AVAILABLE_NAMESPACES)}",
                    )
                ]
            )
        if not isinstance(items, list) or not items:
            raise StateInvalid(
                [Finding("ENV_DECLARE_EMPTY", SEVERITY_ERROR, table, "items must be a non-empty list")]
            )
        target = updated.setdefault("available", {}).setdefault(namespace, [])
        target.extend(item for item in items if item not in target)
        changed = f"available.{namespace}"
    else:
        required = DECLARABLE[table]
        # Use `is None` not truthiness: `reuse_counter: 0` and `supports_evidence: ""`
        # are legitimate required values, and treating 0/falsy-string as "missing"
        # would refuse every fresh declaration of a never-reused capability.
        missing = [key for key in required if entry.get(key) is None]
        if missing:
            raise StateInvalid(
                [
                    Finding(
                        "ENV_DECLARE_INCOMPLETE",
                        SEVERITY_ERROR,
                        table,
                        f"entry is missing: {', '.join(missing)}",
                        f"a {table} entry needs {', '.join(required)}",
                    )
                ]
            )
        entries = updated.setdefault(table, [])
        if any(existing.get("id") == entry.get("id") for existing in entries):
            raise StateInvalid(
                [
                    Finding(
                        "ENV_DECLARE_DUPLICATE",
                        SEVERITY_ERROR,
                        str(entry.get("id")),
                        f"{table} already holds an entry with this id",
                    )
                ]
            )
        entries.append(entry)
        changed = f"{table}[{entry.get('id')}]"

    # Schema-checked before the write, so a refused declaration leaves the file untouched.
    validator = schema.load_validator("environment")
    findings = validator.check(updated)
    errors = [finding for finding in findings if finding.severity == SEVERITY_ERROR]
    if errors:
        raise StateInvalid(errors)

    paths.environment.write_text(
        schema.replace_block(text, "environment", updated), encoding="utf-8"
    )

    result = Result(payload={"path": str(paths.environment), "changed": changed})
    for finding in findings:
        result.add(finding)
    result.human = f"declared {changed} in {paths.environment.name}"
    return result


def _rebaseline(
    paths: repo.ResearchPaths,
    text: str,
    block: dict[str, Any],
    reason: str,
) -> Result:
    """V1 Block 2 / T4: refresh the comparability fingerprint.

    The fingerprint is the anchor every `changed` predicate on a record
    compares against. If the lab changed something outside `env record`
    (a manual edit, a third-party file drop, a CI artefact) the next
    session's predicates will silently keep comparing against the stale
    anchor. `rebaseline` is the explicit "I know what I'm doing, refresh
    the anchor" command — it advances the fingerprint, records a small
    history entry noting the refresh, and does not introduce any new
    environment variable. Without this command, the only way to update
    the anchor was to fake a `env record` with no real change.
    """
    _require_writable_block(block, paths.environment)
    updated = json.loads(json.dumps(block, ensure_ascii=False))
    comparability = updated.setdefault("comparability", {})
    previous_fingerprint = comparability.get("fingerprint")
    # A rebaseline is, by construction, *not* a material change. The
    # history entry uses `status: COMPATIBLE` so downstream readers
    # (audit logs, future `changed` walks) can tell a no-op refresh
    # apart from a real environment move.
    if comparability.get("status") is None:
        comparability["status"] = "COMPATIBLE"
    rebaseline_changes = {"rebaseline": reason}
    comparability["fingerprint"] = _fingerprint(updated, rebaseline_changes)
    comparability["last_material_change"] = (
        (block.get("comparability") or {}).get("last_material_change") or _now()
    )
    updated.setdefault("history", []).append(
        {
            "type": "rebaseline",
            "at": _now(),
            "previous_fingerprint": previous_fingerprint,
            "fingerprint": comparability["fingerprint"],
            "reason": reason,
            "comparability": comparability.get("status"),
        }
    )

    paths.environment.write_text(
        schema.replace_block(text, "environment", updated), encoding="utf-8"
    )

    result = Result(
        payload={
            "previous_fingerprint": previous_fingerprint,
            "fingerprint": comparability["fingerprint"],
            "reason": reason,
        },
        human=(
            f"rebaseline advanced the fingerprint to {comparability['fingerprint']}"
        ),
    )
    return result


def _record(
    paths: repo.ResearchPaths,
    text: str,
    block: dict[str, Any],
    change: dict[str, Any],
) -> Result:
    changes = _change_map(change)
    status = _comparability(change, block)
    _require_writable_block(block, paths.environment)
    document, warnings = _evidence_document(paths, block, change, changes, status)

    evidence_id, evidence_path = ids.claim_new("evidence", paths.evidence)
    document["evidence_id"] = evidence_id
    updated = _merge(block, change, changes, status, evidence_id)

    paths.environment.write_text(
        schema.replace_block(text, "environment", updated), encoding="utf-8"
    )
    ioutil.write_json_atomic(evidence_path, document, validator=schema.load_validator("evidence"))

    result = _closure_result(paths, updated, changes)
    result.payload.update(
        {
            "recorded": evidence_id,
            "path": str(evidence_path),
            # the fingerprint as written, not a re-derivation of it
            "fingerprint": (updated.get("comparability") or {}).get("fingerprint"),
        }
    )
    for finding in warnings:
        result.add(finding)
    result.human = f"environment change recorded as {evidence_id}"
    return result


def _query(paths: repo.ResearchPaths, block: dict[str, Any], change: dict[str, Any]) -> Result:
    changes = _change_map(change)
    result = _closure_result(paths, block, changes)
    result.payload["environment_id"] = block.get("environment_id")
    result.payload["fingerprint"] = (block.get("comparability") or {}).get("fingerprint")
    result.human = _human(result.payload)
    return result


def _closure_result(
    paths: repo.ResearchPaths, block: Mapping[str, Any], changes: Mapping[str, Any]
) -> Result:
    ledger = state.load_ledger(paths)
    now = _now_fingerprint(paths, block, changes)
    invalidated, unresolved = _evaluate(ledger, now)
    affected = _affected_findings(ledger, invalidated)
    anchors = _recommended_anchors(block, ledger, invalidated, unresolved)

    result = Result(
        payload={
            "invalidated": invalidated,
            "unresolved": unresolved,
            "affected_findings": affected,
            "recommended_anchors": anchors,
            "counts": {
                "invalidated": len(invalidated),
                "unresolved": len(unresolved),
                "affected_findings": len(affected),
                "recommended_anchors": len(anchors),
            },
        }
    )
    if invalidated:
        result.add(
            Finding(
                "ENVIRONMENT_INVALIDATES_EVIDENCE",
                SEVERITY_WARNING,
                f"{len(invalidated)} predicate(s)",
                "evidence that depended on the changed environment no longer holds automatically",
                "re-run the anchor evidence, or demote the affected findings with `researchlog findings demote`",
            )
        )
    if unresolved:
        result.add(
            Finding(
                "ENVIRONMENT_PREDICATE_UNRESOLVED",
                SEVERITY_WARNING,
                f"{len(unresolved)} predicate(s)",
                "a predicate could not be evaluated against the current environment",
                "evaluation fails open: nothing was invalidated, but nothing was confirmed either",
            )
        )
    return result


def _evaluate(ledger: state.Ledger, now: Mapping[str, Any]) -> tuple[list[dict], list[dict]]:
    invalidated: list[dict] = []
    unresolved: list[dict] = []
    for evidence_id, record in sorted(ledger.records.items()):
        texts = [str(text) for text in record.get("invalidated_if") or []]
        if not texts:
            continue
        then = _then_fingerprint(record)
        for text in texts:
            try:
                parsed = predicate.parse(text)
            except PredicateSyntaxError as exc:
                unresolved.append(_entry(evidence_id, text, f"malformed predicate: {exc}"))
                continue
            evaluation = predicate.evaluate(parsed, now=now, then=then)
            if evaluation.verdict == predicate.VERDICT_INVALIDATED:
                invalidated.append(_entry(evidence_id, text, evaluation.reason))
            elif evaluation.verdict == predicate.VERDICT_UNRESOLVED:
                unresolved.append(_entry(evidence_id, text, evaluation.reason))
    return _sorted(invalidated), _sorted(unresolved)


def _entry(evidence_id: str, text: str, reason: str) -> dict[str, Any]:
    return {"evidence": evidence_id, "predicate": text, "reason": reason}


def _sorted(entries: list[dict]) -> list[dict]:
    return sorted(entries, key=lambda entry: (entry["evidence"], entry["predicate"]))


def _affected_findings(ledger: state.Ledger, invalidated: list[dict]) -> list[dict]:
    stale = {str(entry["evidence"]) for entry in invalidated}
    affected: list[dict] = []
    for finding in sorted(ledger.findings_entries, key=lambda entry: str(entry.get("id"))):
        cited = [str(ev) for ev in finding.get("evidence") or []]
        hit = sorted(set(cited) & stale)
        if not hit:
            continue
        affected.append(
            {
                "id": finding.get("id"),
                "status": finding.get("status"),
                "invalidated_evidence": hit,
                "all_supporting_evidence_invalidated": bool(cited)
                and all(ev in stale for ev in cited),
                "recommended_action": REVIEW_ACTION,
            }
        )
    return affected


def _recommended_anchors(
    block: Mapping[str, Any],
    ledger: state.Ledger,
    invalidated: list[dict],
    unresolved: list[dict],
) -> list[str]:
    """Anchors are the few records worth re-running after a change — but only when their
    own validity is actually in question; an anchor that still holds needs no re-run."""
    questionable = {str(e["evidence"]) for e in invalidated} | {
        str(e["evidence"]) for e in unresolved
    }
    declared = {str(ev) for ev in (block.get("comparability") or {}).get("anchor_evidence") or []}
    declared |= {
        evidence_id
        for evidence_id, record in ledger.records.items()
        if record.get("anchor") is True
    }
    return sorted(declared & questionable)


def _comparability(change: Mapping[str, Any], block: Mapping[str, Any]) -> str | None:
    """The comparability after the change: what the change declares, else what stands."""
    status = change.get("comparability")
    if status is None:
        return (block.get("comparability") or {}).get("status")
    if status not in COMPARABILITY:
        raise StateInvalid(
            [
                Finding(
                    "ENV_COMPARABILITY_INVALID",
                    SEVERITY_ERROR,
                    str(status),
                    f"comparability must be one of {', '.join(COMPARABILITY)}",
                )
            ]
        )
    return str(status)


def _merge(
    block: Mapping[str, Any],
    change: Mapping[str, Any],
    changes: Mapping[str, Any],
    status: str | None,
    evidence_id: str,
) -> dict[str, Any]:
    updated = json.loads(json.dumps(block, ensure_ascii=False))
    comparability = updated.setdefault("comparability", {})
    comparability["fingerprint"] = _fingerprint(updated, changes)
    comparability["last_material_change"] = _now()
    if status is not None:
        comparability["status"] = status
    updated.setdefault("history", []).append(
        _history_entry(change, changes, evidence_id, comparability)
    )
    return updated


def _history_entry(
    change: Mapping[str, Any],
    changes: Mapping[str, Any],
    evidence_id: str | None,
    comparability: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "type": "environment_change",
        "at": comparability.get("last_material_change"),
        "capability": change.get("capability"),
        "changes": dict(changes),
        "comparability": comparability.get("status"),
        "fingerprint": comparability.get("fingerprint"),
        "evidence_id": evidence_id,
        "notes": change.get("notes"),
    }


def _evidence_document(
    paths: repo.ResearchPaths,
    block: Mapping[str, Any],
    change: Mapping[str, Any],
    changes: Mapping[str, Any],
    status: str | None,
) -> tuple[dict[str, Any], list[Finding]]:
    """An E0 record: a statement about the laboratory, never about a hypothesis."""
    environment: dict[str, Any] = {
        "id": block.get("environment_id") or DEFAULT_ENVIRONMENT_ID,
        "comparability": status,
    }
    inputs: dict[str, Any] = {}
    for key, value in changes.items():
        if key.startswith("inputs."):
            inputs[key[len("inputs.") :]] = value
        elif key.startswith("env."):
            environment[key[len("env.") :]] = value
    environment["fingerprint"] = _fingerprint(block, changes)

    document: dict[str, Any] = {
        "schema_version": "1.0",
        "evidence_id": ids.mint("evidence"),  # provisional; the claimed id replaces it
        "created_at": _now(),
        "experiment_id": None,
        "question": "What changed in the research environment?",
        "subject": {"type": "environment", "id": environment["id"]},
        "evidence_level": "E0",
        "execution_status": "completed",
        "research_outcome": "none",
        "confidence": "certain",
        "observations": _observations(change, changes),
        "measurements": {
            key: value
            for key, value in changes.items()
            if isinstance(value, (str, int, float, bool))
        },
        "environment": environment,
        "inputs": inputs,
        "code_state": jgit.code_state(paths.root).to_dict(),
        "invalidated_if": [],
    }
    document["counts_as_evidence_iteration"] = constraints.derive_counts_as_evidence_iteration(
        document
    )
    findings = [
        *schema.load_validator("evidence").check(document),
        *constraints.check_evidence(document),
    ]
    errors = [f for f in findings if f.severity == SEVERITY_ERROR]
    if errors:
        raise StateInvalid(errors)
    return document, [f for f in findings if f.severity != SEVERITY_ERROR]


def _observations(change: Mapping[str, Any], changes: Mapping[str, Any]) -> list[str]:
    observations = [
        f"{key} is now {json.dumps(value, ensure_ascii=False)}" for key, value in changes.items()
    ]
    if change.get("capability"):
        observations.insert(0, str(change["capability"]))
    if change.get("notes"):
        observations.append(str(change["notes"]))
    return observations


def _change_map(change: Mapping[str, Any]) -> dict[str, Any]:
    raw = change.get("changes")
    if not isinstance(raw, Mapping) or not raw:
        raise StateInvalid(
            [
                Finding(
                    "ENV_CHANGE_EMPTY",
                    SEVERITY_ERROR,
                    "changes",
                    "the change document has no non-empty 'changes' object",
                    'for example {"changes": {"sim_physics_hz": 60}}',
                )
            ]
        )
    normalized: dict[str, Any] = {}
    for key, value in raw.items():
        text = str(key)
        namespace = text.split(".", 1)[0]
        normalized[text if namespace in NAMESPACES else f"env.{text}"] = value
    return normalized


def _now_fingerprint(
    paths: repo.ResearchPaths, block: Mapping[str, Any], changes: Mapping[str, Any]
) -> dict[str, Any]:
    now: dict[str, Any] = {}
    now.update(model.flatten("env", block))
    now.update(changes)
    now.update(model.flatten("code", jgit.code_state(paths.root).to_dict()))
    return now


def _then_fingerprint(record: Mapping[str, Any]) -> dict[str, Any]:
    """What the record itself recorded — the state the evidence was produced in."""
    then: dict[str, Any] = {}
    for prefix, key in (("env", "environment"), ("inputs", "inputs"), ("code", "code_state")):
        value = record.get(key)
        if isinstance(value, Mapping):
            then.update(model.flatten(prefix, value))
    return then


def _fingerprint(block: Mapping[str, Any], changes: Mapping[str, Any]) -> str:
    """A chained digest, so a change is identifiable and its history is an ordered chain."""
    previous = (block.get("comparability") or {}).get("fingerprint")
    payload = json.dumps(
        {"previous": previous, "changes": dict(changes)}, sort_keys=True, ensure_ascii=False
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_environment(paths: repo.ResearchPaths) -> str:
    try:
        return paths.environment.read_text(encoding="utf-8")
    except OSError as exc:
        raise PreconditionMissing(
            "ENVIRONMENT_UNREADABLE", f"cannot read {paths.environment}: {exc}"
        ) from exc


def _read_change(location: str) -> dict[str, Any]:
    try:
        raw = Path(location).read_text(encoding="utf-8")
    except OSError as exc:
        raise PreconditionMissing(
            "ENV_CHANGE_UNREADABLE", f"cannot read {location}: {exc}"
        ) from exc
    try:
        change = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StateInvalid(
            [
                Finding(
                    "ENV_CHANGE_MALFORMED",
                    SEVERITY_ERROR,
                    location,
                    f"line {exc.lineno} column {exc.colno}: {exc.msg}",
                )
            ]
        ) from exc
    if not isinstance(change, dict):
        raise StateInvalid(
            [
                Finding(
                    "ENV_CHANGE_NOT_OBJECT", SEVERITY_ERROR, location, "top level is not an object"
                )
            ]
        )
    return change


def _require_writable_block(block: Mapping[str, Any], path: Path) -> None:
    """ENVIRONMENT.md is not one of the four versioned JSON kinds, so its guard is local.

    The same asymmetry applies: a block written by a newer tool may be read, but never
    overwritten by one that does not understand its fields.
    """
    version = block.get("schema_version")
    if version != SUPPORTED_BLOCK_VERSION:
        raise RefusedByPolicy(
            "ENVIRONMENT_SCHEMA_UNSUPPORTED",
            f"{path} declares schema_version {version!r}; this tool writes {SUPPORTED_BLOCK_VERSION}",
            "upgrade the tool, or move the file aside deliberately — this tool will not "
            "guess at a block format it does not understand",
        )


def _human(payload: dict[str, Any]) -> str:
    counts = payload["counts"]
    return (
        f"invalidated {counts['invalidated']}, unresolved {counts['unresolved']}, "
        f"affected findings {counts['affected_findings']}, anchors {counts['recommended_anchors']}"
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
