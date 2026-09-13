"""Locating a research repository, and naming the files inside it.

Discovery walks upward from the working directory looking for `research/ACTIVE.json`,
the way Git looks for `.git`. That makes every subcommand work from anywhere in the
tree without a `--root` flag, while `--root` remains available for scripts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from researchlog.errors import Finding, PreconditionMissing, SEVERITY_ERROR

RESEARCH_DIR = "research"
ACTIVE_NAME = "ACTIVE.json"
LEDGER_DIR = "ledger"
RUNS_DIR = "runs"
DERIVED_DIR = ".derived"

CANONICAL_MARKDOWN: tuple[str, ...] = (
    "CURRENT.md",
    "ARCHITECT.md",
    "BOUNDARIES.md",
    "ENVIRONMENT.md",
    "FINDINGS.md",
)


@dataclass(frozen=True, slots=True)
class ResearchPaths:
    root: Path
    research: Path
    active: Path
    current: Path
    architect: Path
    boundaries: Path
    environment: Path
    findings: Path
    ledger: Path
    runs: Path
    status: Path
    derived: Path

    def manifest(self, experiment_id: str) -> Path:
        return self.runs / experiment_id / "manifest.json"

    def result(self, experiment_id: str) -> Path:
        return self.runs / experiment_id / "result.json"

    def stdout(self, experiment_id: str) -> Path:
        return self.runs / experiment_id / "stdout.log"

    def stderr(self, experiment_id: str) -> Path:
        return self.runs / experiment_id / "stderr.log"

    def evidence(self, evidence_id: str) -> Path:
        return self.ledger / f"{evidence_id}.json"

    def markdown(self, name: str) -> Path:
        return self.research / name

    def as_dict(self) -> dict[str, str]:
        return {
            "root": str(self.root),
            "research": str(self.research),
        }


def templates_dir() -> Path:
    """The skeleton `init` copies. Kept as real files, not strings in Python."""
    return Path(__file__).resolve().parents[2] / "templates" / "research"


def build(root: Path) -> ResearchPaths:
    research = root / RESEARCH_DIR
    return ResearchPaths(
        root=root,
        research=research,
        active=research / ACTIVE_NAME,
        current=research / "CURRENT.md",
        architect=research / "ARCHITECT.md",
        boundaries=research / "BOUNDARIES.md",
        environment=research / "ENVIRONMENT.md",
        findings=research / "FINDINGS.md",
        ledger=research / LEDGER_DIR,
        runs=research / RUNS_DIR,
        status=research / "STATUS.md",
        derived=research / DERIVED_DIR,
    )


def discover(start: Path | None = None) -> ResearchPaths | None:
    """Walk up from `start` looking for a research state root. None if there is none."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / RESEARCH_DIR / ACTIVE_NAME).is_file():
            return build(candidate)
    return None


def require(start: Path | None = None) -> ResearchPaths:
    """Like discover, but explains what to do when there is no state yet."""
    found = discover(start)
    if found is None:
        raise PreconditionMissing(
            "RESEARCH_STATE_ABSENT",
            f"no {RESEARCH_DIR}/{ACTIVE_NAME} found in this directory or any parent",
            "run `researchlog init` to create the skeleton, or pass --root for a different tree",
        )
    return found


def initialize_dirs(paths: ResearchPaths) -> None:
    """Create the directories the skeleton needs. Never touches existing content."""
    try:
        paths.ledger.mkdir(parents=True, exist_ok=True)
        paths.runs.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PreconditionMissing(
            "RESEARCH_DIRS_UNCREATABLE", f"cannot create the research directories: {exc}"
        ) from exc


def missing_canonical(paths: ResearchPaths) -> list[Finding]:
    """Report which canonical files are absent, without failing."""
    findings: list[Finding] = []
    for name in (ACTIVE_NAME, *CANONICAL_MARKDOWN):
        if not paths.markdown(name).is_file():
            findings.append(
                Finding("CANONICAL_FILE_MISSING", SEVERITY_ERROR, name, "canonical file is absent")
            )
    return findings
