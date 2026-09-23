import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from researchlog.commands.dashboard import finding_index


class FindingsDashboardTests(unittest.TestCase):
    def test_status_and_report_follow_evidence_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / 'report.md'
            report.write_text('研究结论与限制')
            entry = {'id': 'FND-old', 'title': 'old claim', 'status': 'Superseded',
                     'evidence': ['EV-one'], 'superseded_by': 'FND-new', 'reason': 'new evidence'}
            ledger = SimpleNamespace(findings_entries=[entry], records={'EV-one': {
                'artifacts': [{'path': 'report.md', 'role': 'research-report'},
                              {'path': 'absent.md', 'role': 'research-report'},
                              {'path': '../outside.md', 'role': 'research-report'},
                              {'path': 'stdout.log', 'role': 'log'}]}})
            rows = finding_index(SimpleNamespace(root=root), ledger)
            self.assertEqual(rows[0]['status'], 'Superseded')
            self.assertEqual(rows[0]['superseded_by'], 'FND-new')
            self.assertEqual([r['availability'] for r in rows[0]['reports']],
                             ['present', 'missing', 'outside_project'])
            self.assertNotIn('reports', entry)
            self.assertEqual(report.read_text(), '研究结论与限制')

    def test_missing_report_not_invented(self):
        ledger = SimpleNamespace(findings_entries=[{'id': 'FND-1', 'status': 'Open',
                                                     'evidence': ['EV-missing']}], records={})
        self.assertEqual(finding_index(SimpleNamespace(root=Path.cwd()), ledger)[0]['reports'], [])

    def test_external_symlink_not_treated_as_portable_report(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            root = Path(a)
            outside = Path(b) / 'report.md'
            outside.write_text('external')
            (root / 'report.md').symlink_to(outside)
            ledger = SimpleNamespace(findings_entries=[{'id': 'FND-1', 'evidence': ['EV-1']}],
                records={'EV-1': {'artifacts': [{'path': 'report.md', 'role': 'research-report'}]}})
            self.assertEqual(finding_index(SimpleNamespace(root=root), ledger)[0]['reports'][0]['availability'],
                             'outside_project')
