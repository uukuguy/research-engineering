"""Independent process recovery of worker receipts; no model behavior claim."""
import json
import tempfile
import unittest
from pathlib import Path

from researchlog.tests import test_production_boundaries as fixtures
from researchlog.tests import test_routes as route_fixtures


class DelegationTests(unittest.TestCase):
    setUp = fixtures.ProductionBoundaryTests.setUp
    git = fixtures.ProductionBoundaryTests.git
    cli = fixtures.ProductionBoundaryTests.cli
    init = fixtures.ProductionBoundaryTests.init
    commit_all = fixtures.ProductionBoundaryTests.commit_all
    record = fixtures.ProductionBoundaryTests.record
    command = route_fixtures.RouteTests.command
    add = route_fixtures.RouteTests.add

    def setup_project(self):
        self.init()
        self.add('R-A')
        self.assertEqual(self.cli('active', '--set', 'block.id="RB-pilot"')[0], 0)

    def call(self, action, *args, ok=True):
        code, out = self.cli('delegate', action, *args)
        self.assertEqual(code == 0, ok, out)
        return out.get('payload', {})

    def prepare(self, identifier='W-A', **overrides):
        temp = tempfile.TemporaryDirectory(prefix='re-worker-')
        self.addCleanup(temp.cleanup)
        workspace = Path(temp.name).resolve()
        (workspace / 'input.txt').write_text('measured baseline input\n')
        value = dict(route_id='R-A', question='Does independent inspection find a unit mismatch?',
            application_value='Avoid promoting invalid control geometry', authority='Local fixture only',
            block_id='RB-pilot', deadline='2099-01-01T00:00:00+00:00', workspace=str(workspace),
            inputs=['input.txt'], allowed_writes=['out'], max_probe_executions=1,
            stop_conditions=['Question resolved', 'Deadline'], return_expectation='Raw calculation and limits')
        value.update(overrides)
        file = workspace / 'contract.json'
        file.write_text(json.dumps(value))
        out = self.call('prepare', '--id', identifier, '--file', str(file), '--reason', 'Independent check')
        return workspace, out['delegation']

    def dispatch(self, identifier='W-A'):
        return self.call('dispatch', '--id', identifier, '--worker-ref', 'fixture/session/' + identifier,
                         '--reason', 'Native worker launched in isolated directory')

    def result_file(self, workspace, row, status='completed'):
        (workspace / 'out').mkdir(exist_ok=True)
        (workspace / 'out' / 'raw.txt').write_text('0.5 metres = 500 millimetres\n')
        result = dict(packet_id=row['id'], execution_status=status,
            input_sha256=row['contract']['input_sha256'], summary='Unit mapping checked',
            limitations='One sample, no application run', next_probe='Inspect transport units',
            artifacts=['out/raw.txt'])
        file = workspace / 'result.json'
        file.write_text(json.dumps(result))
        return file

    def test_two_workers_return_review_and_fresh_read(self):
        self.setup_project()
        baseline = (self.state / 'CURRENT.md').read_bytes()
        wa, a = self.prepare()
        wb, b = self.prepare('W-B')
        self.dispatch()
        self.dispatch('W-B')
        for workspace, row in ((wa, a), (wb, b)):
            result = self.result_file(workspace, row)
            self.call('collect', '--id', row['id'], '--file', str(result), '--reason', 'Raw output returned')
        self.assertEqual((self.state / 'CURRENT.md').read_bytes(), baseline)
        # New CLI processes must expose returned work, not rerun it.
        rows = self.call('list')['delegations']
        self.assertEqual([r['status'] for r in rows], ['returned', 'returned'])
        self.call('review', '--id', 'W-A', '--outcome', 'accepted', '--reason', 'Unsupported acceptance', ok=False)
        self.commit_all()
        code, out = self.cli('record', '--question', 'Does the returned calculation preserve units?',
            '--subject-type', 'dataset', '--subject-id', 'worker-raw-output', '--level', 'E0',
            '--execution-status', 'completed', '--research-outcome', 'inconclusive',
            '--confidence', 'low', '--observation', 'Inspected worker calculation; no application run.',
            '--no-experiment', '--artifact', str(wa / 'out' / 'raw.txt'))
        self.assertEqual(code, 0, out)
        ev = next((self.state / 'ledger').rglob('EV-*.json'))
        ev_bytes = ev.read_bytes()
        self.call('review', '--id', 'W-A', '--outcome', 'accepted', '--evidence', ev.stem,
                  '--reason', 'Lead inspected raw output, bounded E0 claim')
        self.call('review', '--id', 'W-B', '--outcome', 'needs_followup',
                  '--reason', 'Insufficient independent control, preserve but do not promote')
        rows = self.call('list')['delegations']
        self.assertEqual([r['status'] for r in rows], ['accepted', 'needs_followup'])
        self.assertEqual(len(rows[0]['history']), 4)
        self.assertEqual(ev.read_bytes(), ev_bytes)
        self.commit_all()
        self.call('list')
        code, out = self.cli('dashboard')
        self.assertEqual(code, 0, out)
        self.assertEqual(len(out['payload']['delegations']), 2)
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_duplicate_transition_and_live_route_switch_refused(self):
        self.setup_project()
        self.prepare()
        self.dispatch()
        self.call('progress', '--id', 'W-A', '--reason', 'Input inspected; comparison remains')
        before = (self.state / 'delegations' / 'W-A.json').read_bytes()
        self.call('dispatch', '--id', 'W-A', '--worker-ref', 'duplicate', '--reason', 'Duplicate', ok=False)
        self.assertEqual(before, (self.state / 'delegations' / 'W-A.json').read_bytes())
        self.assertNotEqual(self.cli('active', '--close-block', '--belief-delta', 'none')[0], 0)
        self.assertNotEqual(self.cli('active', '--set', 'block.id="RB-other"')[0], 0)
        code, _ = self.cli('routes', 'park', '--id', 'R-A', '--reason', 'Switch', '--wake-when', 'Later')
        self.assertNotEqual(code, 0)
        code, out = self.cli('reconcile')
        self.assertIn('DELEGATION_UNFINISHED', [f['code'] for f in out['findings']])
        self.call('cancel', '--id', 'W-A', '--reason', 'User stopped fixture worker',
                  '--stop-confirmation', 'Fixture process exited')
        self.assertEqual(self.call('list')['delegations'][0]['status'], 'cancelled')

    def test_changed_artifact_cannot_be_accepted(self):
        self.setup_project()
        workspace, row = self.prepare()
        self.dispatch()
        result = self.result_file(workspace, row)
        self.call('collect', '--id', 'W-A', '--file', str(result), '--reason', 'Collected')
        (workspace / 'out' / 'raw.txt').write_text('different result')
        self.call('review', '--id', 'W-A', '--outcome', 'needs_followup', '--reason', 'Changed', ok=False)

    def test_bad_input_identity_and_path_escape_refused(self):
        self.setup_project()
        workspace, row = self.prepare()
        self.dispatch()
        file = self.result_file(workspace, row)
        value = json.loads(file.read_text())
        value['input_sha256'] = {}
        file.write_text(json.dumps(value))
        self.call('collect', '--id', 'W-A', '--file', str(file), '--reason', 'Wrong input', ok=False)
        value['input_sha256'] = row['contract']['input_sha256']
        value['artifacts'] = ['../outside']
        file.write_text(json.dumps(value))
        self.call('collect', '--id', 'W-A', '--file', str(file), '--reason', 'Escape', ok=False)

    def test_corruption_visible_in_all_readers(self):
        self.setup_project()
        self.prepare()
        file = self.state / 'delegations' / 'W-A.json'
        value = json.loads(file.read_text())
        value['status'] = 'accepted'
        file.write_text(json.dumps(value))
        for cmd in ('validate', 'reconcile', 'dashboard'):
            code, out = self.cli(cmd)
            self.assertNotEqual(code, 0, out)
            self.assertIn('DELEGATION_INVALID', [f['code'] for f in out['findings']])

    def test_third_worker_and_shared_workspace_refused(self):
        self.setup_project()
        self.prepare()
        self.prepare('W-B')
        with self.assertRaises(AssertionError):
            self.prepare('W-C')
        self.call('cancel', '--id', 'W-A', '--reason', 'Not launched', '--stop-confirmation', 'Not launched')
        with self.assertRaises(AssertionError):
            self.prepare('W-D', workspace=str(self.root))

    def test_environment_failure_not_promoted_to_negative(self):
        self.setup_project()
        workspace, row = self.prepare()
        self.dispatch()
        result = self.result_file(workspace, row, 'ENV_BLOCKED')
        self.call('collect', '--id', 'W-A', '--file', str(result), '--reason', 'Missing hardware')
        self.call('review', '--id', 'W-A', '--outcome', 'needs_followup', '--reason', 'No scientific result')
        stored = self.call('list')['delegations'][0]
        self.assertEqual(stored['result']['execution_status'], 'ENV_BLOCKED')
        self.assertEqual(self.command('list')['routes'][0]['status'], 'queued')

    def test_unsupported_version_and_stale_lock_never_overwritten(self):
        self.setup_project()
        self.prepare()
        path = self.state / 'delegations' / 'W-A.json'
        value = json.loads(path.read_text())
        value['schema_version'] = '99.0'
        path.write_text(json.dumps(value))
        before = path.read_bytes()
        self.call('cancel', '--id', 'W-A', '--reason', 'Unsupported', '--stop-confirmation', 'Never launched', ok=False)
        self.assertEqual(path.read_bytes(), before)
        lock = path.parent / '.writer-lock'
        lock.mkdir()
        self.call('cancel', '--id', 'W-A', '--reason', 'Locked', '--stop-confirmation', 'Never launched', ok=False)
        self.assertTrue(lock.is_dir())
        self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
