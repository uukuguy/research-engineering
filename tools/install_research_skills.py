#!/usr/bin/env python3
"""Copy the canonical skills into each client's skill directory.

Canonical source is `skills/`. Both clients get a generated copy:

    skills/  ->  .claude/skills/     (Claude Code)
             ->  .agents/skills/     (Codex)

Copies, not symlinks: the two clients differ in how they resolve symlinks, and a
portable core should not depend on that.

Because the copies are real files, they can drift. `--check` is the answer — it diffs
the canonical source against what is installed and exits non-zero on any difference, so
drift is caught by a gate rather than by noticing that a skill behaves oddly.

**Per-client overlays.** A skill may carry a `.claude/` or `.agents/` subdirectory
holding files that belong to one client only, such as Codex's
`agents/openai.yaml` with `policy.allow_implicit_invocation`. The overlay is merged into
that client's copy only; the canonical skill stays free of client-specific content, so
the shared protocol cannot be silently forked.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

CLIENTS: dict[str, str] = {
    ".claude/skills": ".claude",
    ".agents/skills": ".agents",
}

# Global install dirs (each client picks up its skills from one of these).
# Claude Code reads ~/.claude/skills/<skill>/. Codex (current) reads from
# ~/.agents/skills/<skill>/ per its config. ~/.codex/skills/ is the older
# Codex layout and is still kept in sync for users with that path pinned.
GLOBAL_CLIENTS: dict[str, Path] = {
    "~/.claude/skills": Path.home() / ".claude" / "skills",
    "~/.agents/skills": Path.home() / ".agents" / "skills",
    "~/.codex/skills": Path.home() / ".codex" / "skills",
}


def re_skill_names(source: Path) -> frozenset[str]:
    """Names of skills the RE protocol owns. Anything else in a global
    skills directory belongs to another plugin / tool and must not be touched
    by install or --check.
    """
    return frozenset(
        child.name
        for child in source.iterdir()
        if child.is_dir() and (child / "SKILL.md").is_file()
    )

EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_ERROR = 2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="install_research_skills",
        description="Install the canonical skills into the chosen destinations.",
        epilog="Run with --check in CI or a gate to catch drift between the two copies.",
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--self", action="store_true", help="install into this repository's .claude/ and .agents/")
    target.add_argument("--target", type=Path, help="install into another repository's .claude/ and .agents/")
    target.add_argument(
        "--global",
        dest="install_global",
        action="store_true",
        help="install into the user's global client skill directories "
             "(~/.claude/skills/, ~/.agents/skills/, ~/.codex/skills/) so every "
             "research workspace session picks them up without per-study sync",
    )
    parser.add_argument("--check", action="store_true", help="report drift; write nothing")
    parser.add_argument(
        "--client",
        choices=sorted(CLIENTS) + sorted(GLOBAL_CLIENTS),
        help="limit to one client (project-relative or global path)",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def canonical_source() -> Path:
    return Path(__file__).resolve().parent.parent / "skills"


def expected_tree(source: Path, overlay: str) -> dict[str, bytes]:
    """What the installed copy should contain: canonical files plus that client's overlay."""
    expected: dict[str, bytes] = {}
    for skill in sorted(source.iterdir()):
        if not skill.is_dir() or not (skill / "SKILL.md").is_file():
            continue
        expected.update(_base_files(skill, source))
        expected.update(_overlay_files(skill, overlay))
    return expected


def _base_files(skill: Path, source: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for path in sorted(skill.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        if relative.parts[1:2] and relative.parts[1] in CLIENTS.values():
            continue  # overlay content belongs to a client copy, not the shared one
        files[str(relative)] = path.read_bytes()
    return files


def _overlay_files(skill: Path, overlay: str) -> dict[str, bytes]:
    directory = skill / overlay
    if not directory.is_dir():
        return {}
    files: dict[str, bytes] = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            files[str(Path(skill.name) / path.relative_to(directory))] = path.read_bytes()
    return files


def installed_tree(destination: Path) -> dict[str, bytes]:
    if not destination.is_dir():
        return {}
    return {
        str(path.relative_to(destination)): path.read_bytes()
        for path in sorted(destination.rglob("*"))
        if path.is_file()
    }


def diff(expected: dict[str, bytes], actual: dict[str, bytes]) -> list[str]:
    lines: list[str] = []
    for name in sorted(set(expected) - set(actual)):
        lines.append(f"  missing   {name}")
    for name in sorted(set(actual) - set(expected)):
        lines.append(f"  stale     {name}")
    for name in sorted(set(expected) & set(actual)):
        if expected[name] != actual[name]:
            lines.append(f"  differs   {name}  ({_digest(expected[name])} -> {_digest(actual[name])})")
    return lines


def install(expected: dict[str, bytes], destination: Path, *, quiet: bool) -> int:
    """Replace the destination with exactly the expected tree."""
    if destination.exists():
        shutil.rmtree(destination)
    for name, content in expected.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    if not quiet:
        print(f"installed {len(expected)} file(s) into {destination}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.install_global:
        return _run_global(args)

    root = Path.cwd().resolve() if args.self else args.target.resolve()  # type: ignore[union-attr]
    source = canonical_source()

    if not source.is_dir():
        print(f"error: canonical skill source not found at {source}", file=sys.stderr)
        return EXIT_ERROR

    clients = {args.client: CLIENTS[args.client]} if args.client else CLIENTS
    drift_found = False

    for relative, overlay in clients.items():
        destination = root / relative
        expected = expected_tree(source, overlay)

        if args.check:
            differences = diff(expected, installed_tree(destination))
            if differences:
                drift_found = True
                print(f"{relative}: DRIFT ({len(differences)} file(s))", file=sys.stderr)
                for line in differences:
                    print(line, file=sys.stderr)
            elif not args.quiet:
                print(f"{relative}: up to date ({len(expected)} file(s))")
            continue

        install(expected, destination, quiet=args.quiet)

    if drift_found:
        print(
            "\nThe installed copies differ from skills/. Edit skills/ and re-run without "
            "--check; never edit an installed copy directly.",
            file=sys.stderr,
        )
        return EXIT_DRIFT
    return EXIT_OK


def _run_global(args: argparse.Namespace) -> int:
    """Install into ~/.claude/skills/, ~/.agents/skills/, ~/.codex/skills/.

    The clients only need their own overlay; Claude Code reads from .claude/,
    Codex (current) from .agents/ and the legacy ~/.codex/skills/ mirror is
    preserved for users with that path pinned. Each overlay is installed
    against the canonical source so a downstream workspace session sees the
    exact same SKILL.md as a developer running --self on this repo.

    Scope: only RE-owned skills are touched. Other plugins share the same
    global directories and must not be overwritten or have their files
    listed as drift.
    """
    source = canonical_source()
    if not source.is_dir():
        print(f"error: canonical skill source not found at {source}", file=sys.stderr)
        return EXIT_ERROR

    owned = re_skill_names(source)
    if not owned:
        print("error: no RE-owned skills found in canonical source", file=sys.stderr)
        return EXIT_ERROR

    targets: dict[str, str]
    if args.client:
        if args.client in GLOBAL_CLIENTS:
            targets = {args.client: ".agents" if ".agents" not in args.client else ".claude"}
        else:
            print(f"error: --client {args.client!r} is not a global target", file=sys.stderr)
            return EXIT_ERROR
    else:
        # Each global dir has its own overlay dir name on disk because the
        # convention stores a per-client overlay next to it (e.g. ~/.agents/
        # carries a Codex-style subdirectory). We map each global home to the
        # overlay it should consume from `skills/<overlay>/`.
        targets = {
            "~/.claude/skills": ".claude",
            "~/.agents/skills": ".agents",
            "~/.codex/skills": ".codex",
        }

    drift_found = False
    for relative, overlay in targets.items():
        destination = GLOBAL_CLIENTS[relative]
        expected_full = expected_tree(source, overlay)
        # Restrict to RE-owned skill trees so unrelated plugins sharing the
        # same home directory never get flagged. The plain comprehension
        # variant had a shadowing bug where every owned key got the last
        # iterated (k, content) pair; writing it out makes the filter
        # explicit and avoids that mistake.
        expected: dict[str, bytes] = {}
        for full_key, content in expected_full.items():
            name = full_key.partition("/")[0]
            if name not in owned:
                continue
            expected[full_key] = content

        if args.check:
            differences = diff(expected, _installed_re_skills(destination, owned))
            if differences:
                drift_found = True
                print(f"{relative}: DRIFT ({len(differences)} file(s))", file=sys.stderr)
                for line in differences:
                    print(line, file=sys.stderr)
            elif not args.quiet:
                print(f"{relative}: up to date ({len(expected)} file(s))")
            continue

        _install_re_skills(expected, destination, quiet=args.quiet)

    if drift_found:
        print(
            "\nGlobal copies differ from skills/. Edit skills/ and re-run with --global; "
            "never edit an installed copy directly.",
            file=sys.stderr,
        )
        return EXIT_DRIFT
    if not args.quiet:
        print(
            f"\nInstalled {len(targets)} global client dir(s) (RE-owned skills only). "
            f"Every research workspace session picks them up on next start."
        )
    return EXIT_OK


def _installed_re_skills(destination: Path, owned: frozenset[str]) -> dict[str, bytes]:
    """Read installed files only under RE-owned skill subdirectories.

    Other plugins share the destination home (`~/.claude/skills/`, etc.);
    listing them as drift would be a false positive and overwrite them on
    real install. Scoping is `path.parts[0] in owned` after relativising to
    `destination`.
    """
    if not destination.is_dir():
        return {}
    out: dict[str, bytes] = {}
    for path in sorted(destination.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(destination)
        if not rel.parts or rel.parts[0] not in owned:
            continue
        out[str(rel)] = path.read_bytes()
    return out


def _install_re_skills(
    expected: dict[str, bytes], destination: Path, *, quiet: bool
) -> int:
    """Install only RE-owned skill trees; leave other plugins untouched."""
    owned_names = {k.partition("/")[0] for k in expected}
    # Remove only the RE-owned subtrees first so unrelated plugin files stay.
    for name in owned_names:
        sub = destination / name
        if sub.is_dir():
            shutil.rmtree(sub)
    for name, content in expected.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    if not quiet:
        print(f"installed {len(expected)} file(s) for {len(owned_names)} RE skill(s) into {destination}")
    return EXIT_OK


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:12]


if __name__ == "__main__":
    raise SystemExit(main())
