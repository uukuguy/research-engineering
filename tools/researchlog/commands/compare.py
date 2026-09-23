"""`researchlog compare` — what two evidence records share, and whether the delta is attributable.

A measurement delta between two runs means nothing until you know whether anything *else*
moved. This command answers that mechanically, and it is deliberately allowed to say no:

* `COMPARABLE` — same environment fingerprint, same working-tree delta. A difference in
  the measurements is about the thing that changed.
* `REBASELINE_REQUIRED` — the environments differ. Re-run the anchors before comparing.
* `ATTRIBUTION_FORBIDDEN` — inputs moved together with the code, so a delta cannot be
  assigned to either. This is the verdict that stops "we changed four things and the
  number went up" from becoming a finding.

Only `COMPARABLE` exits 0. The other two exit 3, because "we cannot attribute this" is a
result that needs handling, not a command that failed.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

from researchlog import ioutil, model, repo
from researchlog.errors import (
    EXIT_FINDINGS_PRESENT,
    Finding,
    PreconditionMissing,
    Result,
    SEVERITY_INFO,
    SEVERITY_WARNING,
)

NAME = "compare"
HELP = "compare two evidence records: common measurements, artifact delta, attribution"

FIELDS: tuple[str, ...] = ("measurements", "artifacts", "environment", "all")
DEFAULT_KEY_INPUTS = "model,dataset,evaluator,replay_suite"

COMPARABLE = "COMPARABLE"
REBASELINE_REQUIRED = "REBASELINE_REQUIRED"
ATTRIBUTION_FORBIDDEN = "ATTRIBUTION_FORBIDDEN"


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("records", nargs=2, metavar="EV-ID")
    parser.add_argument("--field", choices=FIELDS, default="all")
    parser.add_argument(
        "--key-inputs",
        default=DEFAULT_KEY_INPUTS,
        help="inputs whose movement alone forbids attribution (comma separated)",
    )


def run(args: argparse.Namespace) -> Result:
    paths = repo.require(args.root)
    first = _load(paths, args.records[0])
    second = _load(paths, args.records[1])
    key_inputs = {part.strip() for part in args.key_inputs.split(",") if part.strip()}

    environment = _environment(first, second)
    verdict, reasons = _verdict(first, second, environment["differing_keys"], key_inputs)

    payload: dict[str, Any] = {
        "records": list(args.records),
        "attribute_verdict": verdict,
        "reasons": reasons,
    }
    if args.field in ("measurements", "all"):
        payload["common_measurements"] = _common_measurements(first, second)
    if args.field in ("artifacts", "all"):
        payload["artifact_delta"] = _artifact_delta(first, second)
    if args.field in ("environment", "all"):
        payload["environment"] = environment

    result = Result(payload=payload, human=_human(args.records, verdict, reasons))
    for finding in _findings(first, second, verdict, reasons):
        result.add(finding)
    if verdict != COMPARABLE:
        result.exit_code = max(result.exit_code, EXIT_FINDINGS_PRESENT)
    return result


def _load(paths: repo.ResearchPaths, evidence_id: str) -> dict[str, Any]:
    # V1 Block 2 / T2: new shards live under `<YYYY-MM>/`. The flat form is
    # still loaded as a fallback so pre-partition shards keep working until
    # they are migrated (or retired). `record` writes only the partition
    # form; `compare` accepts either.
    path = paths.evidence_in_partition(evidence_id)
    if not path.is_file():
        path = paths.evidence(evidence_id)
    if not path.is_file():
        raise PreconditionMissing(
            "EVIDENCE_NOT_FOUND",
            f"no evidence record {evidence_id} at {path}",
            "check the id; compare needs both records present in research/ledger/",
        )
    return ioutil.load_json(path)


def _common_measurements(first: Mapping[str, Any], second: Mapping[str, Any]) -> dict[str, Any]:
    left = first.get("measurements") or {}
    right = second.get("measurements") or {}
    common: dict[str, Any] = {}
    for key in sorted(set(left) & set(right)):
        before, after = left[key], right[key]
        common[key] = {
            "a": before,
            "b": after,
            "delta": _delta(before, after),
            "changed": before != after,
        }
    return common


def _delta(before: Any, after: Any) -> float | int | None:
    if isinstance(before, bool) or isinstance(after, bool):
        return None
    if isinstance(before, (int, float)) and isinstance(after, (int, float)):
        return after - before
    return None


def _artifact_delta(first: Mapping[str, Any], second: Mapping[str, Any]) -> dict[str, list[str]]:
    left = _artifact_index(first)
    right = _artifact_index(second)
    return {
        "added": sorted(set(right) - set(left)),
        "removed": sorted(set(left) - set(right)),
        "changed": sorted(path for path in set(left) & set(right) if left[path] != right[path]),
    }


def _artifact_index(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(entry["path"]): entry.get("sha256")
        for entry in record.get("artifacts") or []
        if isinstance(entry, Mapping) and entry.get("path")
    }


def _environment(first: Mapping[str, Any], second: Mapping[str, Any]) -> dict[str, Any]:
    left = _input_map(first)
    right = _input_map(second)
    keys = sorted(set(left) | set(right))
    return {
        "a": _environment_header(first),
        "b": _environment_header(second),
        "fingerprints_equal": _fingerprint(first) == _fingerprint(second),
        "differing_keys": sorted(
            k for k in keys if k in left and k in right and left[k] != right[k]
        ),
        "only_in_one": sorted(k for k in keys if k not in left or k not in right),
    }


def _environment_header(record: Mapping[str, Any]) -> dict[str, Any]:
    environment = record.get("environment") or {}
    return {
        "id": environment.get("id"),
        "fingerprint": environment.get("fingerprint"),
        "comparability": environment.get("comparability"),
    }


def _input_map(record: Mapping[str, Any]) -> dict[str, Any]:
    """Everything outside the code that could move a number: environment and inputs."""
    flat: dict[str, Any] = {}
    for prefix, key in (("env", "environment"), ("inputs", "inputs")):
        value = record.get(key)
        if isinstance(value, Mapping):
            flat.update(model.flatten(prefix, value))
    return flat


def _fingerprint(record: Mapping[str, Any]) -> Any:
    return (record.get("environment") or {}).get("fingerprint")


def _diff(record: Mapping[str, Any]) -> Any:
    return (record.get("code_state") or {}).get("diff_sha256")


def _verdict(
    first: Mapping[str, Any],
    second: Mapping[str, Any],
    differing: list[str],
    key_inputs: set[str],
) -> tuple[str, list[str]]:
    """Most specific blocking condition first, `COMPARABLE` last.

    The obvious ordering — "equal fingerprint and equal diff means comparable, before
    anything else" — makes `--key-inputs` dead code: an unchanged environment and an
    unchanged working tree are exactly the conditions under which someone changes the
    dataset and reports the number. So the input conflict is checked first, and
    `COMPARABLE` is the verdict only when nothing else moved.
    """
    same_fingerprint = _fingerprint(first) == _fingerprint(second)
    if not same_fingerprint:
        return REBASELINE_REQUIRED, [
            f"environment fingerprints differ ({_fingerprint(first)!r} vs {_fingerprint(second)!r})",
            "re-run the anchor evidence before comparing measurements",
        ]

    conflicts = sorted(key for key in differing if key.rsplit(".", 1)[-1] in key_inputs)
    if conflicts or len(differing) >= 2:
        moved = ", ".join(conflicts or differing)
        return ATTRIBUTION_FORBIDDEN, [
            f"key inputs moved between the two records: {moved}",
            "a delta measured while several inputs moved cannot be assigned to any one of them",
        ]

    left_code = first.get("code_state") or {}
    right_code = second.get("code_state") or {}
    left_tree, right_tree = left_code.get("tree_sha256"), right_code.get("tree_sha256")
    if left_tree and right_tree:
        same_code = left_tree == right_tree
    else:
        # Older evidence has no code-tree hash. Different commits cannot safely
        # be declared equal just because both working trees were clean.
        same_code = left_code.get("commit") == right_code.get("commit")
    if not same_code:
        return ATTRIBUTION_FORBIDDEN, [
            "committed code identities differ (or legacy records cannot establish equality)",
            "use the same executable baseline before attributing the measurement delta",
        ]

    if _diff(first) == _diff(second):
        return COMPARABLE, ["environment, committed code and working-tree delta are identical"]

    return ATTRIBUTION_FORBIDDEN, [
        "the working-tree delta differs between the two records",
        "the code was not the same in both runs, so the delta is not attributable",
    ]


def _findings(
    first: Mapping[str, Any],
    second: Mapping[str, Any],
    verdict: str,
    reasons: list[str],
) -> list[Finding]:
    findings: list[Finding] = []
    subject = f"{first.get('evidence_id')} vs {second.get('evidence_id')}"
    if _fingerprint(first) is None or _fingerprint(second) is None:
        findings.append(
            Finding(
                "COMPARE_FINGERPRINT_ABSENT",
                SEVERITY_INFO,
                subject,
                "at least one record carries no environment fingerprint",
                "an absent fingerprint compares equal to another absent one; record the environment",
            )
        )
    if verdict != COMPARABLE:
        findings.append(
            Finding(
                "COMPARE_NOT_ATTRIBUTABLE",
                SEVERITY_WARNING,
                subject,
                f"{verdict}: {'; '.join(reasons)}",
                "do not promote a conclusion drawn from this comparison",
            )
        )
    return findings


def _human(records: list[str], verdict: str, reasons: list[str]) -> str:
    return f"{records[0]} vs {records[1]}: {verdict}\n" + "\n".join(f"  - {r}" for r in reasons)
