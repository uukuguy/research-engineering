"""Durable bounded work packets. No model launcher, process monitor or authority oracle."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from researchlog.errors import Finding, SEVERITY_ERROR, StateInvalid

OPEN = {'prepared', 'dispatched', 'returned'}
TRANSITIONS = {'prepared': {'dispatched', 'cancelled'},
               'dispatched': {'dispatched', 'returned', 'cancelled'},
               'returned': {'accepted', 'needs_followup'},
               'accepted': set(), 'needs_followup': set(), 'cancelled': set()}


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def local_file(workspace, name):
    if not nonempty(name) or Path(name).is_absolute():
        raise StateInvalid('Artifact/input must be a workspace-relative file')
    path = (workspace / name).resolve()
    if not path.is_relative_to(workspace.resolve()) or not path.is_file():
        raise StateInvalid('Missing or escaping workspace file: ' + name)
    return path


def read_object(path):
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError) as exc:
        raise StateInvalid(f'Unreadable packet JSON {path}: {exc}') from exc
    if not isinstance(value, dict):
        raise StateInvalid('Expected JSON object: ' + str(path))
    return value


def evidence_links(paths, row, records):
    """Require reviewed EV artifacts to identify this receipt, not an unrelated EV."""
    linked = set()
    for ev in row.get('review', {}).get('evidence', []):
        for artifact in records.get(ev, {}).get('artifacts') or []:
            raw = artifact.get('path')
            if nonempty(raw):
                linked.add((str((paths.root / raw).resolve()),
                            str(artifact.get('sha256', '')).removeprefix('sha256:')))
    return all((str(Path(a['path']).resolve()), a['sha256']) in linked
               for a in row['result']['artifacts'])


def load(paths):
    folder = paths.research / 'delegations'
    if folder.is_symlink():
        raise StateInvalid('Delegation directory must not be a symlink')
    rows = []
    for path in sorted(folder.glob('W-*.json')):
        if path.is_symlink():
            raise StateInvalid('Delegation file must not be a symlink')
        row = read_object(path)
        if row.get('schema_version') != '1.0':
            raise StateInvalid('Unsupported delegation schema; do not overwrite')
        if row.get('id') != path.stem or not re.fullmatch(r'W-[A-Za-z0-9][A-Za-z0-9_-]*', path.stem):
            raise StateInvalid('Invalid delegation ID')
        history = row.get('history')
        if not isinstance(history, list) or not history:
            raise StateInvalid('Missing delegation history')
        previous = None
        for event in history:
            if not isinstance(event, dict) or not nonempty(event.get('at')) or not nonempty(event.get('reason')):
                raise StateInvalid('Invalid delegation event')
            status = event.get('status')
            if not nonempty(status):
                raise StateInvalid('Invalid event status')
            if (previous is None and status != 'prepared') or (previous is not None and status not in TRANSITIONS.get(previous, set())):
                raise StateInvalid('Invalid delegation transition')
            previous = status
        if row.get('status') != previous or not isinstance(row.get('contract'), dict):
            raise StateInvalid('Delegation state/history mismatch')
        contract = row['contract']
        for key in ('route_id', 'question', 'application_value', 'authority', 'block_id',
                    'deadline', 'workspace', 'return_expectation'):
            if not nonempty(contract.get(key)):
                raise StateInvalid('Malformed contract field: ' + key)
        try:
            deadline = datetime.fromisoformat(contract['deadline'].replace('Z', '+00:00'))
            if deadline.tzinfo is None or not Path(contract['workspace']).is_absolute():
                raise ValueError()
        except ValueError as exc:
            raise StateInvalid('Malformed contract deadline/workspace') from exc
        hashes = contract.get('input_sha256')
        if not isinstance(hashes, dict) or not hashes or not all(
                nonempty(k) and isinstance(v, str) and re.fullmatch(r'[a-f0-9]{64}', v)
                for k, v in hashes.items()):
            raise StateInvalid('Malformed contract input fingerprints')
        for key in ('inputs', 'allowed_writes', 'stop_conditions'):
            if not isinstance(contract.get(key), list) or not contract[key] or not all(nonempty(x) for x in contract[key]):
                raise StateInvalid('Malformed contract list: ' + key)
        if type(contract.get('max_probe_executions')) is not int or contract['max_probe_executions'] < 0:
            raise StateInvalid('Malformed contract probe budget')
        if previous in ('dispatched', 'returned', 'accepted', 'needs_followup') and not nonempty(row.get('worker_ref')):
            raise StateInvalid('Missing worker identity')
        if previous in ('returned', 'accepted', 'needs_followup') and not isinstance(row.get('result'), dict):
            raise StateInvalid('Missing worker result')
        if 'result' in row:
            result = row['result']
            if not isinstance(result, dict):
                raise StateInvalid('Malformed worker result')
            if result.get('packet_id') != row['id'] or result.get('input_sha256') != hashes:
                raise StateInvalid('Result/contract identity mismatch')
            if result.get('execution_status') not in ('completed', 'ENV_BLOCKED', 'INFRA_FAILED', 'EVIDENCE_INVALID', 'RESOURCE_EXCEEDED'):
                raise StateInvalid('Invalid returned execution status')
            if any(not nonempty(result.get(k)) for k in ('summary', 'limitations', 'next_probe')):
                raise StateInvalid('Incomplete worker result')
            artifacts = result.get('artifacts')
            if not isinstance(artifacts, list) or not artifacts:
                raise StateInvalid('Missing returned artifacts')
            for item in artifacts:
                if not isinstance(item, dict) or not nonempty(item.get('path')) or not isinstance(item.get('sha256'), str) or not re.fullmatch(r'[a-f0-9]{64}', item['sha256']):
                    raise StateInvalid('Malformed returned artifact')
        if previous in ('accepted', 'needs_followup'):
            review = row.get('review')
            if not isinstance(review, dict) or not nonempty(review.get('reason')) or not isinstance(review.get('evidence'), list) or not all(nonempty(x) for x in review['evidence']):
                raise StateInvalid('Missing/malformed lead review')
            if previous == 'accepted' and not review['evidence']:
                raise StateInvalid('Accepted receipt has no evidence')
        if previous == 'cancelled' and not nonempty(row.get('stop_confirmation')):
            raise StateInvalid('Cancellation lacks stop observation')
        rows.append(row)
    return rows


def inspect(paths, ledger, *, pending=False):
    try:
        rows = load(paths)
        from researchlog import schema
        current = schema.require_block(paths.current.read_text(), 'current', source=paths.current.name)
        known = {r['id'] for r in current.get('research_routes', []) if isinstance(r, dict) and 'id' in r}
        issues = []
        for row in rows:
            if row['contract'].get('route_id') not in known:
                raise StateInvalid('Unknown delegation route: ' + row['id'])
            for ev in row.get('review', {}).get('evidence', []):
                if ev not in ledger.records:
                    raise StateInvalid('Missing reviewed evidence: ' + ev)
            if row['status'] == 'accepted' and not evidence_links(paths, row, ledger.records):
                raise StateInvalid('Accepted packet lacks evidence links to returned artifacts')
            for artifact in row.get('result', {}).get('artifacts', []):
                if not Path(artifact['path']).is_file():
                    issues.append(Finding('DELEGATION_ARTIFACT_MISSING', SEVERITY_ERROR,
                        row['id'], 'Worker artifact no longer available: ' + artifact['path']))
            if pending and row['status'] in OPEN:
                from researchlog.errors import SEVERITY_WARNING
                issues.append(Finding('DELEGATION_UNFINISHED', SEVERITY_WARNING, row['id'],
                    f"{row['status']}: inspect saved worker identity and outputs; do not relaunch automatically"))
        return issues
    except (StateInvalid, OSError, KeyError, TypeError) as exc:
        return [Finding('DELEGATION_INVALID', SEVERITY_ERROR, 'delegations', str(exc))]
