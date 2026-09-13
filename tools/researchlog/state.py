"""Loading the whole research state, for the commands that need a global view.

`reconcile`, `compare` and `env query` all need the same picture: every evidence
record, the findings that cite them, and the runs that produced them. Reading is
tolerant — a single unreadable shard is reported rather than aborting the scan,
because a tool that refuses to run when the state is damaged is useless exactly when
it is needed most.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from researchlog import ioutil, jgit, repo, schema
from researchlog.errors import SEVERITY_ERROR, SEVERITY_WARNING, Finding, StateInvalid
from researchlog.model import Record


@dataclass(slots=True)
class Ledger:
    records: dict[str, dict[str, Any]] = field(default_factory=dict)
    findings: list[dict[str, Any]] = field(default_factory=list)
    manifests: dict[str, dict[str, Any]] = field(default_factory=dict)
    findings_entries: list[dict[str, Any]] = field(default_factory=list)
    # The `research:findings` block itself. It is the document that carries
    # `schema_version`; the entries inside it do not, which is why the version check
    # belongs here rather than on each entry.
    findings_block: dict[str, Any] | None = None
    unreadable: list[Finding] = field(default_factory=list)

    def evidence_levels(self) -> dict[str, str]:
        return {
            ev_id: str(record.get("evidence_level", ""))
            for ev_id, record in self.records.items()
            if record.get("evidence_level")
        }

    def supporting(self, finding_id: str) -> list[str]:
        for entry in self.findings_entries:
            if entry.get("id") == finding_id:
                return [str(ev) for ev in entry.get("evidence") or []]
        return []

    def for_experiment(self, experiment_id: str) -> list[dict[str, Any]]:
        return [
            record
            for record in self.records.values()
            if record.get("experiment_id") == experiment_id
        ]

    def experiments_referenced(self) -> set[str]:
        return {
            str(record["experiment_id"])
            for record in self.records.values()
            if record.get("experiment_id")
        }


def _git_recover(paths: repo.ResearchPaths, path: Path) -> Callable[[], str | None] | None:
    """Recover a canonical document from the last commit.

    The design's recovery order is canonical → `.tmp` → Git, and the third step was
    implemented in `ioutil` from the beginning but never wired up: no caller passed the
    callable, so a corrupted `ACTIVE.json` was unrecoverable by the tool even in a
    repository whose last commit held a perfectly good copy.

    Returns None when there is genuinely nothing to recover from, rather than a callable
    that returns None — a repository with no commits has no history to fall back on, and
    saying so is different from offering it.
    """
    if not jgit.is_repository(paths.root):
        return None
    commit = jgit.head_commit(paths.root)
    if commit is None:
        return None
    try:
        relative = path.relative_to(paths.root).as_posix()
    except ValueError:
        return None
    return lambda: jgit.show_file(paths.root, commit, relative)


def load_active(paths: repo.ResearchPaths) -> Record:
    outcome = ioutil.load_json_with_recovery(
        paths.active,
        validator=schema.load_validator("active"),
        git_recover=_git_recover(paths, paths.active),
    )
    return Record(outcome.data, paths.active)


def load_active_with_findings(paths: repo.ResearchPaths) -> tuple[Record, list[Finding]]:
    outcome = ioutil.load_json_with_recovery(
        paths.active,
        validator=schema.load_validator("active"),
        git_recover=_git_recover(paths, paths.active),
    )
    return Record(outcome.data, paths.active), list(outcome.findings)


def load_ledger(paths: repo.ResearchPaths) -> Ledger:
    """Read every evidence shard, the findings document, and all run manifests."""
    ledger = Ledger()
    _load_shards(paths, ledger)
    _load_findings(paths, ledger)
    _load_manifests(paths, ledger)
    ledger.findings = ledger.findings_entries
    return ledger


def current_environment(paths: repo.ResearchPaths) -> tuple[dict[str, Any] | None, dict[str, str]]:
    """The environment an evidence record is produced in, folded from recorded history.

    A `changed` predicate compares the value recorded *then* against the value *now*, and
    `then` is read back from the evidence record itself. Evidence recorded without this
    snapshot can therefore never satisfy a `changed` predicate — and `changed` is the form
    the guidance recommends over a hard-coded value, precisely because it cannot go stale.
    Omitting the snapshot would quietly disable the invalidation mechanism it exists to
    serve, and the failure would look like a predicate-authoring problem rather than a
    missing field.

    Returns `(environment, inputs)`; either may be empty.
    """
    if not paths.environment.is_file():
        return None, {}
    try:
        block = schema.find_block(paths.environment.read_text(encoding="utf-8"), "environment")
    except (OSError, StateInvalid):
        return None, {}
    if not block:
        return None, {}

    flat: dict[str, Any] = {}
    for entry in block.get("history") or []:
        if isinstance(entry, Mapping):
            for key, value in (entry.get("changes") or {}).items():
                flat[str(key)] = value

    comparability = block.get("comparability") or {}
    environment: dict[str, Any] = {
        "id": block.get("environment_id"),
        "comparability": comparability.get("status"),
        "fingerprint": comparability.get("fingerprint"),
    }
    for key, value in flat.items():
        if key.startswith("env."):
            environment[key[len("env.") :]] = value
    inputs = {
        key[len("inputs.") :]: str(value) for key, value in flat.items() if key.startswith("inputs.")
    }
    return environment, inputs


def evidence_referenced_by_findings(ledger: Ledger) -> set[str]:
    cited: set[str] = set()
    for entry in ledger.findings_entries:
        cited.update(str(ev) for ev in entry.get("evidence") or [])
    return cited


def _load_shards(paths: repo.ResearchPaths, ledger: Ledger) -> None:
    if not paths.ledger.is_dir():
        return
    for path in sorted(paths.ledger.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            ledger.unreadable.append(
                Finding("EVIDENCE_UNREADABLE", SEVERITY_ERROR, path.name, f"cannot parse shard: {exc}")
            )
            continue
        if not isinstance(record, dict):
            ledger.unreadable.append(
                Finding("EVIDENCE_NOT_OBJECT", SEVERITY_ERROR, path.name, "shard is not a JSON object")
            )
            continue

        evidence_id = record.get("evidence_id") or path.stem
        if evidence_id in ledger.records:
            ledger.unreadable.append(
                Finding(
                    "DUPLICATE_ID",
                    SEVERITY_ERROR,
                    str(evidence_id),
                    f"two shards declare the same evidence_id ({path.name} and an earlier one)",
                )
            )
            continue
        ledger.records[str(evidence_id)] = record


def _load_findings(paths: repo.ResearchPaths, ledger: Ledger) -> None:
    if not paths.findings.is_file():
        return
    try:
        text = paths.findings.read_text(encoding="utf-8")
        block = schema.find_block(text, "findings")
    except (OSError, StateInvalid) as exc:
        ledger.unreadable.append(
            Finding("FINDINGS_UNREADABLE", SEVERITY_ERROR, "FINDINGS.md", str(exc))
        )
        return
    if block is None:
        return
    ledger.findings_block = block
    entries = block.get("entries")
    if isinstance(entries, list):
        ledger.findings_entries = [entry for entry in entries if isinstance(entry, dict)]


def _load_manifests(paths: repo.ResearchPaths, ledger: Ledger) -> None:
    if not paths.runs.is_dir():
        return
    for directory in sorted(paths.runs.iterdir()):
        manifest_path = directory / "manifest.json"
        if not directory.is_dir() or not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            ledger.unreadable.append(
                Finding("MANIFEST_UNREADABLE", SEVERITY_ERROR, directory.name, f"cannot parse: {exc}")
            )
            continue
        if isinstance(manifest, dict):
            ledger.manifests[directory.name] = manifest


def manifest_completed(manifest: Mapping[str, Any]) -> bool:
    return manifest.get("status") in ("completed", "interrupted")


def unreadable_warning(ledger: Ledger, subject: str) -> list[Finding]:
    if not ledger.unreadable:
        return []
    return [
        Finding(
            "LEDGER_PARTIALLY_UNREADABLE",
            SEVERITY_WARNING,
            subject,
            f"{len(ledger.unreadable)} ledger entr(y/ies) could not be read; "
            f"results below are incomplete",
        )
    ]
