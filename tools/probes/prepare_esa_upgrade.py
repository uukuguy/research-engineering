"""Read-only patch preparation for the frozen ESA September 22 upgrade.

Print one bounded patch group; callers back up and apply reviewed patches separately.
Does not deploy, mutate research state, or enable the development delegation prototype.
"""
import argparse
import difflib
import hashlib
import json
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def protected_digest(dst):
    hashes = {}
    for base in ['.research', 'probes', 'docs/research']:
        for p in (dst / base).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:
                hashes[str(p.relative_to(dst))] = sha(p.read_bytes())
    for name in ['.codex/config.toml', '.claude/settings.json', 'AGENTS.md',
                 'Makefile', 'uv.lock', 'pyproject.toml']:
        p = dst / name
        if p.is_file():
            hashes[name] = sha(p.read_bytes())
    return sha(json.dumps(hashes, sort_keys=True).encode()), len(hashes)


def prepare(src, dst):
    oldlock = (dst / 're-install.json').read_text()
    lock = json.loads(oldlock)
    backup = src / 'outputs' / ('esa-re-upgrade-' + sha(oldlock.encode())[:16])
    payload = {}
    names = ['research-engineering/SKILL.md',
             'research-engineering/references/diagnosis.md',
             'research-engineering/references/external-research.md',
             'research-engineering/references/session-continuity.md',
             'research-pause/SKILL.md', 'research-status/SKILL.md', 'retrospective/SKILL.md']
    for name in names:
        t = (src / 'skills' / name).read_text()
        if name == 'research-engineering/SKILL.md':
            t = '\n'.join(l for l in t.split('\n') if not l.startswith('| two independent questions merit parallel work'))
        if name == 'research-pause/SKILL.md':
            a = t.index('3. For unfinished runs, inspect job liveness and saved outputs.')
            b = t.index('   continue only with a recorded identity', a)
            t = t[:a] + '3. For unfinished runs, inspect job liveness and saved outputs. A detached job may\n' + t[b:]
        if name == 'research-status/SKILL.md':
            a = t.index('If the canonical state directory contains `delegations/`')
            b = t.index('For an established project', a)
            t = t[:a] + t[b:]
        assert 'parallel-research' not in t and '`delegate list`' not in t, name
        for c in ['.agents', '.claude']:
            payload[f'{c}/skills/{name}'] = t
    for name in ['tools/researchlog/commands/run.py', 'tools/researchlog/handoff.py',
                 'tools/researchlog/commands/reconcile.py']:
        t = (src / name).read_text()
        if name.endswith('reconcile.py'):
            t = t.replace('        _delegations,\n', '')
            a = t.index('def _delegations(')
            b = t.index('def _research_routes(', a)
            t = t[:a] + t[b:]
        assert 'delegation' not in t, name
        payload[name] = t
    name = 'docs/RE_OPERATIONS.md'
    t = (dst / name).read_text()
    a = t.index('此入口为交互式操作，研究 block')
    b = t.index('新进程不等于完全隔离', a)
    u = (src / 'templates/project-install/docs/RE_OPERATIONS.md').read_text()
    c = u.index('研究默认围绕')
    d = u.index('新进程不等于完全隔离', c)
    payload[name] = t[:a] + u[c:d] + t[b:]
    changed = {n: t for n, t in payload.items() if (dst / n).read_text() != t}
    for n, t in changed.items():
        if n != 'docs/RE_OPERATIONS.md':
            assert n in lock['files'], n
            lock['files'][n] = sha(t.encode())
    lock.setdefault('targeted_migrations', []).append({
        'purpose': 'method recovery, reporting budget, run timeout and execution pointer validation',
        'changed_files': sorted(changed), 'previous_lock_sha256': sha(oldlock.encode()),
        'backup': str(backup / 'previous.tar.gz'), 'parallel_research_deployed': False})
    changed['re-install.json'] = json.dumps(lock, indent=2) + '\n'
    return changed, backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--group', default='metadata')
    args = parser.parse_args()
    src = Path(__file__).resolve().parents[2]
    dst = args.target.resolve()
    changed, backup = prepare(src, dst)
    if args.group == 'metadata':
        digest, count = protected_digest(dst)
        print(json.dumps({'files': sorted(changed), 'backup': str(backup),
                          'protected_sha256': digest, 'protected_files': count,
                          'prehash': {n: sha((dst / n).read_bytes()) for n in changed},
                          'posthash': {n: sha(t.encode()) for n, t in changed.items()}}))
        return
    parts = ['*** Begin Patch']
    for n, t in changed.items():
        if not n.startswith(args.group):
            continue
        parts += ['*** Update File: ' + str(dst / n)]
        for line in list(difflib.unified_diff((dst / n).read_text().splitlines(), t.splitlines(), n=3))[2:]:
            parts.append('@@' if line.startswith('@@') else line)
    parts += ['*** End Patch']
    print(json.dumps({'patch': '\n'.join(parts)}))


if __name__ == '__main__':
    main()
