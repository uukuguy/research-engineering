import hashlib
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from researchlog.web import Snapshot, basis, handler, publish, validate_brief, display_revisions, current_translations, activity_revision


class WebDashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.state = self.root / '.research'
        self.state.mkdir()
        (self.state / 'ACTIVE.json').write_text('{}')

    def brief(self):
        data = {'version': 1, 'source_revision': basis(self.root)}
        for key in ('headline', 'goal', 'capability', 'gap', 'next', 'decision'):
            data[key] = {'text': '有界结论 <script>not markup</script>', 'refs': ['ACTIVE.json']}
        return data

    def test_publish_rejects_stale_and_does_not_mutate_canonical(self):
        source = self.root / 'brief.json'
        source.write_text(json.dumps(self.brief()))
        with patch.object(Snapshot, 'get', return_value={'source_revision': basis(self.root),
                                                       'payload': {}, 'events': []}):
            dest = publish(self.root, source)
        self.assertTrue(dest.is_file())
        self.assertEqual((self.state / 'ACTIVE.json').read_text(), '{}')
        self.assertEqual(json.loads(dest.read_text())['source_revision'], basis(self.root))
        (self.state / 'CURRENT.md').write_text('changed')
        with self.assertRaises(ValueError):
            publish(self.root, source)

    def test_brief_requires_substantive_fields_and_references(self):
        data = self.brief()
        data['gap']['refs'] = []
        with self.assertRaises(ValueError):
            validate_brief(data)

    def test_unrelated_changes_preserve_only_identical_row_translations(self):
        payload = {'routes': [{'id': 'R-A', 'title': 'navigation', 'status': 'active'}]}
        old = display_revisions(payload, [])
        brief = {'routes': {'R-A': {'text': '导航'}}, 'display_revisions': old}
        payload['current_observation'] = 'new unrelated evidence'
        self.assertIn('R-A', current_translations(brief, display_revisions(payload, []), False)['routes'])
        payload['routes'][0]['status'] = 'parked'
        self.assertNotIn('R-A', current_translations(brief, display_revisions(payload, []), False)['routes'])
        del brief['display_revisions']
        self.assertNotIn('R-A', current_translations(brief, old, False)['routes'])
        self.assertIn('R-A', current_translations(brief, old, True)['routes'])

    def test_activity_identity_survives_counters_not_direction_changes(self):
        payload = {'block': {'id': 'RB-2', 'objective': 'Attack defense', 'completed_evidence_iterations': 1}}
        first = activity_revision(payload)
        payload['block']['completed_evidence_iterations'] = 2
        self.assertEqual(first, activity_revision(payload))
        payload['block']['objective'] = 'Navigation'
        self.assertNotEqual(first, activity_revision(payload))

    def test_basis_ignores_derived_but_detects_ledger_changes(self):
        first = basis(self.root)
        (self.state / '.derived').mkdir()
        (self.state / '.derived/cache').write_text('noise')
        self.assertEqual(first, basis(self.root))
        (self.state / 'ledger').mkdir()
        (self.state / 'ledger/EV-new.json').write_text('{}')
        self.assertNotEqual(first, basis(self.root))

    def test_snapshot_missing_current_stale_and_inconsistent(self):
        result = {'payload': {'recorded_status': 'idle', 'routes': [], 'recent_evidence': []}, 'findings': []}
        with patch('researchlog.web.subprocess.run') as run:
            run.return_value.stdout = json.dumps(result)
            reader = Snapshot(self.root)
            self.assertEqual(reader.get()['brief_status'], 'missing')
            source = self.root / 'brief.json'
            source.write_text(json.dumps(self.brief()))
            publish(self.root, source)
            reader.checked = 0
            self.assertEqual(reader.get()['brief_status'], 'current')
            (self.state / 'CURRENT.md').write_text('new')
            reader.checked = 0
            self.assertEqual(reader.get()['brief_status'], 'stale')
            reader.checked = 0
            with patch('researchlog.web.basis', side_effect=['before', 'after']):
                with self.assertRaises(ValueError):
                    reader.get()

    def test_route_correction_is_newer_than_supporting_evidence(self):
        events = Snapshot.events({'recent_evidence': [{'id': 'EV', 'created_at': '2026-01-01T01:00:00Z'}],
            'routes': [{'id': 'R', 'title': 'navigation', 'history': [
                {'at': '2025-12-31T22:00:00-04:00', 'reason': 'surrogate invalid', 'to': 'parked'}]}]})
        self.assertEqual(events[0]['kind'], 'route')
        self.assertEqual(events[0]['detail'], 'surrogate invalid')

    def test_reports_are_registered_text_only_and_hash_checked(self):
        reader = Snapshot(self.root)
        doc = self.root / 'report.md'
        doc.write_text('result')
        record = {'path': 'report.md', 'recorded_sha256': hashlib.sha256(b'result').hexdigest()}
        with patch.object(reader, 'get', return_value={'payload': {'conclusions': [{'id': 'F', 'reports': [record]}]}}):
            self.assertEqual(reader.report('F', 0)['integrity'], 'match')
            doc.write_text('edited')
            self.assertEqual(reader.report('F', 0)['integrity'], 'changed')
            record['path'] = '../outside.md'
            with self.assertRaises(ValueError):
                reader.report('F', 0)
            record['path'] = 'page.html'
            with self.assertRaises(ValueError):
                reader.report('F', 0)
            with self.assertRaises(ValueError):
                reader.report('F', -1)

    def test_http_limits_host_origin_paths_and_writes(self):
        reader = Snapshot(self.root)
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler(reader))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def request(method, path, headers=None):
                client = HTTPConnection('127.0.0.1', server.server_port)
                client.request(method, path, headers=headers or {})
                response = client.getresponse()
                code, body, csp = response.status, response.read(), response.getheader('Content-Security-Policy')
                client.close()
                return code, body, csp
            code, body, csp = request('GET', '/')
            self.assertEqual(code, 200)
            self.assertIn('frame-ancestors', csp)
            self.assertIn('研究工作台'.encode(), body)
            self.assertEqual(request('GET', '/', {'Host': 'attacker.example'})[0], 403)
            self.assertEqual(request('GET', '/', {'Origin': 'https://attacker.example'})[0], 403)
            self.assertEqual(request('GET', '/../../TASK.md')[0], 404)
            self.assertEqual(request('POST', '/api/snapshot')[0], 501)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
