"""Fresh-process portfolio recovery and refusal tests, without an LLM or live project."""
import json
import unittest

from researchlog import schema
from researchlog.tests.test_production_boundaries import ProductionBoundaryTests as Fixture


class RouteTests(unittest.TestCase):
    setUp = Fixture.setUp
    git = Fixture.git
    cli = Fixture.cli
    init = Fixture.init
    commit_all = Fixture.commit_all
    record = Fixture.record

    def command(self, *args):
        code, result = self.cli('routes', *args)
        self.assertEqual(code, 0, result)
        return result['payload']

    def add(self, identifier, *extra):
        return self.command('add', '--id', identifier, '--title', identifier,
            '--question', 'Which mechanism fits?', '--value', 'Unlock application capability',
            '--next-probe', 'Compare two actual inputs', '--resume-point', 'probes/slice.py at known baseline',
            '--reason', 'Cheapest useful uncertainty', *extra)

    def rejected_without_write(self, *args):
        before = (self.state / 'CURRENT.md').read_bytes()
        code, result = self.cli('routes', *args)
        self.assertNotEqual(code, 0, result)
        self.assertEqual(before, (self.state / 'CURRENT.md').read_bytes())
        return result

    def test_a_b_fresh_process_wake_a_preserves_both_routes(self):
        self.init()
        self.add('R-A')
        self.add('R-B', '--alternatives', 'R-A', '--priority', '2')
        self.command('activate', '--id', 'R-A', '--reason', 'First discriminating probe')
        self.command('update', '--id', 'R-A', '--reason', 'Checkpoint before switching',
                     '--resume-point', 'probes/slice.py: inspected A; missing transport')
        self.command('activate', '--id', 'R-B', '--reason', 'B unlocks the transport surface',
                     '--park-reason', 'Await transport evidence', '--park-wake-when', 'Transport available')
        # Every cli() uses a new process, without conversation context.
        before = (self.state / 'CURRENT.md').read_bytes()
        rows = self.command('list')['routes']
        self.assertEqual(before, (self.state / 'CURRENT.md').read_bytes())
        self.assertEqual([r['status'] for r in rows], ['parked', 'active'])
        self.assertIn('missing transport', rows[0]['resume_point'])
        self.assertEqual(rows[0]['wake_when'], 'Transport available')
        self.commit_all()
        code, ev = self.record()
        self.assertEqual(code, 0, ev)
        # Read the immutable ID from the ledger, not from fixture-authored expectations.
        files = list((self.state / 'ledger').rglob('EV-*.json'))
        self.assertEqual(len(files), 1)
        evidence_id = files[0].stem
        evidence_bytes = files[0].read_bytes()
        self.command('wake', '--id', 'R-A', '--reason', 'New transport observation',
                     '--trigger', 'Transport available from B', '--evidence', evidence_id)
        self.command('activate', '--id', 'R-A', '--reason', 'Test newly unblocked path',
                     '--park-reason', 'B retained for regression', '--park-wake-when', 'Transport changes')
        rows = self.command('list')['routes']
        self.assertEqual([r['status'] for r in rows], ['active', 'parked'])
        self.assertIn(evidence_id, rows[0]['evidence'])
        wake = [h for h in rows[0]['history'] if h['action'] == 'wake'][0]
        self.assertEqual(wake['trigger'], 'Transport available from B')
        self.assertEqual(files[0].read_bytes(), evidence_bytes)
        self.commit_all()
        before = (self.state / 'CURRENT.md').read_bytes()
        code, data = self.cli('dashboard', '--route', 'R-A')
        self.assertEqual(code, 0, data)
        self.assertEqual([r['id'] for r in data['payload']['routes']], ['R-A'])
        self.assertEqual(before, (self.state / 'CURRENT.md').read_bytes())
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_number_selection_is_guarded_by_the_displayed_portfolio(self):
        self.init()
        self.add('R-A')
        self.add('R-B', '--priority', '2')
        listing = self.command('list')
        self.assertEqual([c['id'] for c in listing['choices']], ['R-A', 'R-B'])
        revision = listing['portfolio_revision']
        selected = self.command('list', '--select', '2', '--portfolio-revision', revision)
        self.assertEqual(selected['routes'][0]['id'], 'R-B')
        self.rejected_without_write('activate', '--select', '2', '--reason', 'Select B')
        self.rejected_without_write('activate', '--select', '0', '--portfolio-revision', revision, '--reason', 'Invalid')
        result = self.command('activate', '--select', '2', '--portfolio-revision', revision, '--reason', 'Select B')
        self.assertFalse(result['research_authorized'])
        self.assertEqual(self.command('list')['choices'][0]['id'], 'R-B')
        self.rejected_without_write('park', '--select', '2', '--portfolio-revision', revision,
                                    '--reason', 'Old number', '--wake-when', 'Later')

    def test_switch_refuses_unfinished_execution_or_missing_handoff(self):
        self.init()
        self.add('R-A')
        self.add('R-B')
        self.command('activate', '--id', 'R-A', '--reason', 'Select A')
        self.rejected_without_write('activate', '--id', 'R-B', '--reason', 'Select B')
        code, out = self.cli('active', '--set-status', 'implementing')
        self.assertEqual(code, 0, out)
        self.rejected_without_write('activate', '--id', 'R-B', '--reason', 'Select B',
                                    '--park-reason', 'Defer', '--park-wake-when', 'Later')

    def test_graph_integrity_and_rejected_routes_need_evidence(self):
        self.init()
        self.add('R-A')
        self.add('R-B', '--depends-on', 'R-A')
        self.rejected_without_write('activate', '--id', 'R-B', '--reason', 'Premature')
        self.rejected_without_write('update', '--id', 'R-A', '--depends-on', 'R-B', '--reason', 'Cycle')
        self.rejected_without_write('update', '--id', 'R-A', '--alternatives', 'R-missing', '--reason', 'Bad ref')
        self.rejected_without_write('update', '--id', 'R-A', '--evidence', 'EV-missing', '--reason', 'Bad EV')
        self.rejected_without_write('close', '--id', 'R-A', '--outcome', 'rejected', '--reason', 'No evidence')
        self.rejected_without_write('park', '--id', 'R-A', '--reason', 'Defer', '--wake-when', '')
        self.rejected_without_write('update', '--id', 'R-A', '--priority', '0', '--reason', 'Invalid')

    def test_environment_block_wakes_to_queue_not_execution(self):
        self.init()
        self.add('R-A')
        self.command('block', '--id', 'R-A', '--reason', 'No local GPU', '--wake-when', 'Authorized GPU available')
        self.rejected_without_write('activate', '--id', 'R-A', '--reason', 'Bypass wake')
        result = self.command('wake', '--id', 'R-A', '--reason', 'Access now available',
                              '--trigger', 'Architect supplied authorized environment')
        self.assertFalse(result['research_authorized'])
        self.assertEqual(result['routes'][0]['status'], 'queued')
        self.assertEqual(json.loads((self.state / 'ACTIVE.json').read_text())['status'], 'idle')

    def test_legacy_absence_readonly_and_generic_writer_cannot_erase_routes(self):
        self.init(legacy=True)
        self.commit_all()
        self.assertFalse(self.command('list')['registered'])
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.add('R-A')
        before = (self.state / 'CURRENT.md').read_bytes()
        code, out = self.cli('current', '--set', 'research_routes=[]')
        self.assertNotEqual(code, 0, out)
        self.assertEqual(before, (self.state / 'CURRENT.md').read_bytes())

    def test_corrupt_portfolio_reported_by_validate_and_dashboard(self):
        self.init()
        path = self.state / 'CURRENT.md'
        text = path.read_text()
        block = schema.require_block(text, 'current', source=path.name)
        block['research_routes'] = [None]
        path.write_text(schema.replace_block(text, 'current', block))
        for cmd in ('validate', 'reconcile', 'dashboard', 'routes'):
            code, out = self.cli(cmd, *(['list'] if cmd == 'routes' else []))
            self.assertNotEqual(code, 0, out)
            self.assertIn('ROUTES_INVALID', [f['code'] for f in out['findings']])

    def test_completion_unlocks_dependency_but_inconclusive_cannot_reject(self):
        self.init()
        self.add('R-A')
        self.add('R-B', '--depends-on', 'R-A')
        self.commit_all()
        code, out = self.record()
        self.assertEqual(code, 0, out)
        evidence_id = next((self.state / 'ledger').rglob('EV-*.json')).stem
        self.rejected_without_write('close', '--id', 'R-A', '--outcome', 'rejected',
                                    '--evidence', evidence_id, '--reason', 'Not a negative')
        self.command('close', '--id', 'R-A', '--outcome', 'completed',
                     '--evidence', evidence_id, '--reason', 'Inspection question resolved within scope')
        self.command('activate', '--id', 'R-B', '--reason', 'Prerequisite now complete')
        self.rejected_without_write('wake', '--id', 'R-A', '--reason', 'Reopen', '--trigger', 'Changed inputs')

    def test_pending_manifest_blocks_switch_even_if_active_idle(self):
        self.init()
        self.add('R-A')
        # Deliberately construct the inconsistent pointer/manifest boundary.
        path = self.state / 'runs' / 'EXP-pending' / 'manifest.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'schema_version': '1.0', 'experiment_id': 'EXP-pending',
                                    'status': 'pending', 'code_state': {}, 'execution': {}}))
        self.rejected_without_write('activate', '--id', 'R-A', '--reason', 'Unsafe switch')

    def test_historical_interruption_does_not_lock_portfolio(self):
        self.init()
        self.add('R-A')
        path = self.state / 'runs' / 'EXP-old' / 'manifest.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'schema_version': '1.0', 'experiment_id': 'EXP-old',
                                    'status': 'interrupted', 'code_state': {}, 'execution': {}}))
        before = path.read_bytes()
        self.command('activate', '--id', 'R-A', '--reason', 'Resume unrelated research')
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(path.with_name('result.json').exists())

    def test_current_interruption_still_blocks_portfolio(self):
        self.init()
        self.add('R-A')
        path = self.state / 'runs' / 'EXP-current' / 'manifest.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'schema_version': '1.0', 'experiment_id': 'EXP-current',
                                    'status': 'interrupted', 'code_state': {}, 'execution': {}}))
        active = self.state / 'ACTIVE.json'
        data = json.loads(active.read_text())
        data['experiment_id'] = 'EXP-current'
        active.write_text(json.dumps(data))
        self.rejected_without_write('activate', '--id', 'R-A', '--reason', 'Unsafe switch')

    def test_incomplete_output_capture_still_blocks_portfolio(self):
        self.init()
        self.add('R-A')
        path = self.state / 'runs' / 'EXP-capture' / 'manifest.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'schema_version': '1.0', 'experiment_id': 'EXP-capture',
            'status': 'interrupted', 'code_state': {}, 'execution': {'output_capture_complete': False}}))
        self.rejected_without_write('activate', '--id', 'R-A', '--reason', 'Unsafe switch')

    def test_newer_schema_refuses_route_and_current_writes(self):
        self.init()
        path = self.state / 'CURRENT.md'
        text = path.read_text()
        block = schema.require_block(text, 'current', source=path.name)
        block['schema_version'] = '99.0'
        path.write_text(schema.replace_block(text, 'current', block))
        before = path.read_bytes()
        with self.assertRaises(AssertionError):
            self.add('R-A')
        self.assertEqual(before, path.read_bytes())
        code, out = self.cli('current', '--set', 'objective=new')
        self.assertNotEqual(code, 0, out)
        self.assertEqual(before, path.read_bytes())


if __name__ == '__main__':
    unittest.main()
