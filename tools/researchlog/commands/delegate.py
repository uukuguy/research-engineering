"""Lead-owned work packet lifecycle; workers return files, never mutate shared state."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from researchlog import delegation as d, repo, routes, schema, state
from researchlog.errors import Result, StateInvalid

NAME = 'delegate'
HELP = 'prepare, dispatch, collect and review bounded worker packets (does not launch agents)'


def configure(parser):
    parser.add_argument('--root', type=Path)
    sub = parser.add_subparsers(dest='action', required=True)
    for name in ('list', 'prepare', 'dispatch', 'progress', 'collect', 'review', 'cancel'):
        p = sub.add_parser(name)
        p.add_argument('--root', type=Path, default=argparse.SUPPRESS)
        p.add_argument('--json', action='store_true', default=argparse.SUPPRESS)
        p.add_argument('--id', required=name != 'list')
        if name != 'list':
            p.add_argument('--reason', required=True)
        if name in ('prepare', 'collect'):
            p.add_argument('--file', type=Path, required=True)
        if name == 'dispatch':
            p.add_argument('--worker-ref', required=True, help='client/session/task identity; not liveness proof')
        if name == 'review':
            p.add_argument('--outcome', choices=('accepted', 'needs_followup'), required=True)
            p.add_argument('--evidence', action='append', default=[])
        if name == 'cancel':
            p.add_argument('--stop-confirmation', required=True, help='observation that worker stopped/never launched')


def contract(paths, value, rows):
    for key in ('route_id', 'question', 'application_value', 'authority', 'block_id', 'deadline',
                'workspace', 'return_expectation'):
        if not d.nonempty(value.get(key)):
            raise StateInvalid('Required contract field: ' + key)
    try:
        from datetime import datetime, timezone
        deadline = datetime.fromisoformat(value['deadline'].replace('Z', '+00:00'))
        if deadline.tzinfo is None or deadline <= datetime.now(timezone.utc):
            raise ValueError()
    except ValueError as exc:
        raise StateInvalid('Deadline must be a future timezone-qualified timestamp') from exc
    for key in ('inputs', 'allowed_writes', 'stop_conditions'):
        if not isinstance(value.get(key), list) or not value[key] or not all(d.nonempty(x) for x in value[key]):
            raise StateInvalid('Required nonempty string list: ' + key)
    for name in value['allowed_writes']:
        if Path(name).is_absolute() or '..' in Path(name).parts or not Path(name).parts:
            raise StateInvalid('Write scope must name relative files/directories, not the entire workspace')
        if Path(name).parts[0] in ('.git', '.research', 'research', '.agents', '.claude', '.codex'):
            raise StateInvalid('Worker cannot own shared protocol/state/configuration')
    if type(value.get('max_probe_executions')) is not int or value['max_probe_executions'] < 0:
        raise StateInvalid('max_probe_executions must be a nonnegative integer')
    workspace = Path(value['workspace'])
    if not workspace.is_absolute() or not workspace.is_dir():
        raise StateInvalid('Workspace must be an existing absolute directory')
    workspace = workspace.resolve()
    if workspace.is_relative_to(paths.root) or paths.root.is_relative_to(workspace):
        raise StateInvalid('Worker requires a separate workspace outside the lead project')
    for row in rows:
        other = Path(row['contract']['workspace'])
        if row['status'] in d.OPEN and (workspace.is_relative_to(other) or other.is_relative_to(workspace)):
            raise StateInvalid('Unfinished worker owns an overlapping workspace')
    current = schema.require_block(paths.current.read_text(), 'current', source=paths.current.name)
    ledger = state.load_ledger(paths)
    if routes.check(current, set(ledger.records)) or ledger.unreadable:
        raise StateInvalid('Reconcile route/evidence state before delegation')
    portfolio = {r['id']: r for r in current.get('research_routes', [])}
    route = portfolio.get(value['route_id'])
    if not route or route['status'] not in ('queued', 'active'):
        raise StateInvalid('Only available queued/active routes can receive work')
    if any(portfolio[x]['status'] != 'completed' for x in route['depends_on']):
        raise StateInvalid('Route dependencies are unfinished')
    block = state.load_active(paths).get('block') or {}
    if block.get('id') != value['block_id'] or block.get('belief_delta') is not None:
        raise StateInvalid('Packet must belong to the current open research block')
    if sum(r['status'] in ('prepared', 'dispatched') for r in rows) >= 2:
        raise StateInvalid('Initial supervised pilot allows at most two outstanding workers')
    value = dict(value, workspace=str(workspace))
    value['input_sha256'] = {name: d.fingerprint(d.local_file(workspace, name)) for name in value['inputs']}
    return value


def run(args):
    paths = repo.require(args.root)
    if args.action == 'list':
        rows = [r for r in d.load(paths) if not args.id or r['id'] == args.id]
        if args.id and not rows:
            raise StateInvalid('Unknown work packet')
        from researchlog.commands.dashboard import line
        return Result(payload={'delegations': rows, 'liveness': 'unknown'}, human='\n'.join(
            line(f"{r['id']} [{r['status']}] {r['contract']['question']}") for r in rows) or '暂无分派任务。')
    if not re.fullmatch(r'W-[A-Za-z0-9][A-Za-z0-9_-]*', args.id) or not d.nonempty(args.reason):
        raise StateInvalid('Expected W-* ID and nonempty reason')
    folder = paths.research / 'delegations'
    if folder.is_symlink():
        raise StateInvalid('Delegation directory must not be a symlink')
    folder.mkdir(exist_ok=True)
    lock = folder / '.writer-lock'
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise StateInvalid('Delegation writer busy or interrupted; inspect owner before removing stale lock') from exc
    try:
        rows = d.load(paths)
        row = next((r for r in rows if r['id'] == args.id), None)
        target = folder / (args.id + '.json')
        before = target.read_text() if target.exists() else None
        if args.action == 'prepare':
            if row:
                raise StateInvalid('Packet ID already exists; retries require a new ID')
            row = {'schema_version': '1.0', 'id': args.id,
                   'contract': contract(paths, d.read_object(args.file), rows), 'history': []}
            next_status = 'prepared'
        else:
            if row is None:
                raise StateInvalid('Unknown work packet')
            next_status = {'dispatch': 'dispatched', 'progress': 'dispatched', 'collect': 'returned',
                           'review': getattr(args, 'outcome', None), 'cancel': 'cancelled'}[args.action]
            if next_status not in d.TRANSITIONS[row['status']]:
                raise StateInvalid('Illegal work packet transition')
            if args.action == 'dispatch' and row['status'] != 'prepared':
                raise StateInvalid('Already dispatched; do not launch a duplicate')
            if args.action == 'progress' and row['status'] != 'dispatched':
                raise StateInvalid('Progress is only recorded for dispatched work')
            if args.action == 'dispatch':
                from datetime import datetime, timezone
                if not d.nonempty(args.worker_ref):
                    raise StateInvalid('Worker identity required')
                if datetime.fromisoformat(row['contract']['deadline'].replace('Z', '+00:00')) <= datetime.now(timezone.utc):
                    raise StateInvalid('Packet deadline expired; do not launch')
                block = state.load_active(paths).get('block') or {}
                if block.get('id') != row['contract']['block_id'] or block.get('belief_delta') is not None:
                    raise StateInvalid('Original block no longer open')
                row['worker_ref'] = args.worker_ref
            elif args.action == 'collect':
                result = d.read_object(args.file)
                for key in ('summary', 'limitations', 'next_probe'):
                    if not d.nonempty(result.get(key)):
                        raise StateInvalid('Missing worker result field: ' + key)
                if result.get('packet_id') != args.id or result.get('execution_status') not in (
                        'completed', 'ENV_BLOCKED', 'INFRA_FAILED', 'EVIDENCE_INVALID', 'RESOURCE_EXCEEDED'):
                    raise StateInvalid('Wrong packet ID or execution status')
                if result.get('input_sha256') != row['contract']['input_sha256']:
                    raise StateInvalid('Returned input identity differs from issued packet')
                names = result.get('artifacts')
                if not isinstance(names, list) or not names or not all(d.nonempty(x) for x in names):
                    raise StateInvalid('Result requires raw output/report artifact paths')
                workspace = Path(row['contract']['workspace'])
                result['artifacts'] = [{'path': str(d.local_file(workspace, name)),
                    'sha256': d.fingerprint(d.local_file(workspace, name))} for name in names]
                row['result'] = result
            elif args.action == 'review':
                ledger = state.load_ledger(paths)
                if ledger.unreadable or any(ev not in ledger.records for ev in args.evidence):
                    raise StateInvalid('Review references missing/unreadable evidence')
                for item in row['result']['artifacts']:
                    path = Path(item['path'])
                    if not path.is_file() or d.fingerprint(path) != item['sha256']:
                        raise StateInvalid('Returned artifact missing or changed; cannot review')
                if args.outcome == 'accepted' and not args.evidence:
                    raise StateInvalid('Acceptance requires lead-recorded evidence; completion is not a conclusion')
                row['review'] = {'reason': args.reason, 'evidence': args.evidence,
                                 'meaning': 'receipt reviewed, not hypothesis confirmation or promotion'}
                if args.outcome == 'accepted' and not d.evidence_links(paths, row, ledger.records):
                    raise StateInvalid('Evidence must link the returned artifact paths and hashes, not unrelated work')
            elif args.action == 'cancel':
                if not d.nonempty(args.stop_confirmation):
                    raise StateInvalid('Stop/never-launched observation is required')
                row['stop_confirmation'] = args.stop_confirmation
        row['status'] = next_status
        row['history'].append({'at': d.now(), 'status': next_status, 'reason': args.reason})
        rendered = json.dumps(row, ensure_ascii=False, indent=2) + '\n'
        if before is None:
            # Lock serializes all cooperating writers; immutable ID checked above.
            import os, tempfile
            fd, name = tempfile.mkstemp(prefix='.packet-', dir=folder)
            temporary = Path(name)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    stream.write(rendered)
                    stream.flush()
                    os.fsync(stream.fileno())
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
        else:
            routes.write_current(target, before, rendered)
        import os
        directory_fd = os.open(folder, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return Result(payload={'delegation': row, 'agent_launched': False, 'research_authorized': False},
                      human='分派记录已保存；未启动或停止 agent，未批准研究结论。')
    finally:
        lock.rmdir()
