import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/research-engineering/scripts/safe_preview.py'


class SafePreviewTests(unittest.TestCase):
    def check_bytes(self, raw, *args):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'sample'
            path.write_bytes(raw)
            run = subprocess.run([sys.executable, str(SCRIPT), str(path), *args], capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertTrue(all(b == 10 or 32 <= b < 127 for b in run.stdout))
            return json.loads(run.stdout)

    def test_terminal_shift_and_escape_bytes_never_emitted(self):
        result = self.check_bytes(b'\xcf\xfa\xed\xfe\x00\x0e\x0f\x1b(0')
        self.assertEqual(result['kind'], 'binary_or_control_bytes')
        self.assertNotIn('text', result)

    def test_valid_text_is_preserved_inside_escaped_json(self):
        text = '中文\n#usda 1.0\tOK\n'
        self.assertEqual(self.check_bytes(text.encode())['text'], text)

    def test_text_with_escape_is_binary_even_when_utf8_valid(self):
        self.assertEqual(self.check_bytes(b'hello\x1b[2J')['kind'], 'binary_or_control_bytes')

    def test_bounded_preview_handles_split_utf8(self):
        result = self.check_bytes('a中end'.encode(), '--limit', '2')
        self.assertTrue(result['truncated'])
        self.assertEqual(result['text'], 'a')

    def test_missing_file_error_is_escaped(self):
        with tempfile.TemporaryDirectory() as folder:
            run = subprocess.run([sys.executable, str(SCRIPT), folder + '/missing\x1b'], capture_output=True)
            self.assertEqual(run.returncode, 2)
            self.assertNotIn(b'\x1b', run.stdout)
            self.assertIn('error', json.loads(run.stdout))


if __name__ == '__main__':
    unittest.main()
