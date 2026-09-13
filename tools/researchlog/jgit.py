"""Git plumbing via subprocess.

No GitPython: the tool ships with no dependencies, and every command here maps to one
`git` invocation whose output we parse. All calls are list-form, never `shell=True`.

Read-only helpers return None rather than raising when Git is unavailable or the
repository has no commits yet — a research repo may legitimately be younger than its
first commit, and that must not stop `reconcile` from reporting what it can.
"""

from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

# The research state directory is a layout fact, not a git fact, and `repo` is where that
# layout is defined. `repo` does not import this module, so there is no cycle.
from researchlog import repo

TIMEOUT_SECONDS = 30
_TRAILER_KEY = "Evidence"


@dataclass(frozen=True, slots=True)
class GitResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass(frozen=True, slots=True)
class CodeState:
    branch: str | None
    commit: str | None
    dirty: bool
    diff_sha256: str | None
    changed_files: tuple[str, ...]

    def to_dict(self, *, base_commit: str | None = None) -> dict[str, object]:
        return {
            "branch": self.branch,
            "commit": self.commit,
            "base_commit": base_commit if base_commit is not None else self.commit,
            "dirty": self.dirty,
            "diff_sha256": self.diff_sha256,
        }


def git(args: Sequence[str], *, cwd: Path) -> GitResult:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        return GitResult(127, "", "git executable not found")
    except subprocess.TimeoutExpired:  # pragma: no cover - defensive
        return GitResult(124, "", f"git {' '.join(args)} timed out after {TIMEOUT_SECONDS}s")
    return GitResult(completed.returncode, completed.stdout, completed.stderr)


def is_repository(root: Path) -> bool:
    return git(["rev-parse", "--git-dir"], cwd=root).ok


def head_commit(root: Path) -> str | None:
    result = git(["rev-parse", "HEAD"], cwd=root)
    return result.stdout.strip() if result.ok else None


def current_branch(root: Path) -> str | None:
    result = git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=root)
    if not result.ok:
        return None
    name = result.stdout.strip()
    return None if name == "HEAD" else name  # detached


def status_porcelain(root: Path, *, exclude: Sequence[str] = ()) -> tuple[str, ...]:
    arguments = ["status", "--porcelain"]
    arguments.extend(_pathspec(exclude))
    result = git(arguments, cwd=root)
    if not result.ok:
        return ()
    return tuple(line for line in result.stdout.splitlines() if line.strip())


def is_dirty(root: Path, *, exclude: Sequence[str] = ()) -> bool:
    return bool(status_porcelain(root, exclude=exclude))


def diff_sha256(root: Path, *, exclude: Sequence[str] = ()) -> str | None:
    """Hash of the working tree delta, so a dirty run still has a stable code identity."""
    pathspec = _pathspec(exclude)
    tracked = git(["diff", "HEAD", "--", *pathspec], cwd=root)
    untracked = git(["ls-files", "--others", "--exclude-standard", "--", *pathspec], cwd=root)
    if not tracked.ok and not untracked.ok:
        return None
    digest = hashlib.sha256()
    digest.update(tracked.stdout.encode("utf-8"))
    digest.update(untracked.stdout.encode("utf-8"))
    return f"sha256:{digest.hexdigest()}"


def code_state(root: Path) -> CodeState:
    """The identity of the *code*, not of the research record.

    The canonical state directory is excluded. It is what the research wrote down, not what
    the research ran, and hashing it made every evidence record's identity unique: writing a
    shard moved the identity of the run that produced it. So no two records were ever
    comparable, and `compare` answered `ATTRIBUTION_FORBIDDEN` every time — the verdict that
    exists to stop unattributable deltas from becoming findings was on permanently, which is
    the same as not having it.

    `is_dirty` is left with its whole-repository meaning and is called without an exclusion
    by `ACTIVE.git.dirty_expected`, which is about uncommitted work of any kind, bookkeeping
    included.
    """
    exclude = (repo.RESEARCH_DIR,)
    changed = status_porcelain(root, exclude=exclude)
    return CodeState(
        branch=current_branch(root),
        commit=head_commit(root),
        dirty=bool(changed),
        diff_sha256=diff_sha256(root, exclude=exclude) if changed else None,
        changed_files=changed,
    )


def _pathspec(exclude: Sequence[str]) -> list[str]:
    """`git` arguments selecting the whole tree minus the excluded directories.

    Anchored at the repository root, so a directory that merely shares the name — a
    `templates/research/` skeleton, say — is not excluded along with it.
    """
    return [".", *(f":(exclude){pattern}/**" for pattern in exclude)]


def check_ignore(root: Path, path: str) -> str | None:
    """Return the .gitignore pattern excluding `path`, or None if it is tracked-able."""
    result = git(["check-ignore", "-v", "--", path], cwd=root)
    if result.returncode != 0:
        return None
    parts = result.stdout.strip().split(":", 3)
    return parts[-1].strip() if parts else "unknown pattern"


def show_file(root: Path, revision: str, path: str) -> str | None:
    result = git(["show", f"{revision}:{path}"], cwd=root)
    return result.stdout if result.ok else None


def evidence_trailers(root: Path, *, limit: int = 200) -> list[tuple[str, str]]:
    """Return (commit_sha, evidence_id) for commits that carry an Evidence trailer.

    Used to detect a commit whose message cites the evidence that contains that very
    commit — a self-reference that cannot be resolved and must not be recorded.
    """
    result = git(
        ["log", f"-{limit}", "--format=%H%x00%(trailers:key=" + _TRAILER_KEY + ",valueonly)"],
        cwd=root,
    )
    if not result.ok:
        return []
    pairs: list[tuple[str, str]] = []
    for block in result.stdout.split("\n\n"):
        lines = [line for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        sha = lines[0].split("\x00")[0].strip()
        for line in lines:
            for chunk in line.split("\x00")[1:]:
                for value in chunk.split():
                    if value:
                        pairs.append((sha, value.strip()))
    return pairs
