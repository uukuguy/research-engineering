"""The `invalidated_if` mini-language.

An evidence record declares what must stay true for it to remain valid:

    "invalidated_if": [
      "env.sim_physics_hz != 30",
      "inputs.replay_suite changed",
      "evaluator.version != eval-v3"
    ]

This turns environment comparability from a judgement call into a lookup. When the
environment changes, the affected evidence is whatever said it depended on the thing
that changed — no reasoning required, and no chance of a plausible-sounding excuse.

The language is deliberately tiny. There is no general expression engine, no `and`, no
`or`, no parentheses, and no negation of a compound. A list of predicates is a
conjunction; if you need a disjunction, that is two evidence records, and that is
usually the more honest modelling anyway.

Evaluation fails **open**: an unresolvable predicate does not invalidate the evidence,
it raises `UNRESOLVED` for a human to look at. Quietly treating "could not check" as
"still valid" would hide real staleness, and treating it as "invalid" would cry wolf
until people stopped reading the output.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from researchlog.errors import PredicateSyntaxError

NAMESPACES: Final = ("env", "inputs", "code")
OPERATORS: Final = ("==", "!=", "<", "<=", ">", ">=", "in", "not_in")

VERDICT_VALID = "VALID"
VERDICT_INVALIDATED = "INVALIDATED"
VERDICT_UNRESOLVED = "UNRESOLVED"

_CHANGED_SUFFIX = " changed"


@dataclass(frozen=True, slots=True)
class Predicate:
    text: str
    path: str
    op: str | None  # None means the unary `changed`
    literal: Any = None


@dataclass(frozen=True, slots=True)
class Evaluation:
    verdict: str
    reason: str = ""

    @property
    def invalidates(self) -> bool:
        return self.verdict == VERDICT_INVALIDATED


def parse(text: str) -> Predicate:
    """Parse one predicate. Raises PredicateSyntaxError with a usable message."""
    if not isinstance(text, str) or not text.strip():
        raise PredicateSyntaxError(f"predicate must be a non-empty string, got {text!r}")
    stripped = text.strip()
    namespace, dot, rest = stripped.partition(".")
    if not dot:
        raise PredicateSyntaxError(
            f"{stripped!r} has no namespace; expected one of {', '.join(NAMESPACES)} followed by '.'"
        )
    if namespace not in NAMESPACES:
        raise PredicateSyntaxError(
            f"unknown namespace {namespace!r} in {stripped!r}; expected one of {', '.join(NAMESPACES)}"
        )
    if not rest:
        raise PredicateSyntaxError(f"{stripped!r} names a namespace but no key")

    for op in OPERATORS:
        head, separator, tail = rest.partition(f" {op} ")
        if separator:
            if not head:
                raise PredicateSyntaxError(f"{stripped!r} has no path before {op!r}")
            return Predicate(stripped, f"{namespace}.{head}", op, _literal(tail, stripped))

    if rest.endswith(_CHANGED_SUFFIX):
        key = rest[: -len(_CHANGED_SUFFIX)].strip()
        if not key:
            raise PredicateSyntaxError(f"{stripped!r} has no path before 'changed'")
        return Predicate(stripped, f"{namespace}.{key}", None)

    raise PredicateSyntaxError(
        f"no operator in {stripped!r}; expected one of {', '.join(OPERATORS)}, or a trailing 'changed'"
    )


def evaluate(predicate: Predicate, *, now: Mapping[str, Any], then: Mapping[str, Any]) -> Evaluation:
    """Pure. `now` and `then` are flat dotted-key maps of current and recorded state.

    A predicate that is true means the evidence no longer holds.
    """
    if predicate.path not in now:
        return Evaluation(VERDICT_UNRESOLVED, f"{predicate.path} is absent from the current fingerprint")

    if predicate.op is None:
        if predicate.path not in then:
            return Evaluation(VERDICT_UNRESOLVED, f"{predicate.path} was never recorded")
        if _equal(now[predicate.path], then[predicate.path]):
            return Evaluation(VERDICT_VALID)
        return Evaluation(
            VERDICT_INVALIDATED,
            f"{predicate.path} changed from {then[predicate.path]!r} to {now[predicate.path]!r}",
        )

    current = now[predicate.path]

    if predicate.op in ("in", "not_in"):
        if not isinstance(predicate.literal, (list, tuple, set, str)):
            return Evaluation(
                VERDICT_UNRESOLVED,
                f"'{predicate.op}' needs a list or string on the right, got {predicate.literal!r}",
            )
        member = _contains(predicate.literal, current)
        fired = member if predicate.op == "in" else not member
        return _verdict(fired, predicate, current)

    fired = _compare(predicate.op, current, predicate.literal)
    if fired is None:
        return Evaluation(
            VERDICT_UNRESOLVED,
            f"{predicate.path}={current!r} is not comparable with {predicate.literal!r}",
        )
    return _verdict(fired, predicate, current)


def _verdict(fired: bool, predicate: Predicate, current: Any) -> Evaluation:
    if fired:
        return Evaluation(
            VERDICT_INVALIDATED, f"{predicate.path} {predicate.op or 'changed'} {predicate.literal!r} holds"
        )
    return Evaluation(VERDICT_VALID)


def _compare(op: str, left: Any, right: Any) -> bool | None:
    """Compare two scalars, numerically when both sides look numeric.

    Returns None when the two sides cannot be compared at all, which the caller turns
    into UNRESOLVED rather than guessing.
    """
    left_number = _as_number(left)
    right_number = _as_number(right)
    if left_number is not None and right_number is not None:
        left, right = left_number, right_number
    elif isinstance(left, (list, Mapping)) or isinstance(right, (list, Mapping)):
        return None

    if op == "==":
        return bool(left == right)
    if op == "!=":
        return bool(left != right)
    try:
        return bool({"<": left < right, "<=": left <= right, ">": left > right, ">=": left >= right}[op])
    except TypeError:
        return None


def evaluate_all(
    predicates: list[str],
    *,
    now: Mapping[str, Any],
    then: Mapping[str, Any] | None = None,
) -> list[Evaluation]:
    """Evaluate a list in order. Parse errors propagate; they are authoring mistakes."""
    context = then if then is not None else now
    return [evaluate(parse(text), now=now, then=context) for text in predicates]


def invalidated(predicates: list[str], *, now: Mapping[str, Any], then: Mapping[str, Any] | None = None) -> bool:
    return any(result.invalidates for result in evaluate_all(predicates, now=now, then=then))


def _literal(text: str, whole: str) -> Any:
    stripped = text.strip()
    if not stripped:
        raise PredicateSyntaxError(f"{whole!r} has an operator but no right-hand value")
    if stripped.startswith("["):
        if not stripped.endswith("]"):
            raise PredicateSyntaxError(f"unterminated list in {whole!r}")
        inner = stripped[1:-1].strip()
        if not inner:
            return []
        return [_literal(part, whole) for part in _split_top_level(inner)]
    if stripped.startswith('"') or stripped in ("true", "false", "null"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise PredicateSyntaxError(f"malformed literal in {whole!r}: {exc.msg}") from exc
    if _looks_compound(stripped):
        raise PredicateSyntaxError(
            f"{whole!r} looks like a compound condition; this language has no and/or. "
            f"A list of predicates is already a conjunction — write two entries instead."
        )
    if " " in stripped:
        raise PredicateSyntaxError(
            f"{whole!r} has an unquoted value containing spaces; wrap it in double quotes"
        )
    number = _as_number(stripped)
    if number is not None:
        return int(number) if float(number).is_integer() else number
    return stripped


def _looks_compound(text: str) -> bool:
    padded = f" {text} "
    return " and " in padded or " or " in padded or text.startswith("(")


def _split_top_level(text: str) -> list[str]:
    """Split a bracketed list on commas that are not inside a quoted string."""
    parts: list[str] = []
    current: list[str] = []
    in_quotes = False
    for char in text:
        if char == '"':
            in_quotes = not in_quotes
            current.append(char)
        elif char == "," and not in_quotes:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    parts.append("".join(current).strip())
    return [part for part in parts if part]


def _as_number(value: Any) -> float | None:
    """Numeric view of a value, so a probe writing "30" still matches an author's 30."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _equal(left: Any, right: Any) -> bool:
    result = _compare("==", left, right)
    return (left == right) if result is None else result


def _contains(container: Any, member: Any) -> bool:
    if isinstance(container, (list, tuple, set)):
        return any(_equal(member, item) for item in container)
    if isinstance(container, str):
        return str(member) in container
    return False
