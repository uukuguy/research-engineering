"""The invariant layer: everything the schema cannot express structurally.

The schema checks shapes. This module checks meanings — the rules that decide whether a
record is *coherent*, not merely well-formed. Three of them carry most of the weight:

**Execution status and research outcome are separate axes.** An OOM, a missing SDK, or a
killed session must never enter FINDINGS as "the mechanism does not work". Only
`SCIENTIFIC_NEGATIVE` may weaken a hypothesis, and here that is a hard error rather than
a request.

**An evidence iteration is counted, not claimed.** `counts_as_evidence_iteration` is
derived by the tool from fields the caller supplies. The caller's own value is rejected
if it disagrees, so a block contract cannot be extended by assertion.

**A surrogate must declare what it cannot support.** When evidence falls short of the
level the question needed, the contract becomes mandatory, and an `EVIDENCE_INVALID`
surrogate may not be used to confirm or refute anything.

This is an auditable mechanism, not an anti-cheat mechanism. It makes misreporting
visible; it cannot make it impossible, and the documentation should not pretend
otherwise.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from researchlog.errors import SEVERITY_ERROR, SEVERITY_WARNING, Finding, PredicateSyntaxError
from researchlog.predicate import parse

EVIDENCE_LEVELS: tuple[str, ...] = ("E0", "E1", "E2", "E3", "E4", "E5")

# Execution statuses that carry no scientific content. None of them may be paired with
# a claim about a hypothesis.
NON_SCIENTIFIC_EXECUTION: frozenset[str] = frozenset(
    {"interrupted", "infra_failed", "env_blocked", "env_unsupported", "resource_exceeded", "invalid"}
)

# Only these outcomes describe something learned. `failed` and `none` do not.
COUNTED_OUTCOMES: frozenset[str] = frozenset(
    {"confirmed", "refuted", "inconclusive", "informative_failure", "promising"}
)

# Outcomes that assert something about a hypothesis.
ASSERTIVE_OUTCOMES: frozenset[str] = frozenset({"confirmed", "refuted"})

BELIEF_DELTAS: frozenset[str] = frozenset({"none", "refined", "overturned"})

FINDING_STATUSES_REQUIRING_REPLACEMENT: frozenset[str] = frozenset({"Superseded"})

# Signal types whose exact wording carries scope, so the original must survive verbatim.
# A boundary is a statement about the world as the architect phrased it: normalising
# "do not touch the planner's recovery branch" into "do not modify the navigation
# planner" is not a translation, it is a quiet widening of what is forbidden. The
# English rendering belongs in `statement`; both are kept. `DECISION FINAL` is listed
# separately because ARCHITECT.md's table names it as its own type.
SIGNAL_TYPES_REQUIRING_SOURCE_TEXT: frozenset[str] = frozenset(
    {"CONSTRAINT", "DECISION", "DECISION FINAL", "VETO"}
)


def evidence_level_rank(level: Any) -> int:
    return EVIDENCE_LEVELS.index(level) if level in EVIDENCE_LEVELS else -1


def derive_counts_as_evidence_iteration(record: Mapping[str, Any]) -> bool:
    """The single definition of a belief-changing iteration.

    The block contract and every throughput KPI are driven by this, so it is computed
    here and nowhere else.
    """
    if record.get("execution_status") != "completed":
        return False
    if record.get("research_outcome") not in COUNTED_OUTCOMES:
        return False
    differentiated = record.get("hypotheses_differentiated") or []
    return bool(differentiated) or record.get("belief_delta", "none") != "none"


def check_evidence(
    record: Mapping[str, Any],
    *,
    declared_count: Any = None,
    known_hypotheses: Sequence[str] | None = None,
    allowed_hypotheses: Sequence[str] | None = None,
) -> list[Finding]:
    """Coherence checks for one evidence record."""
    findings: list[Finding] = []
    identifier = str(record.get("evidence_id", "?"))

    findings.extend(_check_execution_vs_outcome(record, identifier))
    findings.extend(_check_surrogate(record, identifier))
    findings.extend(_check_counts(record, identifier, declared_count))
    findings.extend(_check_hypotheses(record, identifier, known_hypotheses, allowed_hypotheses))
    findings.extend(_check_predicates(record, identifier))
    return findings


def check_finding(entry: Mapping[str, Any], *, evidence_levels: Mapping[str, str]) -> list[Finding]:
    """Coherence checks for one FINDINGS entry. `evidence_levels` maps EV id to level."""
    findings: list[Finding] = []
    identifier = str(entry.get("id", "?"))
    cited = list(entry.get("evidence") or [])
    status = entry.get("status")

    missing = [ev for ev in cited if ev not in evidence_levels]
    if missing:
        findings.append(
            Finding(
                "DANGLING_FINDING_REF",
                SEVERITY_WARNING,
                identifier,
                f"cites evidence that does not exist: {', '.join(sorted(missing))}",
            )
        )

    if status == "Established" and not cited:
        findings.append(
            Finding(
                "FINDING_ESTABLISHED_WITHOUT_EVIDENCE",
                SEVERITY_ERROR,
                identifier,
                "an Established finding must cite at least one evidence record",
            )
        )

    highest = _highest_level(cited, evidence_levels)
    declared = entry.get("max_evidence_level")
    if highest is not None and declared is not None and declared != highest:
        findings.append(
            Finding(
                "FINDING_LEVEL_MISMATCH",
                SEVERITY_ERROR,
                identifier,
                f"declares max_evidence_level {declared} but its evidence reaches {highest}",
                f"the field is derived; set it to {highest} or drop it and let the tool fill it",
            )
        )

    if status in FINDING_STATUSES_REQUIRING_REPLACEMENT:
        if not entry.get("superseded_by"):
            findings.append(
                Finding(
                    "FINDING_SUPERSEDED_WITHOUT_REPLACEMENT",
                    SEVERITY_ERROR,
                    identifier,
                    "a Superseded finding must name superseded_by",
                )
            )
        if not entry.get("reason"):
            findings.append(
                Finding(
                    "FINDING_SUPERSEDED_WITHOUT_REASON",
                    SEVERITY_ERROR,
                    identifier,
                    "a Superseded finding must record why it was replaced",
                )
            )
    return findings


def highest_level(cited: Sequence[str], evidence_levels: Mapping[str, str]) -> str | None:
    """Public form of the level derivation, used when writing a finding."""
    return _highest_level(cited, evidence_levels)


def check_block_contract(
    block: Mapping[str, Any],
    *,
    member_records: Sequence[Mapping[str, Any]],
) -> list[Finding]:
    """A block's own summary must agree with the evidence it contains."""
    findings: list[Finding] = []
    counted = sum(1 for record in member_records if derive_counts_as_evidence_iteration(record))
    declared = block.get("completed_evidence_iterations")
    if isinstance(declared, int) and declared != counted:
        findings.append(
            Finding(
                "EVIDENCE_ITERATION_COUNT_DRIFT",
                SEVERITY_ERROR,
                str(block.get("id", "?")),
                f"block claims {declared} evidence iterations, its evidence shows {counted}",
                "the count is derived from the ledger; do not maintain it by hand",
            )
        )

    block_delta = block.get("belief_delta")
    if block_delta not in BELIEF_DELTAS and block_delta is not None:
        findings.append(
            Finding(
                "BLOCK_BELIEF_DELTA_INVALID",
                SEVERITY_ERROR,
                str(block.get("id", "?")),
                f"belief_delta must be null, none, refined or overturned; got {block_delta!r}",
            )
        )
    elif block_delta == "none" and any(
        record.get("belief_delta", "none") != "none" for record in member_records
    ):
        findings.append(
            Finding(
                "BLOCK_BELIEF_DELTA_INCONSISTENT",
                SEVERITY_ERROR,
                str(block.get("id", "?")),
                "block closes as belief_delta 'none' but one of its evidence records changed belief",
            )
        )
    return findings


def check_signal(signal: Mapping[str, Any]) -> list[Finding]:
    """Coherence checks for one `research:signal` block in ARCHITECT.md.

    Signals carry no schema — they are independent blocks in a human-readable file, not a
    versioned document — so the rules they must satisfy live here with the other meanings
    the schema cannot express.
    """
    signal_type = str(signal.get("type") or "").strip().upper()
    if signal_type not in SIGNAL_TYPES_REQUIRING_SOURCE_TEXT:
        return []

    source_text = signal.get("source_text")
    if isinstance(source_text, str) and source_text.strip():
        return []

    return [
        Finding(
            "SIGNAL_SOURCE_TEXT_REQUIRED",
            SEVERITY_ERROR,
            str(signal.get("id") or "?"),
            f"a {signal_type} signal must keep the architect's original wording in source_text",
            "the wording carries the scope, so normalising it changes what was decided; "
            "keep the sentence as written in source_text and put the English rendering in "
            "`statement` — never manufacture a quotation you do not have",
        )
    ]


def _check_execution_vs_outcome(record: Mapping[str, Any], identifier: str) -> list[Finding]:
    status = record.get("execution_status")
    outcome = record.get("research_outcome")
    if status in NON_SCIENTIFIC_EXECUTION and outcome in ASSERTIVE_OUTCOMES:
        return [
            Finding(
                "NON_SCIENTIFIC_REFUTATION",
                SEVERITY_ERROR,
                identifier,
                f"execution_status {status!r} cannot support research_outcome {outcome!r}",
                "an environment or infrastructure failure is not evidence about a hypothesis; "
                "use 'inconclusive' or 'none' and record the limitation instead",
            )
        ]
    return []


def _check_surrogate(record: Mapping[str, Any], identifier: str) -> list[Finding]:
    findings: list[Finding] = []
    contract = record.get("surrogate_contract")
    needed = _surrogate_required(record)

    if needed and not contract:
        findings.append(
            Finding(
                "SURROGATE_CONTRACT_REQUIRED",
                SEVERITY_ERROR,
                identifier,
                "evidence below the required level, or flagged as a surrogate, must carry a "
                "surrogate_contract",
                "record target_causal_claim, required/preserved/missing features, and the "
                "conclusions this evidence may and may not support",
            )
        )
        return findings

    if contract and isinstance(contract, Mapping):
        missing = [
            key
            for key in (
                "target_causal_claim",
                "required_causal_features",
                "preserved_features",
                "missing_or_distorted_features",
                "allowed_conclusions",
                "forbidden_conclusions",
                "verdict",
            )
            if not contract.get(key) and contract.get(key) != []
        ]
        if missing:
            findings.append(
                Finding(
                    "SURROGATE_CONTRACT_INCOMPLETE",
                    SEVERITY_ERROR,
                    identifier,
                    f"surrogate_contract is missing: {', '.join(missing)}",
                )
            )
        if contract.get("verdict") == "EVIDENCE_INVALID" and record.get("research_outcome") in ASSERTIVE_OUTCOMES:
            findings.append(
                Finding(
                    "INVALID_SURROGATE_ASSERTS_CONCLUSION",
                    SEVERITY_ERROR,
                    identifier,
                    "a surrogate declared EVIDENCE_INVALID cannot confirm or refute a hypothesis",
                    "downgrade research_outcome to 'inconclusive'",
                )
            )
    return findings


def _surrogate_required(record: Mapping[str, Any]) -> bool:
    if record.get("surrogate") is True:
        return True
    target = record.get("target_evidence_level")
    if target is None:
        return False
    return evidence_level_rank(record.get("evidence_level")) < evidence_level_rank(target)


def _check_counts(record: Mapping[str, Any], identifier: str, declared: Any) -> list[Finding]:
    actual = derive_counts_as_evidence_iteration(record)
    stored = record.get("counts_as_evidence_iteration")
    for label, value in (("stored", stored), ("supplied", declared)):
        if value is not None and bool(value) != actual:
            return [
                Finding(
                    "EVIDENCE_ITERATION_COUNT_FALSE",
                    SEVERITY_ERROR,
                    identifier,
                    f"{label} counts_as_evidence_iteration={value!r} but the fields derive {actual!r}",
                    "this field is computed from execution_status, research_outcome, "
                    "hypotheses_differentiated and belief_delta; do not set it by hand",
                )
            ]
    return []


def _check_hypotheses(
    record: Mapping[str, Any],
    identifier: str,
    known: Sequence[str] | None,
    allowed: Sequence[str] | None,
) -> list[Finding]:
    findings: list[Finding] = []
    referenced = set(record.get("hypothesis_ids") or []) | set(record.get("hypotheses_differentiated") or [])

    if known is not None and referenced:
        unknown = sorted(referenced - set(known))
        if unknown:
            findings.append(
                Finding(
                    "UNKNOWN_HYPOTHESIS",
                    SEVERITY_ERROR,
                    identifier,
                    f"references hypotheses that do not exist: {', '.join(unknown)}",
                )
            )

    if allowed is not None:
        outside = sorted(set(record.get("hypotheses_differentiated") or []) - set(allowed))
        if outside:
            findings.append(
                Finding(
                    "HYPOTHESIS_OUTSIDE_BLOCK",
                    SEVERITY_WARNING,
                    identifier,
                    f"differentiates hypotheses the block does not cover: {', '.join(outside)}",
                )
            )
    return findings


def _check_predicates(record: Mapping[str, Any], identifier: str) -> list[Finding]:
    findings: list[Finding] = []
    for text in record.get("invalidated_if") or []:
        try:
            parse(text)
        except PredicateSyntaxError as exc:
            findings.append(
                Finding(
                    "PREDICATE_SYNTAX",
                    SEVERITY_ERROR,
                    identifier,
                    f"invalidated_if entry {text!r} is malformed: {exc}",
                )
            )
    return findings


def _highest_level(cited: Sequence[str], evidence_levels: Mapping[str, str]) -> str | None:
    ranks = [evidence_level_rank(evidence_levels[ev]) for ev in cited if ev in evidence_levels]
    ranks = [rank for rank in ranks if rank >= 0]
    return EVIDENCE_LEVELS[max(ranks)] if ranks else None
