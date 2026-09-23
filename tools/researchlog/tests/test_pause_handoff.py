"""Pause regressions: exact checkpoint scope and ledger-derived close checks."""
import json
import unittest
from types import SimpleNamespace

from researchlog import handoff, repo
from researchlog.tests import test_production_boundaries as fixtures


class PauseHandoffTests(unittest.TestCase):
    setUp = fixtures.ProductionBoundaryTests.setUp
    git = fixtures.ProductionBoundaryTests.git
    cli = fixtures.ProductionBoundaryTests.cli
    init = fixtures.ProductionBoundaryTests.init
    commit_all = fixtures.ProductionBoundaryTests.commit_all
    record = fixtures.ProductionBoundaryTests.record

    def test_explicit_checkpoint_does_not_expand_to_expected_paths(self):
        self.init()
        self.commit_all()
        (self.root / 'wanted.py').write_text('wanted\n')
        (self.root / 'unrelated.py').write_text('user work\n')
        self.cli('active', '--set', 'git.expected_touched_files=["unrelated.py"]')
        code, result = self.cli('checkpoint', '--paths', 'wanted.py', '--dry-run')
        self.assertEqual(code, 0, result)
        self.assertEqual(result['payload']['files'], ['wanted.py'])
        code, result = self.cli('checkpoint', '--paths', 'wanted.py')
        self.assertEqual(code, 0, result)
        self.assertEqual(self.git('show', '--pretty=', '--name-only', 'HEAD').strip(), 'wanted.py')

    def test_handoff_counts_refresh_without_belief_or_status_change(self):
        self.init()
        self.commit_all()
        self.cli('active', '--set', 'block.id=RB-TEST')
        code, evidence = self.record(counted=True)
        self.assertEqual(code, 0, evidence)
        code, result = self.cli('reconcile', '--handoff')
        self.assertNotEqual(code, 0, result)
        self.assertIn('HANDOFF_COUNTS_STALE', {f['code'] for f in result['findings']})
        before = json.loads((self.state / 'ACTIVE.json').read_text())
        code, result = self.cli('active', '--refresh-counts')
        self.assertEqual(code, 0, result)
        after = json.loads((self.state / 'ACTIVE.json').read_text())
        self.assertEqual(after['block']['completed_evidence_iterations'], 1)
        self.assertEqual(after['block']['belief_delta'], before['block']['belief_delta'])
        self.assertEqual(after['status'], before['status'])
        code, result = self.cli('reconcile', '--handoff')
        codes = {f['code'] for f in result['findings']}
        self.assertNotIn('HANDOFF_COUNTS_STALE', codes)
        self.assertIn('HANDOFF_CURRENT_MISSING_EVIDENCE', codes)

    def test_handoff_requires_current_checkpoint_and_preserves_readonly(self):
        self.init()
        self.commit_all()
        self.cli('current', '--set', 'next_empirical_action=Pause and brief architect')
        before = (self.state / 'CURRENT.md').read_bytes()
        code, result = self.cli('reconcile', '--handoff')
        self.assertNotEqual(code, 0, result)
        self.assertIn('HANDOFF_NOT_CHECKPOINTED', {f['code'] for f in result['findings']})
        self.assertEqual((self.state / 'CURRENT.md').read_bytes(), before)
        self.commit_all()
        code, result = self.cli('reconcile', '--handoff')
        self.assertNotIn('HANDOFF_NOT_CHECKPOINTED', {f['code'] for f in result['findings']})

    def test_active_checkpoint_stamp_allowed_but_semantic_dirty_state_refused(self):
        self.init()
        self.commit_all()
        self.cli('active', '--set-observation', 'Saved partial result')
        code, result = self.cli('checkpoint', '--paths', '.research/ACTIVE.json')
        self.assertEqual(code, 0, result)
        code, result = self.cli('reconcile', '--handoff')
        self.assertNotIn('HANDOFF_NOT_CHECKPOINTED', {f['code'] for f in result['findings']})
        self.cli('active', '--set-observation', 'Not checkpointed')
        code, result = self.cli('reconcile', '--handoff')
        self.assertIn('HANDOFF_NOT_CHECKPOINTED', {f['code'] for f in result['findings']})

    def test_incomplete_capture_blocks_handoff_even_if_run_is_interrupted(self):
        self.init()
        self.commit_all()
        self.cli('active', '--set', 'experiment_id=EXP-capture')
        manifest = {'status': 'interrupted', 'execution': {'output_capture_complete': False}}
        ledger = SimpleNamespace(records={}, manifests={'EXP-capture': manifest})
        findings = handoff.inspect(repo.require(self.root), ledger)
        self.assertIn('HANDOFF_CAPTURE_UNRESOLVED', {f.code for f in findings})
        manifest['execution']['output_capture_complete'] = True
        findings = handoff.inspect(repo.require(self.root), ledger)
        self.assertNotIn('HANDOFF_CAPTURE_UNRESOLVED', {f.code for f in findings})
