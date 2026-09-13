"""Exit codes, findings, command results, and the exception hierarchy.

The exit-code vocabulary is part of the tool's contract with the agent. An agent
must be able to branch on the code alone, without parsing prose:

    0  OK                    success, nothing pending
    1  TOOL_INTERNAL         unexpected exception (stderr carries the traceback)
    2  STATE_INVALID         schema, reference, or predicate failure; cannot proceed
    3  FINDINGS_PRESENT      completed, but found something that needs handling
    4  REFUSED_BY_POLICY     unknown-newer schema, duplicate expensive run, protected path
    5  PRECONDITION_MISSING  no research/ dir, missing manifest, job liveness unknown
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

EXIT_OK = 0
EXIT_TOOL_INTERNAL = 1
EXIT_STATE_INVALID = 2
EXIT_FINDINGS_PRESENT = 3
EXIT_REFUSED_BY_POLICY = 4
EXIT_PRECONDITION_MISSING = 5

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"


@dataclass(frozen=True, slots=True)
class Finding:
    """A fact the tool noticed. Findings are reported, never acted on."""

    code: str
    severity: str
    subject: str
    message: str
    fix_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "subject": self.subject,
            "message": self.message,
        }
        if self.fix_hint:
            out["fix_hint"] = self.fix_hint
        return out


@dataclass(slots=True)
class Result:
    """What a command returns. The CLI owns all serialization and exit handling."""

    exit_code: int = EXIT_OK
    payload: dict[str, Any] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    human: str = ""

    def add(self, finding: Finding) -> Result:
        """Append a finding, raising the exit code if the finding warrants it."""
        self.findings.append(finding)
        if finding.severity == SEVERITY_ERROR:
            self.exit_code = max(self.exit_code, EXIT_STATE_INVALID)
        elif finding.severity == SEVERITY_WARNING and self.exit_code == EXIT_OK:
            self.exit_code = EXIT_FINDINGS_PRESENT
        return self

    def merge(self, other: Result) -> Result:
        for finding in other.findings:
            self.add(finding)
        self.payload.update(other.payload)
        if other.human:
            self.human = f"{self.human}\n{other.human}".strip()
        return self

    @property
    def has_errors(self) -> bool:
        return any(f.severity == SEVERITY_ERROR for f in self.findings)

    def to_dict(self, *, command: str, schema_versions: dict[str, str], tool_version: str) -> dict[str, Any]:
        return {
            "ok": self.exit_code == EXIT_OK,
            "command": command,
            "exit_code": self.exit_code,
            "payload": self.payload,
            "findings": [f.to_dict() for f in self.findings],
            "schema_versions": schema_versions,
            "tool_version": tool_version,
        }


class ResearchLogError(Exception):
    """Base class. Every subclass carries the exit code it should produce.

    `payload` exists so a failure can still hand back what it managed to establish — a
    `run` that could not start its child has nevertheless created a manifest, and the
    caller needs its identity in order to inspect the logs.
    """

    exit_code: int = EXIT_TOOL_INTERNAL

    def __init__(self, message: str = "", *, payload: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.payload: dict[str, Any] = dict(payload or {})

    def to_result(self) -> Result:
        return Result(exit_code=self.exit_code, payload=dict(self.payload), human=str(self))


class StateInvalid(ResearchLogError):
    """The state on disk cannot be used. Carries findings describing why."""

    exit_code = EXIT_STATE_INVALID

    def __init__(self, findings: list[Finding] | str) -> None:
        self.findings: list[Finding] = (
            [Finding("STATE_INVALID", SEVERITY_ERROR, "-", findings)]
            if isinstance(findings, str)
            else list(findings)
        )
        super().__init__("; ".join(f"{f.code}: {f.message}" for f in self.findings))

    def to_result(self) -> Result:
        result = Result(exit_code=EXIT_STATE_INVALID)
        for finding in self.findings:
            result.add(finding)
        return result


class RefusedByPolicy(ResearchLogError):
    """The tool could do this, but policy says it must not."""

    exit_code = EXIT_REFUSED_BY_POLICY

    def __init__(
        self, code: str, message: str, fix_hint: str = "", *, payload: dict[str, Any] | None = None
    ) -> None:
        self.finding = Finding(code, SEVERITY_ERROR, "-", message, fix_hint)
        super().__init__(f"{code}: {message}", payload=payload)

    def to_result(self) -> Result:
        return Result(
            exit_code=EXIT_REFUSED_BY_POLICY, payload=dict(self.payload), findings=[self.finding]
        )


class PreconditionMissing(ResearchLogError):
    """Something required is not there yet."""

    exit_code = EXIT_PRECONDITION_MISSING

    def __init__(
        self, code: str, message: str, fix_hint: str = "", *, payload: dict[str, Any] | None = None
    ) -> None:
        self.finding = Finding(code, SEVERITY_ERROR, "-", message, fix_hint)
        super().__init__(f"{code}: {message}", payload=payload)

    def to_result(self) -> Result:
        return Result(
            exit_code=EXIT_PRECONDITION_MISSING, payload=dict(self.payload), findings=[self.finding]
        )


class PredicateSyntaxError(StateInvalid):
    """A malformed `invalidated_if` predicate."""

    def __init__(self, message: str) -> None:
        super().__init__([Finding("PREDICATE_SYNTAX", SEVERITY_ERROR, "-", message)])


class IdSpaceExhausted(ResearchLogError):
    exit_code = EXIT_TOOL_INTERNAL

    def __init__(self, message: str) -> None:
        self.finding = Finding("ID_SPACE_EXHAUSTED", SEVERITY_ERROR, "-", message)
        super().__init__(message)

    def to_result(self) -> Result:
        return Result(exit_code=EXIT_TOOL_INTERNAL, findings=[self.finding])


Command = Callable[[Any], Result]
