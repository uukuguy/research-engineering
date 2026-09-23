"""Real nested-process regressions; no simulator or live project involved."""
import json
import os
import signal
import subprocess
import sys
import time
import unittest

from researchlog.tests import test_production_boundaries as fixtures


@unittest.skipUnless(os.name == 'posix', 'POSIX process-group supervision')
class RunTimeoutTests(unittest.TestCase):
    setUp = fixtures.ProductionBoundaryTests.setUp
    git = fixtures.ProductionBoundaryTests.git
    cli = fixtures.ProductionBoundaryTests.cli
    init = fixtures.ProductionBoundaryTests.init

    def nested(self, parent_exits=False):
        self.init()
        # The descendant exits by itself after 3 seconds even against the old code.
        marker = self.root / 'escaped-work'
        child = ('import time,pathlib; print("child-started", flush=True); '
                 f'time.sleep(3); pathlib.Path({str(marker)!r}).write_text("late")')
        parent = ('import subprocess,sys,time; '
                  f'p=subprocess.Popen([sys.executable,"-c",{child!r}]); '
                  + ('' if parent_exits else 'p.wait()'))
        began = time.monotonic()
        code, result = self.cli('run', '--experiment-id', 'EXP-timeout',
                                '--timeout', '0.4', '--heartbeat-interval', '0',
                                '--', sys.executable, '-c', parent)
        elapsed = time.monotonic() - began
        self.assertEqual(code, 3, result)
        self.assertEqual(result['payload']['status'], 'interrupted')
        self.assertLess(elapsed, 2.5, result)
        run = self.state / 'runs/EXP-timeout'
        manifest = json.loads((run / 'manifest.json').read_text())
        self.assertEqual(manifest['interruption_reason'], 'timeout')
        self.assertTrue(manifest['execution']['output_capture_complete'])
        self.assertFalse((run / 'result.json').exists())
        self.assertIn('child-started', (run / 'stdout.log').read_text())
        time.sleep(0.1)
        self.assertFalse(marker.exists())
        return manifest

    def test_timeout_stops_descendant_and_keeps_partial_log(self):
        # An unrelated process must survive our group signal.
        unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'])
        try:
            manifest = self.nested()
            self.assertIsNone(unrelated.poll())
            self.assertEqual(manifest['execution']['process_group_id'],
                             manifest['execution']['pid_or_job_id'])
        finally:
            if unrelated.poll() is None:
                unrelated.terminate()
            unrelated.wait(timeout=3)

    def test_timeout_applies_after_launcher_exits_with_open_child_pipes(self):
        self.nested(parent_exits=True)

    def test_invalid_timeout_does_not_create_run(self):
        self.init()
        for value in ('0', '-1', 'nan', 'inf'):
            code, result = self.cli('run', '--experiment-id', 'EXP-invalid',
                                    '--timeout', value, '--', sys.executable, '-c', 'pass')
            self.assertNotEqual(code, 0, result)
            self.assertFalse((self.state / 'runs/EXP-invalid').exists())

    def test_detached_child_is_reported_without_blocking_close(self):
        self.init()
        child = 'import time; print("detached", flush=True); time.sleep(3)'
        parent = ('import subprocess,sys; '
                  f'subprocess.Popen([sys.executable,"-c",{child!r}],start_new_session=True)')
        began = time.monotonic()
        code, result = self.cli('run', '--experiment-id', 'EXP-detached',
                                '--timeout', '0.4', '--heartbeat-interval', '0',
                                '--', sys.executable, '-c', parent)
        try:
            self.assertEqual(code, 3, result)
            self.assertLess(time.monotonic() - began, 2.5)
            self.assertIn('RUN_OUTPUT_CAPTURE_INCOMPLETE',
                          {f['code'] for f in result['findings']})
            run = self.state / 'runs/EXP-detached'
            manifest = json.loads((run / 'manifest.json').read_text())
            self.assertFalse(manifest['execution']['output_capture_complete'])
            self.assertFalse((run / 'result.json').exists())
        finally:
            # The deliberately detached fixture is finite; let it exit itself.
            time.sleep(max(0, began + 3.5 - time.monotonic()))

    def test_interrupt_supervisor_closes_owned_run(self):
        self.init()
        entry = fixtures.ENTRY
        argv = [sys.executable, str(entry), 'run', '--json', '--experiment-id',
                'EXP-interrupt', '--heartbeat-interval', '0', '--', sys.executable,
                '-c', 'import time; print("ready", flush=True); time.sleep(3)']
        process = subprocess.Popen(argv, cwd=self.root, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        try:
            log = self.state / 'runs/EXP-interrupt/stdout.log'
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                if log.exists() and 'ready' in log.read_text():
                    break
                time.sleep(0.03)
            else:
                self.fail('fixture did not start')
            process.send_signal(signal.SIGINT)
            stdout, stderr = process.communicate(timeout=2)
            result = json.loads(stdout)
            self.assertEqual(process.returncode, 3, (result, stderr))
            manifest = json.loads((log.parent / 'manifest.json').read_text())
            self.assertEqual(manifest['interruption_reason'], 'process_signal')
            self.assertFalse((log.parent / 'result.json').exists())
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
