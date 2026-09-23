"""Read-only local handoff checks, not a semantic or portability certificate."""
import json

from researchlog import constraints, jgit, state
from researchlog.errors import Finding, SEVERITY_ERROR, StateInvalid


def inspect(paths, ledger):
    findings = []

    def error(code, where, message):
        findings.append(Finding(code, SEVERITY_ERROR, str(where), message))

    try:
        active = state.load_active(paths)
    except StateInvalid as exc:
        return list(exc.findings)
    members = constraints.block_members(active.get('block.id'), list(ledger.records.values()))
    for field, count in (
        ('completed_evidence_iterations', constraints.count_evidence_iterations(members)),
        ('reproduction_iterations', constraints.count_reproduction_iterations(members)),
    ):
        if (active.get('block.' + field) or 0) != count:
            error('HANDOFF_COUNTS_STALE', 'ACTIVE.json',
                  f'{field} differs from ledger ({count}); run active --refresh-counts')

    try:
        current = paths.current.read_text(encoding='utf-8')
    except OSError:
        current = ''
    if members:
        latest = max(members, key=lambda r: str(r.get('evidence_id', '')))
        eid = latest.get('evidence_id')
        if eid and eid not in current:
            error('HANDOFF_CURRENT_MISSING_EVIDENCE', paths.current,
                  f'CURRENT does not reference latest block evidence {eid}; persist its limits and resume point')

    required = {paths.active, paths.current, paths.architect, paths.boundaries, paths.environment, paths.findings}
    experiment = active.get('experiment_id')
    manifest = ledger.manifests.get(experiment)
    if manifest:
        if manifest.get('execution', {}).get('output_capture_complete') is False:
            error('HANDOFF_CAPTURE_UNRESOLVED', experiment,
                  'output capture is incomplete; verify surviving jobs and saved output before handoff')
        required.add(paths.manifest(experiment))
        if state.manifest_completed(manifest):
            required.add(paths.result(experiment))
        # Only project-local script arguments, never arbitrary shell command parsing.
        command = manifest.get('command', [])
        if isinstance(command, list):
            for arg in command:
                if isinstance(arg, str) and arg.endswith(('.py', '.sh')):
                    candidate = paths.root / arg
                    if candidate.is_file() and candidate.resolve().is_relative_to(paths.root.resolve()):
                        required.add(candidate)
    for record in members:
        for artifact in record.get('artifacts') or []:
            name = artifact.get('path')
            if not isinstance(name, str):
                continue
            candidate = paths.root / name
            if not candidate.is_file():
                error('HANDOFF_ARTIFACT_MISSING', name, 'referenced artifact is not accessible')
            elif candidate.resolve().is_relative_to(paths.root.resolve()):
                required.add(candidate)
            elif not artifact.get('sha256'):
                error('HANDOFF_EXTERNAL_IDENTITY_MISSING', name, 'external artifact needs a recorded identity')

    if not jgit.is_repository(paths.root):
        error('HANDOFF_NO_CHECKPOINT', paths.root, 'no Git repository; local record checkpoint unavailable')
        return findings
    for path in sorted(required):
        name = path.relative_to(paths.root).as_posix()
        if not path.is_file():
            error('HANDOFF_ARTIFACT_MISSING', name, 'recovery file is missing')
            continue
        committed = jgit.git(['cat-file', '-e', 'HEAD:' + name], cwd=paths.root)
        diff = jgit.git(['diff', 'HEAD', '--', name], cwd=paths.root)
        if path == paths.active and committed.ok and diff.stdout:
            saved = jgit.git(['show', 'HEAD:' + name], cwd=paths.root)
            try:
                before, after = json.loads(saved.stdout), json.loads(path.read_text())
                # Only the tool's unavoidable post-commit stamp may remain dirty.
                stamp = after.get('git', {}).get('checkpoint_commit')
                for document in (before, after):
                    document.pop('updated_at', None)
                    document.get('git', {}).pop('checkpoint_commit', None)
                if before == after and stamp == jgit.head_commit(paths.root):
                    continue
            except (ValueError, OSError):
                pass
        if not committed.ok or not diff.ok or diff.stdout:
            error('HANDOFF_NOT_CHECKPOINTED', name,
                  'recovery file is not saved in HEAD; inspect and checkpoint its exact path')
    return findings
