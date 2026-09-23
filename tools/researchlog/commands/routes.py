"""Explicit, single-writer portfolio changes; never launch or authorize research."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from researchlog import repo, routes, schema, state
from researchlog.errors import Result, StateInvalid

NAME = 'routes'
HELP = 'list, register, update, park, block, wake or switch durable research routes'


def configure(parser):
    parser.add_argument('--root', type=Path, default=None)
    sub = parser.add_subparsers(dest='action', required=True)
    for name in ('list', 'add', 'update', 'park', 'block', 'wake', 'activate', 'close'):
        p = sub.add_parser(name)
        p.add_argument('--root', type=Path, default=argparse.SUPPRESS)
        p.add_argument('--json', action='store_true', default=argparse.SUPPRESS)
        target = p.add_mutually_exclusive_group(required=name not in ('list',))
        target.add_argument('--id')
        if name != 'add':
            target.add_argument('--select', type=int, help='number from a previously displayed route list')
            p.add_argument('--portfolio-revision', help='exact revision of the displayed selection list')
        if name == 'list':
            continue
        p.add_argument('--reason', required=True)
        p.add_argument('--evidence', action='append', default=[])
        if name in ('add', 'update'):
            p.add_argument('--priority', type=int, default=1 if name == 'add' else None)
            for field in ('title', 'question', 'value', 'next-probe', 'resume-point'):
                p.add_argument('--' + field, required=name == 'add')
            for field in ('depends-on', 'alternatives'):
                p.add_argument('--' + field, nargs='*', default=None)
        if name in ('park', 'block'):
            p.add_argument('--wake-when', required=True)
        if name == 'activate':
            p.add_argument('--park-reason')
            p.add_argument('--park-wake-when')
        if name == 'wake':
            p.add_argument('--trigger', required=True,
                           help='observed change satisfying the wake condition; not an automatic check')
        if name == 'close':
            p.add_argument('--outcome', choices=('completed', 'rejected'), required=True)


def run(args):
    paths = repo.require(args.root)
    text = paths.current.read_text(encoding='utf-8')
    block = schema.require_block(text, 'current', source=paths.current.name)
    ledger = state.load_ledger(paths)
    problems = routes.check(block, set(ledger.records))
    if problems or ledger.unreadable:
        raise StateInvalid(problems + ledger.unreadable)
    rows = block.get('research_routes', [])
    revision = hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    ordered = sorted(rows, key=lambda r: (r['status'] != 'active', r['priority'], r['id']))
    choices = [{'number': i, 'id': r['id'], 'title': r['title'], 'status': r['status']}
               for i, r in enumerate(ordered, 1)]
    number = getattr(args, 'select', None)
    if number is not None:
        if getattr(args, 'portfolio_revision', None) != revision:
            raise StateInvalid('Route list changed or revision missing; display the current list and ask for selection again')
        if not 1 <= number <= len(choices):
            raise StateInvalid('Route selection is outside the displayed list')
        args.id = choices[number - 1]['id']
    if args.action == 'list':
        selected = [r for r in rows if not args.id or r['id'] == args.id]
        selected.sort(key=lambda r: (r['priority'], r['id']))
        if args.id and not selected:
            raise StateInvalid('Unknown route: ' + args.id)
        from researchlog.commands.dashboard import line
        numbers = {c['id']: c['number'] for c in choices}
        return Result(payload={'routes': selected, 'choices': choices, 'portfolio_revision': revision,
                               'registered': 'research_routes' in block},
                      human='\n'.join(line(f"{numbers[r['id']]}. {r['id']} [{r['status']}] P{r['priority']} {r['title']}") for r in ordered if not args.id or r['id'] == args.id)
                      or '尚未登记研究路线；不代表没有未解决问题。')

    schema.require_writable('current', paths.current, block)
    if not args.reason.strip():
        raise StateInvalid('A nonempty reason is required')
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    by_id = {r['id']: r for r in rows}
    changed = []

    def note(row, status, reason, trigger=None):
        previous = row['status']
        row.update(status=status, reason=reason, updated_at=stamp)
        event = {'at': stamp, 'action': args.action, 'from': previous, 'to': status,
                 'reason': reason, 'evidence': list(args.evidence),
                 'next_probe': row['next_probe'], 'resume_point': row['resume_point'],
                 'wake_when': row['wake_when']}
        if trigger is not None:
            event['trigger'] = trigger
        row['history'].append(event)
        changed.append(row['id'])

    if args.action == 'add':
        if args.id in by_id:
            raise StateInvalid('Route already registered: ' + args.id)
        row = {k: getattr(args, k) for k in ('title', 'question', 'value', 'next_probe', 'resume_point')}
        row.update(id=args.id, status='queued', reason=args.reason, wake_when='',
                   priority=args.priority,
                   updated_at=stamp, evidence=[], history=[],
                   depends_on=args.depends_on or [], alternatives=args.alternatives or [])
        rows.append(row)
    else:
        if args.id not in by_id:
            raise StateInvalid('Unknown route: ' + args.id)
        row = by_id[args.id]
    row['evidence'] = list(dict.fromkeys(row['evidence'] + args.evidence))

    # Changing focus/lifecycle is unsafe while execution is unfinished. Registration
    # and descriptive updates remain possible while researching the current route.
    if args.action not in ('add', 'update'):
        from researchlog import delegation
        if any(r['status'] in delegation.OPEN for r in delegation.load(paths)):
            raise StateInvalid('Review/close outstanding worker packets before changing route lifecycle')
        active = state.load_active(paths)
        if active.get('status') != 'idle' or any(
                m.get('status') in ('running', 'pending') or
                (exp == active.get('experiment_id') and
                 m.get('status') == 'interrupted' and not paths.result(exp).is_file()) or
                m.get('execution', {}).get('output_capture_complete') is False
                for exp, m in ledger.manifests.items()):
            raise StateInvalid('Close/reconcile unfinished execution before changing route lifecycle')
    if args.action == 'update':
        for key in ('title', 'question', 'value', 'next_probe', 'resume_point', 'depends_on', 'alternatives', 'priority'):
            if getattr(args, key) is not None:
                row[key] = getattr(args, key)
        note(row, row['status'], args.reason)
    elif args.action in ('park', 'block'):
        if row['status'] in ('completed', 'rejected'):
            raise StateInvalid('Wake a closed route explicitly before parking/blocking it')
        row['wake_when'] = args.wake_when
        note(row, 'parked' if args.action == 'park' else 'blocked', args.reason)
    elif args.action == 'wake':
        if row['status'] not in ('parked', 'blocked', 'completed', 'rejected'):
            raise StateInvalid('Only a parked, blocked or closed route can be woken')
        if not args.trigger.strip():
            raise StateInvalid('Wake needs an observed trigger')
        if row['status'] in ('completed', 'rejected') and not args.evidence:
            raise StateInvalid('Reopening a closed route requires new cited evidence')
        note(row, 'queued', args.reason, args.trigger)
    elif args.action == 'activate':
        if row['status'] != 'queued':
            raise StateInvalid('Only queued routes can activate; wake dormant routes explicitly first')
        for old in rows:
            if old['status'] == 'active':
                if not args.park_reason or not args.park_reason.strip() or not args.park_wake_when or not args.park_wake_when.strip():
                    raise StateInvalid('Switch requires --park-reason and --park-wake-when for the previous route')
                old['wake_when'] = args.park_wake_when
                note(old, 'parked', args.park_reason)
        note(row, 'active', args.reason)
    elif args.action == 'close':
        if not args.evidence:
            raise StateInvalid('Closing a route requires cited evidence; defer untested routes instead')
        records = [ledger.records.get(ev, {}) for ev in args.evidence]
        usable = [ev for ev in records if ev.get('execution_status') == 'completed' and
                  (ev.get('surrogate_contract') or {}).get('verdict') != 'EVIDENCE_INVALID']
        if not usable:
            raise StateInvalid('Environment failure or invalid evidence cannot close a research route')
        if args.outcome == 'rejected' and not any(
                ev.get('research_outcome') in ('refuted', 'failed') for ev in usable):
            raise StateInvalid('Rejection requires scientific negative evidence; park unchosen routes')
        note(row, args.outcome, args.reason)
    else:
        note(row, 'queued', args.reason)
    block['research_routes'] = rows
    problems = routes.check(block, set(ledger.records))
    problems += schema.load_validator('current').check(block)
    if problems:
        raise StateInvalid(problems)
    routes.write_current(paths.current, text, schema.replace_block(text, 'current', block))
    return Result(payload={'changed': changed, 'routes': rows, 'research_authorized': False},
                  human='已保存路线状态；未启动实验，也不构成研究授权。')
