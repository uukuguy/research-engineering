"""Execution pointer checks must also run after ACTIVE becomes idle."""
from types import SimpleNamespace

from researchlog import repo
from researchlog.commands.reconcile import _active_manifest_stale
from researchlog.tests.test_commands import CommandTestCase


class ActiveRunPointerTests(CommandTestCase):
    def check_pointer(self, execution, manifest_status, path=None):
        expected = 'research/runs/EXP-pointer/manifest.json'
        code, result = self.invoke(['active', '--set', 'status=idle',
            '--set', 'experiment_id=EXP-pointer', '--set', 'execution.status=' + execution,
            '--set', 'execution.run_manifest=' + (path or expected)])
        self.assertEqual(code, 0, result)
        before = self.research('ACTIVE.json').read_bytes()
        manifests = {} if manifest_status is None else {
            'EXP-pointer': {'experiment_id': 'EXP-pointer', 'status': manifest_status}}
        result = _active_manifest_stale(repo.require(self.root),
                                      SimpleNamespace(manifests=manifests), SimpleNamespace())
        self.assertEqual(self.research('ACTIVE.json').read_bytes(), before)
        return {f.code for f in result}

    def test_idle_completed_cannot_point_to_interrupted_run(self):
        self.assertIn('ACTIVE_MANIFEST_STALE', self.check_pointer('completed', 'interrupted'))

    def test_terminal_pointer_requires_existing_manifest(self):
        self.assertIn('ACTIVE_MANIFEST_MISSING', self.check_pointer('completed', None))

    def test_run_path_must_match_experiment_identity(self):
        self.assertIn('ACTIVE_MANIFEST_POINTER_MISMATCH', self.check_pointer(
            'completed', 'completed', 'research/runs/EXP-other/manifest.json'))

    def test_matching_terminal_status_is_valid(self):
        self.assertEqual(self.check_pointer('completed', 'completed'), set())
        self.assertEqual(self.check_pointer('interrupted', 'interrupted'), set())

    def test_planned_run_does_not_require_a_manifest_yet(self):
        self.assertEqual(self.check_pointer('idle', None), set())

    def test_running_completion_still_detected(self):
        self.assertIn('ACTIVE_MANIFEST_STALE', self.check_pointer('running', 'completed'))
